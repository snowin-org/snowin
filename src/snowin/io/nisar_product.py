"""Read NISAR GUNW products and return SnowIn xarray variables.

Retrieval functions receive phase and incidence in SnowIn's required
units and direction; they do not read NISAR source conventions.
"""

from __future__ import annotations

import json
import math
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import numpy as np
import xarray as xr

from .._precision import as_science_float
from ._nisar_hdf5 import (
    IDENTIFICATION_GROUP,
    RADAR_GRID_GROUP,
    _read_radar_grid_incidence,
    _read_radar_los,
    read_attrs_hdf5,
    read_scalar_hdf5,
)
from .geometry import (
    _DEM_SOURCE_METADATA,
    DEMSource,
    _open_dem,
    _progress,
    _validate_dem_source,
    compute_local_incidence,
)
from .phase_normalization import (
    NISAR_GUNW_PHASE_TRANSFORM,
    NISAR_GUNW_SOURCE_PHASE_DEFINITION,
    _build_phase_normalized_dataset,
    _iso_utc,
    _positive_scalar,
    _require_2d,
    _require_aligned,
    _serializable_attrs,
    normalize_gunw_pair,
)

_SPEED_OF_LIGHT_M_S = 299_792_458.0

_KNOWN_SOURCE_ANGLE_UNITS = {"degree", "degrees", "deg"}


def read_gunw_wavelength_m(
    gunw_file: str | Path,
    *,
    frequency: str = "frequencyA",
) -> float:
    """Resolve wavelength from the GUNW authoritative center-frequency field."""
    path = f"/science/LSAR/GUNW/grids/{frequency}/centerFrequency"
    center_frequency = read_scalar_hdf5(gunw_file, path)
    attrs = read_attrs_hdf5(gunw_file, path)
    if center_frequency is None:
        raise ValueError(f"GUNW center-frequency metadata is missing at {path}")
    frequency_units = attrs.get("units")
    if frequency_units is None:
        raise ValueError(f"GUNW center-frequency units are missing at {path}")
    if frequency_units not in {"hertz", "Hz"}:
        raise ValueError(
            f"GUNW center-frequency units {frequency_units!r} are unsupported at "
            f"{path}; expected hertz"
        )
    frequency_hz = _positive_scalar("center_frequency_hz", center_frequency)
    return _SPEED_OF_LIGHT_M_S / frequency_hz


def _open_nisar_gunw_layer(
    path: Path,
    *,
    frequency: str,
    polarization: str | None,
    chunks: dict[str, int] | str | None,
) -> tuple[Any, xr.Dataset, str]:
    """Open a GUNW layer through nisar_pytools and return its owning tree."""
    try:
        from nisar_pytools import open_nisar
    except ImportError as exc:
        raise ImportError(
            "Opening NISAR GUNW files requires nisar_pytools; install SnowIn "
            "with the 'nisar' extra"
        ) from exc

    tree = open_nisar(path, chunks=chunks)
    try:
        layer_path = f"science/LSAR/GUNW/grids/{frequency}/unwrappedInterferogram"
        available = list(tree[layer_path].children)
        if polarization is None:
            polarization = next((pol for pol in ("HH", "VV") if pol in available), None)
        if polarization is None or polarization not in available:
            raise ValueError(
                "GUNW does not contain the requested HH or VV unwrapped phase "
                f"layer; available polarizations: {available}"
            )
        layer_path = f"{layer_path}/{polarization}"
        layer = tree[layer_path].to_dataset()
        if not isinstance(layer, xr.Dataset):
            raise TypeError("nisar_pytools did not expose the GUNW layer as a Dataset")
        return tree, layer, polarization
    except Exception:
        # nisar_pytools owns the HDF5 handle through a DataTree finalizer.
        # Dropping this reference releases it on exceptional open paths.
        del tree
        raise


def _nisar_acquisition_time(path: Path, role: Literal["reference", "secondary"]) -> str:
    """Read a NISAR UTC time, whose product format omits the timezone suffix."""
    value = read_scalar_hdf5(
        path,
        f"{IDENTIFICATION_GROUP}/{role}ZeroDopplerStartTime",
    )
    if value is None or str(value) in {"NaT", ""}:
        raise ValueError(f"GUNW is missing required {role} acquisition time metadata")
    text = str(value).strip()
    parseable = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(parseable)
    except ValueError:
        return _iso_utc(value, f"{role}_time")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        # NISAR's product format defines these fields as UTC while omitting
        # an offset suffix. Make that product-specific rule explicit here;
        # see the NISAR L2 Product Format Document v1.2.1. Generic SnowIn
        # timestamp inputs still require Z or an offset.
        text = f"{text}Z"
    return _iso_utc(text, f"{role}_time")


