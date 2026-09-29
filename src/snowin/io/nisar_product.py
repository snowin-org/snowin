"""NISAR GUNW to SnowIn normalized-Dataset adapter using nisar_pytools.

This module is the product boundary for NISAR GUNW semantics. The generic
scientific kernel in :mod:`snowin.snow.dswe` receives only normalized phase
and geometry; it does not know NISAR source conventions.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Literal

import numpy as np
import xarray as xr

from ._nisar_hdf5 import (
    IDENTIFICATION_GROUP,
    RADAR_GRID_GROUP,
    _open_group,
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
    compute_cop30_local_incidence,
)
from .phase_normalization import (
    _CANONICAL_PHASE_DEFINITION,
    NISAR_GUNW_PHASE_TRANSFORM,
    NISAR_GUNW_SOURCE_PHASE_DEFINITION,
    _iso_utc,
    _normalize_source_phase,
    _positive_scalar,
    _require_2d,
    _require_aligned,
    _serializable_attrs,
    normalize_gunw_pair,
)

SPEED_OF_LIGHT_M_S = 299_792_458.0
"""Defined speed of light used to convert product center frequency to metres."""

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
    if center_frequency is None or attrs.get("units") not in {"hertz", "Hz"}:
        raise ValueError(
            f"GUNW center-frequency metadata is missing or has unknown units at {path}"
        )
    frequency_hz = _positive_scalar("center_frequency_hz", center_frequency)
    return SPEED_OF_LIGHT_M_S / frequency_hz


def _grid_data(
    data_array: xr.DataArray,
    source_dataset: xr.Dataset,
    *,
    name: str,
) -> xr.DataArray:
    if data_array.ndim != 2:
        raise ValueError(f"{name} must be two-dimensional, got {data_array.dims}")
    if "yCoordinates" not in source_dataset or "xCoordinates" not in source_dataset:
        raise ValueError(f"{name} source group is missing xCoordinates/yCoordinates")
    y = source_dataset["yCoordinates"].load().data
    x = source_dataset["xCoordinates"].load().data
    return xr.DataArray(
        data_array.data,
        dims=("y", "x"),
        coords={"y": y, "x": x},
        attrs=_serializable_attrs(data_array.attrs),
        name=name,
    )


def _radar_grid_slice(
    data_array: xr.DataArray,
    source_dataset: xr.Dataset,
    *,
    radar_cube_index: int,
) -> xr.DataArray:
    if data_array.ndim != 3:
        raise ValueError(f"incidenceAngle must be a height cube, got {data_array.dims}")
    height_dim = data_array.dims[0]
    if radar_cube_index < 0 or radar_cube_index >= data_array.sizes[height_dim]:
        raise IndexError(
            f"radar_cube_index={radar_cube_index} is outside the height cube"
        )
    return _grid_data(
        data_array.isel({height_dim: radar_cube_index}),
        source_dataset,
        name="incidence_angle",
    )


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
        from nisar_pytools.utils.metadata import get_gunw
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
        layer = get_gunw(
            tree,
            polarization=polarization,
            layer="unwrappedInterferogram",
            frequency=frequency,
            valid_mask=False,
        )
        if not isinstance(layer, xr.Dataset):
            raise TypeError("nisar_pytools.get_gunw did not return an xarray Dataset")
        return tree, layer, polarization
    except Exception:
        # nisar_pytools owns the HDF5 handle through a DataTree finalizer.
        # Dropping this reference releases it on exceptional open paths.
        del tree
        raise


def _nisar_acquisition_time(tree: Any, role: Literal["reference", "secondary"]) -> str:
    """Read acquisition times from the upstream tree metadata helper."""
    from nisar_pytools.utils.metadata import get_acquisition_time

    times = get_acquisition_time(tree)
    value = getattr(times, role)
    if value is None or str(value) in {"NaT", ""}:
        raise ValueError(f"GUNW is missing required {role} acquisition time metadata")
    return _iso_utc(value.to_pydatetime(), f"{role}_time")


def open_gunw(
    gunw_file: str | Path,
    *,
    wavelength_m: float | None = None,
    polarization: str | None = None,
    frequency: str = "frequencyA",
    chunks: dict[str, int] | str | None = "auto",
    progress: bool = True,
) -> xr.Dataset:
    """Open and normalize a NISAR GUNW without computing incidence geometry.

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
        raw_phase.attrs["units"] = raw_phase.attrs.get("units", "").lower()
        if raw_phase.attrs["units"] not in {"radians", "radian", "rad"}:
            raise ValueError("GUNW unwrappedPhase has missing or unknown angle units")

        additional: dict[str, xr.DataArray] = {}
        for source_name, normalized_name in {
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
                if normalized_name in {"ionosphere", "ionosphere_unc"}:
                    layer_attrs["correction_status"] = "available_not_applied"
                additional[normalized_name] = xr.DataArray(
                    variable.data,
                    dims=("y", "x"),
                    coords={
                        "y": raw_phase.coords["y"],
                        "x": raw_phase.coords["x"],
                    },
                    attrs=layer_attrs,
                    name=normalized_name,
                )

        radar_grid_path = "science/LSAR/GUNW/metadata/radarGrid"
        try:
            radar_grid = tree[radar_grid_path].to_dataset()
        except KeyError:
            radar_grid = None
        if radar_grid is not None:
            for source_name, normalized_name in {
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
                additional[normalized_name] = xr.DataArray(
                    variable.data,
                    dims=dimensions,
                    coords=coords,
                    attrs=layer_attrs,
                    name=normalized_name,
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
        source_provenance = {
            "source_dataset_paths": json.dumps(source_paths, sort_keys=True),
            "source_reader": "nisar_pytools.open_nisar + SnowIn normalization",
            "wavelength_source": (
                "explicit wavelength_m override"
                if wavelength_m is not None
                else "NISAR GUNW centerFrequency metadata via c/f"
            ),
            "incidence_angle_status": "not_computed",
        }
        canonical_phase, phase_transform = _normalize_source_phase(
            raw_phase, NISAR_GUNW_SOURCE_PHASE_DEFINITION
        )
        attrs: dict[str, Any] = {
            "snowin_schema_version": "0.1-draft",
            "product_kind": "pairwise_interferogram",
            "reference_time": _nisar_acquisition_time(tree, "reference"),
            "secondary_time": _nisar_acquisition_time(tree, "secondary"),
            "temporal_edge": "reference_to_secondary",
            "phase_difference_definition": _CANONICAL_PHASE_DEFINITION,
            "source_phase_difference_definition": NISAR_GUNW_SOURCE_PHASE_DEFINITION,
            "phase_transform": phase_transform,
            "wavelength_m": (
                _positive_scalar("wavelength_m", wavelength_m)
                if wavelength_m is not None
                else read_gunw_wavelength_m(path, frequency=frequency)
            ),
            "source_product_type": "NISAR_GUNW",
            "source_reader": "nisar_pytools.open_nisar + SnowIn normalization",
            "correction_layers_applied": False,
        }
        if granule_id is not None:
            attrs["source_granule_id"] = str(granule_id)
        attrs.update(source_provenance)
        variables: dict[str, xr.DataArray] = {"phase": canonical_phase}
        for name, variable in additional.items():
            copied = variable.rename(name)
            copied.attrs = _serializable_attrs(variable.attrs)
            copied.attrs.setdefault("grid_mapping", "spatial_ref")
            variables[name] = copied
        result = xr.Dataset(
            variables,
            coords={
                "y": raw_phase.coords["y"],
                "x": raw_phase.coords["x"],
                "spatial_ref": spatial_ref,
            },
            attrs=attrs,
        )
        result["x"].attrs.setdefault("units", "m")
        result["y"].attrs.setdefault("units", "m")
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
    not acquire or cache ancillary elevation data. The returned two-dimensional
    DataArray is aligned to ``target.phase``; :func:`add_gunw_incidence`
    appends it to the target Dataset.
    """
    if not isinstance(target, xr.Dataset) or "phase" not in target:
        raise TypeError("target must be an xarray.Dataset containing 'phase'")
    _require_2d("phase", target["phase"])
    path = Path(gunw_file).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"GUNW file not found: {path}")
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
    radar_group = RADAR_GRID_GROUP

    if incidence_source == "product_ellipsoid":
        _progress("opening GUNW ellipsoid incidence field", progress)
        radar_ds = _open_group(path, radar_group, chunks=chunks)
        try:
            if "incidenceAngle" not in radar_ds:
                raise ValueError(f"GUNW incidenceAngle is missing at {radar_group}")
            raw_incidence = _radar_grid_slice(
                radar_ds["incidenceAngle"],
                radar_ds,
                radar_cube_index=radar_cube_index,
            )
            source_incidence_units = raw_incidence.attrs.get("units")
            if source_incidence_units not in _KNOWN_SOURCE_ANGLE_UNITS:
                raise ValueError(
                    "GUNW incidenceAngle has missing or unknown source angle units; "
                    "expected degrees metadata"
                )
            incidence = raw_incidence * (math.pi / 180.0)
            incidence.attrs = _serializable_attrs(raw_incidence.attrs)
            incidence.attrs.update(
                {
                    "units": "rad",
                    "incidence_angle_reference": "ellipsoid",
                    "source_units": source_incidence_units,
                    "source_variable": "incidenceAngle",
                }
            )
            phase = target["phase"]
            if np.array_equal(
                incidence.coords["x"].data, phase.coords["x"].data
            ) and np.array_equal(incidence.coords["y"].data, phase.coords["y"].data):
                incidence = incidence.assign_coords(
                    x=phase.coords["x"], y=phase.coords["y"]
                )
            else:
                incidence = incidence.interp_like(phase, method=incidence_resampling)
            incidence.attrs.update(
                {
                    "incidence_angle_source": "NISAR GUNW radarGrid ellipsoid incidenceAngle",
                    "incidence_angle_resampling": incidence_resampling,
                    "incidence_angle_radar_cube_index": radar_cube_index,
                }
            )
            # Geometry is intentionally materialized before the temporary
            # radar-grid file handle is closed.
            incidence = incidence.load()
        finally:
            radar_ds.close()
        return incidence.rename("incidence_angle")

    _progress("preparing DEM for local incidence", progress)
    target_x = np.asarray(target.coords["x"].data, dtype=float)
    target_y = np.asarray(target.coords["y"].data, dtype=float)
    if dem is None or (isinstance(dem, str) and dem == "auto"):
        raise ValueError(
            "local incidence requires a caller-supplied prepared DEM path or "
            "xarray.DataArray; SnowIn does not download DEMs"
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
    incidence = compute_cop30_local_incidence(
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
    incidence.attrs.update(
        {
            "incidence_angle_source": f"{source_metadata['label']} plus NISAR GUNW radar-grid LOS",
            "incidence_angle_algorithm": (
                "snowin.io.geometry.compute_cop30_local_incidence"
            ),
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
                f"{source_metadata['label']} bilinear reprojection to GUNW phase grid"
            ),
        }
    )
    return incidence.rename("incidence_angle")


def add_gunw_incidence(
    target: xr.Dataset,
    gunw_file: str | Path,
    **kwargs: Any,
) -> xr.Dataset:
    """Compute incidence for ``gunw_file`` and append it to ``target``."""
    progress = kwargs.get("progress", True)
    _progress("starting explicit GUNW incidence calculation", progress)
    incidence = compute_gunw_incidence(gunw_file, target, **kwargs)
    _require_aligned(target["phase"], incidence)
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
            source_paths["incidence_angle"] = f"{RADAR_GRID_GROUP}/incidenceAngle"
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
    "SPEED_OF_LIGHT_M_S",
    "add_gunw_incidence",
    "compute_gunw_incidence",
    "normalize_gunw_pair",
    "open_gunw",
    "read_gunw_wavelength_m",
]