def open_gunw(
    gunw_file: str | Path,
    *,
    wavelength_m: float | None = None,
    polarization: str | None = None,
    frequency: str = "frequencyA",
    chunks: dict[str, int] | str | None = "auto",
    progress: bool = True,
) -> xr.Dataset:
    """Open a NISAR GUNW and preserve its delivered phase without calculating incidence.

    This fast product-inspection step opens the phase, coherence, connected
    components, ionospheric screens, tropospheric screens, coordinates,
    metadata, and wavelength. Radar-grid tropospheric screens retain their
    native ``radar_height``, ``radar_y``, and ``radar_x`` dimensions because
    they are not on the interferogram grid. Correction layers are exposed but
    never applied. It deliberately does not download a DEM or read the
    radar-grid LOS cube. Call
    :func:`add_gunw_incidence` with the same explicit GUNW path when the
    terrain-surface incidence angle is needed.

    ``chunks='auto'`` preserves lazy Dask-backed arrays.  Pass ``chunks=None``
    for an eager read when Dask is not installed.
    """
    path = Path(gunw_file).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"GUNW file not found: {path}")
    if polarization is not None and polarization not in {"HH", "VV"}:
        raise ValueError("polarization must be 'HH', 'VV', or None")
    _progress(f"opening GUNW phase data from {path.name}", progress)
    tree, phase_ds, pol = _open_nisar_gunw_layer(
        path,
        frequency=frequency,
        polarization=polarization,
        chunks=chunks,
    )
    try:
        if "unwrappedPhase" not in phase_ds:
            raise ValueError("GUNW phase layer is missing unwrappedPhase")
        if "x" not in phase_ds.coords or "y" not in phase_ds.coords:
            raise ValueError("GUNW phase layer is missing x/y grid coordinates")
        source_projection = phase_ds.get("spatial_ref")
        if source_projection is None:
            # nisar_pytools exposes the GUNW grid-mapping variable as
            # ``projection`` and carries its EPSG code in Dataset attrs.
            source_projection = phase_ds.get("projection")
        if source_projection is None:
            raise ValueError("GUNW phase layer is missing its projection metadata")

        raw_phase = phase_ds["unwrappedPhase"].rename("unwrappedPhase")
        if raw_phase.dims != ("y", "x"):
            raise ValueError(
                "GUNW unwrappedPhase must use dimensions ('y', 'x'); "
                f"got {raw_phase.dims!r}"
            )
        phase_units = raw_phase.attrs.get("units")
        if phase_units is None or (
            isinstance(phase_units, str) and not phase_units.strip()
        ):
            raise ValueError("GUNW unwrappedPhase units are missing; expected radians")
        phase_units = str(phase_units).lower()
        if phase_units not in {"radians", "radian", "rad"}:
            raise ValueError(
                f"GUNW unwrappedPhase units {phase_units!r} are unsupported; "
                "expected radians"
            )
        raw_phase.attrs["units"] = phase_units

        additional: dict[str, xr.DataArray] = {}
        for source_name, snowin_name in {
            "coherenceMagnitude": "coherence",
            "connectedComponents": "connected_component",
            "ionospherePhaseScreen": "ionosphere",
            "ionospherePhaseScreenUncertainty": "ionosphere_unc",
        }.items():
            if source_name in phase_ds:
                variable = phase_ds[source_name]
                if variable.dims != ("y", "x"):
                    raise ValueError(
                        f"GUNW {source_name} must use dimensions ('y', 'x')"
                    )
                layer_attrs = _serializable_attrs(variable.attrs)
                layer_attrs.update(
                    {
                        "source_variable": source_name,
                        "grid_mapping": "spatial_ref",
                    }
                )
                if snowin_name in {"ionosphere", "ionosphere_unc"}:
                    layer_attrs["correction_status"] = "available_not_applied"
                additional[snowin_name] = xr.DataArray(
                    variable.data,
                    dims=("y", "x"),
                    coords={
                        "y": raw_phase.coords["y"],
                        "x": raw_phase.coords["x"],
                    },
                    attrs=layer_attrs,
                    name=snowin_name,
                )

        radar_grid_path = "science/LSAR/GUNW/metadata/radarGrid"
        try:
            radar_grid = tree[radar_grid_path].to_dataset()
        except KeyError:
            radar_grid = None
        if radar_grid is not None:
            for source_name, snowin_name in {
                "hydrostaticTroposphericPhaseScreen": "hydro_tropo",
                "wetTroposphericPhaseScreen": "wet_tropo",
            }.items():
                if source_name not in radar_grid:
                    continue
                variable = radar_grid[source_name]
                if len(variable.dims) == 3 and variable.dims[-2:] == ("y", "x"):
                    height_dim = variable.dims[0]
                    dimensions = ("radar_height", "radar_y", "radar_x")
                    source_dimensions = (height_dim, "y", "x")
                elif variable.dims == ("y", "x"):
                    dimensions = ("radar_y", "radar_x")
                    source_dimensions = ("y", "x")
                else:
                    raise ValueError(
                        f"GUNW {source_name} must use a radar-grid y/x plane, "
                        "optionally with a leading height dimension; "
                        f"got {variable.dims!r}"
                    )
                coords = {
                    target: xr.DataArray(
                        variable.coords[source].data,
                        dims=(target,),
                        attrs=_serializable_attrs(variable.coords[source].attrs),
                    )
                    for source, target in zip(source_dimensions, dimensions)
                }
                if "radar_height" in coords:
                    coords["radar_height"].attrs.setdefault("units", "m")
                    coords["radar_height"].attrs.setdefault(
                        "long_name", "height above ellipsoid"
                    )
                layer_attrs = _serializable_attrs(variable.attrs)
                layer_attrs.update(
                    {
                        "source_variable": source_name,
                        "source_grid": "NISAR GUNW radarGrid",
                        "grid_mapping": "spatial_ref",
                        "correction_status": "available_not_applied",
                    }
                )
                additional[snowin_name] = xr.DataArray(
                    variable.data,
                    dims=dimensions,
                    coords=coords,
                    attrs=layer_attrs,
                    name=snowin_name,
                )

        spatial_ref_attrs = _serializable_attrs(source_projection.attrs)
        if "epsg_code" not in spatial_ref_attrs:
            dataset_epsg = phase_ds.attrs.get("projection")
            if dataset_epsg is not None:
                spatial_ref_attrs["epsg_code"] = _serializable_attrs(
                    {"epsg_code": dataset_epsg}
                )["epsg_code"]
        spatial_ref = xr.DataArray(
            source_projection.data,
            attrs=spatial_ref_attrs,
            name="spatial_ref",
        )
        granule_id = read_scalar_hdf5(path, f"{IDENTIFICATION_GROUP}/granuleId")
        source_paths = {
            "phase": (
                f"/science/LSAR/GUNW/grids/{frequency}/"
                f"unwrappedInterferogram/{pol}/unwrappedPhase"
            ),
            "center_frequency": (
                f"/science/LSAR/GUNW/grids/{frequency}/centerFrequency"
            ),
        }
        optional_layer_paths = {
            "ionosphere": (
                f"/science/LSAR/GUNW/grids/{frequency}/"
                f"unwrappedInterferogram/{pol}/ionospherePhaseScreen"
            ),
            "ionosphere_unc": (
                f"/science/LSAR/GUNW/grids/{frequency}/"
                f"unwrappedInterferogram/{pol}/ionospherePhaseScreenUncertainty"
            ),
            "hydro_tropo": (
                "/science/LSAR/GUNW/metadata/radarGrid/"
                "hydrostaticTroposphericPhaseScreen"
            ),
            "wet_tropo": (
                "/science/LSAR/GUNW/metadata/radarGrid/wetTroposphericPhaseScreen"
            ),
        }
        source_paths.update(
            {
                name: path
                for name, path in optional_layer_paths.items()
                if name in additional
            }
        )
        source_metadata = {
            "source_dataset_paths": json.dumps(source_paths, sort_keys=True),
            "source_reader": "nisar_pytools.open_nisar; SnowIn identity phase normalization",
            "source_acquisition_time_zone": (
                "UTC per NISAR L2 Product Format Document v1.2.1"
            ),
            "wavelength_source": (
                "explicit wavelength_m override"
                if wavelength_m is not None
                else "NISAR GUNW centerFrequency metadata via c/f"
            ),
            "incidence_angle_status": "not_computed",
        }
        result = _build_phase_normalized_dataset(
            raw_phase,
            spatial_ref,
            source_phase_difference_definition=NISAR_GUNW_SOURCE_PHASE_DEFINITION,
            reference_time=_nisar_acquisition_time(path, "reference"),
            secondary_time=_nisar_acquisition_time(path, "secondary"),
            wavelength_m=(
                _positive_scalar("wavelength_m", wavelength_m)
                if wavelength_m is not None
                else read_gunw_wavelength_m(path, frequency=frequency)
            ),
            source_granule_id=str(granule_id) if granule_id is not None else None,
            additional_variables=additional,
            native_grid_dimensions={
                name: (
                    ("radar_height", "radar_y", "radar_x"),
                    ("radar_y", "radar_x"),
                )
                for name in ("hydro_tropo", "wet_tropo")
            },
            source_metadata={**source_metadata, "correction_layers_applied": False},
        )
    except Exception:
        del tree
        raise

    tree_holder = [tree]

    def close() -> None:
        tree_holder.clear()

    result.set_close(close)
    return result


def compute_gunw_incidence(
    gunw_file: str | Path,
    target: xr.Dataset,
    *,
    dem_source: DEMSource = "nisar_cop30",
    dem: str | Path | xr.DataArray | None = None,
    dem_vertical_correction_m: xr.DataArray | str | Path | None = None,
    require_vertical_datum_match: bool = False,
    incidence_source: str = "cop30_local",
    radar_cube_index: int = 0,
    incidence_resampling: str = "linear",
    chunks: dict[str, int] | str | None = None,
    geometry_chunks: int | tuple[int, int] | None = None,
    progress: bool = True,
) -> xr.DataArray:
    """Compute incidence for an explicit GUNW and an already-open target.

    The explicit ``gunw_file`` requirement prevents geometry from being
    inferred from, or silently substituted for, another product. For local
    incidence, callers must supply a prepared DEM through ``dem``; SnowIn does
    not acquire or cache ancillary elevation data. When ``target`` records a
    ``source_granule_id``, SnowIn verifies it against the explicit GUNW before
    reading geometry. The returned two-dimensional DataArray is aligned to
    ``target.phase``; :func:`add_gunw_incidence` appends it to the target
    Dataset.
    """
    if not isinstance(target, xr.Dataset) or "phase" not in target:
        raise TypeError("target must be an xarray.Dataset containing 'phase'")
    _require_2d("phase", target["phase"])
    path = Path(gunw_file).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"GUNW file not found: {path}")
    target_granule_id = target.attrs.get("source_granule_id")
    if target_granule_id is not None:
        gunw_granule_id = read_scalar_hdf5(path, f"{IDENTIFICATION_GROUP}/granuleId")
        if gunw_granule_id is None:
            raise ValueError(
                "GUNW is missing granuleId needed to verify it matches the target"
            )
        if str(gunw_granule_id) != str(target_granule_id):
            raise ValueError(
                "GUNW granuleId does not match target source_granule_id: "
                f"{gunw_granule_id!r} != {target_granule_id!r}"
            )
    dem_source = _validate_dem_source(dem_source)
    vertical_correction_m = dem_vertical_correction_m
    if incidence_source not in {"cop30_local", "product_ellipsoid"}:
        raise ValueError(
            "incidence_source must be 'cop30_local' or 'product_ellipsoid'"
        )
    if incidence_resampling not in {"linear", "nearest"}:
        raise ValueError("incidence_resampling must be 'linear' or 'nearest'")
    epsg_code = target.spatial_ref.attrs.get("epsg_code")
    if epsg_code is None:
        raise ValueError("target spatial_ref is missing epsg_code")
    if incidence_source == "product_ellipsoid":
        _progress("opening GUNW ellipsoid incidence field", progress)
        values, x_radar, y_radar, source_attrs = _read_radar_grid_incidence(
            path, radar_cube_index=radar_cube_index
        )
        source_incidence_units = source_attrs.get("units")
        if source_incidence_units is None:
            raise ValueError("GUNW incidenceAngle units are missing; expected degrees")
        if source_incidence_units not in _KNOWN_SOURCE_ANGLE_UNITS:
            raise ValueError(
                f"GUNW incidenceAngle units {source_incidence_units!r} are "
                "unsupported; expected degrees"
            )
        raw_incidence = xr.DataArray(
            values,
            dims=("y", "x"),
            coords={"y": y_radar, "x": x_radar},
            attrs=_serializable_attrs(source_attrs),
            name="incidence_angle",
        )
        incidence = raw_incidence * (math.pi / 180.0)
        incidence.attrs = _serializable_attrs(raw_incidence.attrs)
        incidence.attrs.update(
            {
                "units": "rad",
                "incidence_angle_reference": "ellipsoid",
                "incidence_angle_origin": "product_ellipsoid",
                "source_units": source_incidence_units,
                "source_variable": "incidenceAngle",
            }
        )
        phase = target["phase"]
        already_aligned = np.array_equal(
            incidence.coords["x"].data, phase.coords["x"].data
        ) and np.array_equal(incidence.coords["y"].data, phase.coords["y"].data)
        if already_aligned:
            incidence = incidence.assign_coords(
                x=phase.coords["x"], y=phase.coords["y"]
            )
        else:
            incidence = incidence.interp_like(phase, method=incidence_resampling)
        incidence.attrs.update(
            {
                "incidence_angle_source": "NISAR GUNW radarGrid ellipsoid incidenceAngle",
                "incidence_angle_source_dataset_path": (
                    f"{RADAR_GRID_GROUP}/incidenceAngle"
                ),
                "incidence_angle_origin": "product_ellipsoid",
                "incidence_angle_grid_alignment": (
                    "already_aligned" if already_aligned else "resampled_to_phase_grid"
                ),
                "incidence_angle_resampling": (
                    "none" if already_aligned else incidence_resampling
                ),
                "incidence_angle_radar_cube_index": radar_cube_index,
            }
        )
        return as_science_float(incidence).rename("incidence_angle")

    _progress("preparing DEM for local incidence", progress)
    target_x = np.asarray(target.coords["x"].data)
    target_y = np.asarray(target.coords["y"].data)
    if dem is None or (isinstance(dem, str) and dem == "auto"):
        raise ValueError(
            "local incidence requires a caller-supplied prepared DEM path or "
            "xarray.DataArray; SnowIn does not download DEMs"
        )
    if dem_source != "nisar_cop30":
        warnings.warn(
            "SnowIn recommends the NISAR-modified Copernicus DEM "
            '(dem_source="nisar_cop30") for NISAR local-incidence geometry. '
            f"The selected DEM source is {dem_source!r}; verify its vertical "
            "datum and apply any required geoid/ellipsoid correction.",
            UserWarning,
            stacklevel=2,
        )
    dem_input = dem
    dem_grid = _open_dem(
        dem_input,
        x=target_x,
        y=target_y,
        epsg_code=int(epsg_code),
        dem_source=dem_source,
    )
    _progress("reading GUNW radar-grid LOS vectors", progress)
    heights, x_radar, y_radar, los_x, los_y, los_z = _read_radar_los(path)
    incidence = compute_local_incidence(
        dem_grid,
        los_x,
        los_y,
        los_z,
        heights,
        x_radar,
        y_radar,
        epsg_code=int(epsg_code),
        vertical_correction_m=vertical_correction_m,
        require_vertical_datum_match=require_vertical_datum_match,
        dem_source=dem_source,
        geometry_chunks=geometry_chunks,
        progress=progress,
    )
    source_metadata = _DEM_SOURCE_METADATA[dem_source]
    local_source_paths = {
        "height_above_ellipsoid": f"{RADAR_GRID_GROUP}/heightAboveEllipsoid",
        "los_unit_vector_x": f"{RADAR_GRID_GROUP}/losUnitVectorX",
        "los_unit_vector_y": f"{RADAR_GRID_GROUP}/losUnitVectorY",
        "x_coordinates": f"{RADAR_GRID_GROUP}/xCoordinates",
        "y_coordinates": f"{RADAR_GRID_GROUP}/yCoordinates",
    }
    incidence.attrs.update(
        {
            "incidence_angle_source": (
                "DEM elevation, NISAR radar-grid heightAboveEllipsoid, "
                "LOS unit vectors, and target-grid geometry"
            ),
            "incidence_angle_origin": "terrain_local",
            "incidence_angle_source_datasets": json.dumps(
                local_source_paths, sort_keys=True
            ),
            "incidence_angle_source_units": (
                "DEM elevation and heightAboveEllipsoid in metres; "
                "LOS components dimensionless; projected x/y coordinates in metres"
            ),
            "incidence_angle_los_z_handling": (
                "read from losUnitVectorZ when present; otherwise derived from "
                "losUnitVectorX and losUnitVectorY"
            ),
            "incidence_angle_algorithm": ("snowin.io.geometry.compute_local_incidence"),
            "incidence_angle_reference": "local",
            "gunw_height_reference": "WGS84 ellipsoid",
            "dem_source": dem_source,
            "dem_product": source_metadata["product"],
            "dem_vertical_datum": source_metadata["vertical_datum"],
            "dem_height_reference": source_metadata["height_reference"],
            "vertical_datum_transform": incidence.attrs.get(
                "vertical_correction_definition", "not applied"
            ),
            "vertical_datum_status": incidence.attrs.get(
                "vertical_datum_status", "unknown"
            ),
            "vertical_correction_source": incidence.attrs.get(
                "vertical_correction_source", "none"
            ),
            "coordinate_orientation": "GUNW projected x/y phase-grid coordinates",
            "dem_input": str(dem_input)
            if not isinstance(dem_input, xr.DataArray)
            else "xarray.DataArray",
            "incidence_angle_resampling": (
                "DEM already aligned with the GUNW phase grid; no resampling"
                if incidence.attrs.get("dem_grid_alignment") == "already_aligned"
                else "DEM bilinearly reprojected to the GUNW phase grid"
            ),
        }
    )
    return incidence.rename("incidence_angle")


def add_gunw_incidence(
    target: xr.Dataset,
    gunw_file: str | Path,
    **kwargs: Any,
) -> xr.Dataset:
    """Compute incidence and append it to ``target`` in place.

    ``open_gunw`` attaches a close callback to its Dataset to retain ownership
    of the lazy NISAR file handle. Mutating that owner preserves the callback;
    callers should use the returned Dataset (which is the same object).
    """
    progress = kwargs.get("progress", True)
    _progress("starting explicit GUNW incidence calculation", progress)
    incidence = compute_gunw_incidence(gunw_file, target, **kwargs)
    _require_aligned(target["phase"], incidence)
    # Caller-created pairs follow the same precision contract as open_gunw.
    # Mutate the owner to preserve its lazy file-resource close callback.
    for name, variable in target.data_vars.items():
        if name != "spatial_ref" and variable.dtype.kind == "f":
            target[name] = as_science_float(variable)
    target["phase"] = as_science_float(target["phase"])
    target["incidence_angle"] = incidence
    target["incidence_angle"].attrs = _serializable_attrs(incidence.attrs)
    geometry_valid = (
        np.isfinite(incidence) & (incidence >= 0.0) & (incidence < math.pi / 2.0)
    ).rename("geometry_valid")
    geometry_valid.attrs = {
        "units": "1",
        "long_name": "valid incidence geometry support",
        "definition": "incidence_angle is finite and in [0, pi/2)",
        "incidence_angle_reference": incidence.attrs.get(
            "incidence_angle_reference", "unknown"
        ),
    }
    target["geometry_valid"] = geometry_valid
    target.attrs["snowin_data_state"] = "retrieval_ready_pair"
    target.attrs.update(
        {
            key: value
            for key, value in _serializable_attrs(incidence.attrs).items()
            if key not in {"units", "long_name", "definition"}
        }
    )
    target.attrs["incidence_angle_status"] = "computed"
    if incidence.attrs.get("incidence_angle_reference") == "local":
        target.attrs["incidence_angle_reference"] = "local terrain surface"
    target.attrs["incidence_angle_source"] = incidence.attrs.get(
        "incidence_angle_source", "explicit GUNW incidence calculation"
    )
    paths = target.attrs.get("source_dataset_paths")
    if paths is not None:
        try:
            source_paths = json.loads(str(paths))
            if incidence.attrs.get("incidence_angle_origin") == "product_ellipsoid":
                source_paths["incidence_angle"] = incidence.attrs[
                    "incidence_angle_source_dataset_path"
                ]
            elif incidence.attrs.get("incidence_angle_source_datasets"):
                geometry_paths = json.loads(
                    incidence.attrs["incidence_angle_source_datasets"]
                )
                source_paths.update(
                    {
                        f"incidence_geometry_{name}": path
                        for name, path in geometry_paths.items()
                    }
                )
            target.attrs["source_dataset_paths"] = json.dumps(
                source_paths, sort_keys=True
            )
        except (TypeError, json.JSONDecodeError):
            pass
    _progress("incidence_angle appended to SnowIn dataset", progress)
    return target


__all__ = [
    "NISAR_GUNW_PHASE_TRANSFORM",
    "NISAR_GUNW_SOURCE_PHASE_DEFINITION",
    "add_gunw_incidence",
    "compute_gunw_incidence",
    "normalize_gunw_pair",
    "open_gunw",
    "read_gunw_wavelength_m",
]
