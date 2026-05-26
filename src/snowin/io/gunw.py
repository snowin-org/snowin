"""Low-level readers and metadata helpers for NISAR GUNW products."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import re

import h5py
import numpy as np
import xarray as xr


@dataclass(frozen=True)
class GunwAcquisitionTimes:
    """Reference/secondary acquisition timing parsed from a GUNW filename."""

    ref_start: datetime | None
    ref_end: datetime | None
    sec_start: datetime | None
    sec_end: datetime | None
    days_between: float | None


@dataclass(frozen=True)
class GunwLayers:
    """Standardized NISAR GUNW layers and product metadata.

    Missing layers are represented explicitly as ``None``. This avoids
    silently changing downstream behavior when a product lacks a layer.
    """

    gunw_file: Path
    polarization: str
    layers: dict[str, xr.DataArray | None]
    metadata: dict[str, Any]
    dataset_attr_paths: dict[str, str]


STANDARD_GUNW_LAYER_NAMES: tuple[str, ...] = (
    "unwrapped_phase",
    "coherence_unw",
    "coherence_wrapped",
    "connected_components",
    "mask",
    "ionosphere",
    "ionosphere_unc",
    "wet_tropo",
    "hydro_tropo",
    "incidence_angle",
    "wrapped_ifg",
    "corr_peak",
)


UNWRAPPED_GROUP_TEMPLATE = (
    "/science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/{pol}"
)
WRAPPED_GROUP_TEMPLATE = (
    "/science/LSAR/GUNW/grids/frequencyA/wrappedInterferogram/{pol}"
)
PIXEL_OFFSET_GROUP_TEMPLATE = "/science/LSAR/GUNW/grids/frequencyA/pixelOffsets/{pol}"
UNWRAPPED_MASK_GROUP = "/science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram"
RADAR_GRID_GROUP = "/science/LSAR/GUNW/metadata/radarGrid"
IDENTIFICATION_GROUP = "/science/LSAR/identification"


def decode_hdf5_scalar(value: Any) -> Any:
    """Decode common scalar/list values returned by h5py."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, np.bytes_):
        return value.tobytes().decode("utf-8", errors="replace")
    if isinstance(value, np.ndarray):
        if value.shape == ():
            return decode_hdf5_scalar(value.item())
        if value.dtype.kind in {"S", "U"}:
            flat = value.flatten()
            if flat.size == 1:
                return decode_hdf5_scalar(flat[0])
            return [decode_hdf5_scalar(v) for v in flat]
        return value.tolist()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def read_scalar_hdf5(nc_file: str | Path, dataset_path: str) -> Any:
    """Read one scalar HDF5/netCDF value, returning ``None`` if absent."""
    nc_file = Path(nc_file)
    with h5py.File(nc_file, "r") as h5:
        if dataset_path not in h5:
            return None
        value = h5[dataset_path][()]
    return decode_hdf5_scalar(value)


def read_attrs_hdf5(nc_file: str | Path, dataset_path: str) -> dict[str, Any]:
    """Read attributes for a dataset/group, returning an empty dict if absent."""
    nc_file = Path(nc_file)
    with h5py.File(nc_file, "r") as h5:
        if dataset_path not in h5:
            return {}
        return {
            key: decode_hdf5_scalar(val) for key, val in h5[dataset_path].attrs.items()
        }


def open_group_dataset(nc_file: str | Path, group: str, var_name: str) -> xr.DataArray:
    """Open and load one variable from a NISAR GUNW HDF5 group."""
    ds = xr.open_dataset(
        nc_file,
        group=group,
        engine="h5netcdf",
        phony_dims="sort",
    )
    try:
        if var_name not in ds:
            raise KeyError(
                f"{var_name} not found in {group}; found {list(ds.data_vars)}"
            )
        da = ds[var_name].load()
    finally:
        ds.close()
    return da


def detect_pol(nc_file: str | Path) -> str:
    """Detect the first available HH/VV polarization in a GUNW product."""
    for pol in ("HH", "VV"):
        group = UNWRAPPED_GROUP_TEMPLATE.format(pol=pol)
        try:
            _ = open_group_dataset(nc_file, group, "unwrappedPhase")
            return pol
        except Exception:
            continue
    raise RuntimeError(
        "Could not detect HH or VV polarization in unwrappedInterferogram."
    )


def squeeze_2d(da: xr.DataArray) -> xr.DataArray:
    """Squeeze and select leading slices until an array is 2-D."""
    da = da.squeeze()
    while da.ndim > 2:
        da = da.isel({da.dims[0]: 0})
    if da.ndim != 2:
        raise ValueError(f"Expected 2-D array, got dims={da.dims}, shape={da.shape}")
    return da


def attach_xy_coords(da: xr.DataArray, group: str, nc_file: str | Path) -> xr.DataArray:
    """Attach x/y coordinates from the GUNW group to a 2-D DataArray."""
    ds_coords = xr.open_dataset(
        nc_file,
        group=group,
        engine="h5netcdf",
        phony_dims="sort",
    )
    try:
        x = ds_coords["xCoordinates"].load()
        y = ds_coords["yCoordinates"].load()
    finally:
        ds_coords.close()

    da = squeeze_2d(da)
    return da.assign_coords({da.dims[1]: x.values, da.dims[0]: y.values})


def read_2d(nc_file: str | Path, group: str, var_name: str) -> xr.DataArray:
    """Read a geocoded 2-D GUNW layer with x/y coordinates attached."""
    da = open_group_dataset(nc_file, group, var_name)
    return attach_xy_coords(da, group, nc_file)


def read_radar_grid_slice(
    nc_file: str | Path,
    group: str,
    var_name: str,
    radar_cube_index: int = 0,
) -> xr.DataArray:
    """Read one height slice from a 3-D radar-grid metadata cube."""
    ds = xr.open_dataset(
        nc_file,
        group=group,
        engine="h5netcdf",
        phony_dims="sort",
    )
    try:
        if var_name not in ds:
            raise KeyError(
                f"{var_name} not found in {group}; found {list(ds.data_vars)}"
            )
        da = ds[var_name]
        if da.ndim != 3:
            raise ValueError(
                f"{var_name} expected 3-D cube, got dims={da.dims}, shape={da.shape}"
            )

        cube_dim = da.dims[0]
        if radar_cube_index < 0 or radar_cube_index >= da.sizes[cube_dim]:
            raise IndexError(
                f"radar_cube_index={radar_cube_index} out of range for "
                f"{var_name} with size {da.sizes[cube_dim]}"
            )
        da = da.isel({cube_dim: radar_cube_index}).load()
        x = ds["xCoordinates"].load()
        y = ds["yCoordinates"].load()
    finally:
        ds.close()

    if da.ndim != 2:
        raise ValueError(f"{var_name} slice is not 2-D after slicing; got {da.shape}")
    return da.assign_coords({da.dims[1]: x.values, da.dims[0]: y.values})


def try_read(nc_file: str | Path, group: str, var_name: str) -> xr.DataArray | None:
    """Read a 2-D layer, returning ``None`` if it is absent or unreadable."""
    try:
        return read_2d(nc_file, group, var_name)
    except Exception:
        return None


def try_read_radar_grid(
    nc_file: str | Path,
    group: str,
    var_name: str,
    radar_cube_index: int,
) -> xr.DataArray | None:
    """Read a radar-grid layer, returning ``None`` if it is absent or unreadable."""
    try:
        return read_radar_grid_slice(
            nc_file,
            group,
            var_name,
            radar_cube_index=radar_cube_index,
        )
    except Exception:
        return None


def parse_epsg_value(value: Any) -> int | None:
    """Best-effort EPSG parser for HDF5 scalar/attribute values."""
    value = decode_hdf5_scalar(value)
    if value is None:
        return None
    if isinstance(value, list) and value:
        return parse_epsg_value(value[0])
    if isinstance(value, np.integer | int):
        ivalue = int(value)
        return ivalue if 1000 <= ivalue <= 999999 else None
    if isinstance(value, np.floating | float):
        ivalue = int(value)
        return (
            ivalue
            if np.isfinite(value)
            and abs(float(value) - ivalue) < 1e-6
            and 1000 <= ivalue <= 999999
            else None
        )
    if isinstance(value, str):
        for hit in re.findall(r"\d{4,6}", value):
            ivalue = int(hit)
            if 1000 <= ivalue <= 999999:
                return ivalue
    return None


def detect_grid_epsg(nc_file: str | Path) -> int | None:
    """Best-effort detection of the projected CRS EPSG used by GUNW x/y grids."""
    candidates = [
        "/science/LSAR/GUNW/grids/frequencyA/projection",
        "/science/LSAR/GUNW/grids/frequencyA/epsg",
        "/science/LSAR/GUNW/grids/frequencyA/epsgCode",
        "/science/LSAR/GUNW/metadata/geolocationGrid/projection",
        "/science/LSAR/GUNW/metadata/radarGrid/projection",
    ]
    attr_names = {
        "epsg",
        "EPSG",
        "epsgCode",
        "epsg_code",
        "projection",
        "spatial_ref",
        "crs_wkt",
    }
    with h5py.File(nc_file, "r") as h5:
        for path in candidates:
            if path in h5:
                epsg = parse_epsg_value(h5[path][()])
                if epsg is not None:
                    return epsg
                for value in h5[path].attrs.values():
                    epsg = parse_epsg_value(value)
                    if epsg is not None:
                        return epsg

        found: int | None = None

        def visitor(_name: str, obj: Any) -> None:
            nonlocal found
            if found is not None:
                return
            for key, value in obj.attrs.items():
                key_l = str(key).lower()
                if (
                    key in attr_names
                    or "epsg" in key_l
                    or "projection" in key_l
                    or "spatial" in key_l
                ):
                    epsg = parse_epsg_value(value)
                    if epsg is not None:
                        found = epsg
                        return

        h5.visititems(visitor)
        return found


def parse_acquisition_times_from_filename(path: str | Path) -> GunwAcquisitionTimes:
    """Parse the four acquisition timestamps embedded in a NISAR GUNW filename."""
    path = Path(path)
    hits = re.findall(r"\d{8}T\d{6}", path.name)
    if len(hits) < 4:
        return GunwAcquisitionTimes(None, None, None, None, None)

    ref_start = datetime.strptime(hits[0], "%Y%m%dT%H%M%S")
    ref_end = datetime.strptime(hits[1], "%Y%m%dT%H%M%S")
    sec_start = datetime.strptime(hits[2], "%Y%m%dT%H%M%S")
    sec_end = datetime.strptime(hits[3], "%Y%m%dT%H%M%S")
    days_between = (sec_start - ref_start).total_seconds() / 86400.0
    return GunwAcquisitionTimes(ref_start, ref_end, sec_start, sec_end, days_between)


def read_identification_metadata(nc_file: str | Path) -> dict[str, Any]:
    """Read common GUNW identification metadata fields."""
    fields = {
        "referenceAbsoluteOrbitNumber": f"{IDENTIFICATION_GROUP}/referenceAbsoluteOrbitNumber",
        "secondaryAbsoluteOrbitNumber": f"{IDENTIFICATION_GROUP}/secondaryAbsoluteOrbitNumber",
        "referenceIsJointObservation": f"{IDENTIFICATION_GROUP}/referenceIsJointObservation",
        "secondaryIsJointObservation": f"{IDENTIFICATION_GROUP}/secondaryIsJointObservation",
        "trackNumber": f"{IDENTIFICATION_GROUP}/trackNumber",
        "frameNumber": f"{IDENTIFICATION_GROUP}/frameNumber",
        "missionId": f"{IDENTIFICATION_GROUP}/missionId",
        "processingCenter": f"{IDENTIFICATION_GROUP}/processingCenter",
        "productType": f"{IDENTIFICATION_GROUP}/productType",
        "granuleId": f"{IDENTIFICATION_GROUP}/granuleId",
        "productDoi": f"{IDENTIFICATION_GROUP}/productDoi",
        "productVersion": f"{IDENTIFICATION_GROUP}/productVersion",
        "productSpecificationVersion": f"{IDENTIFICATION_GROUP}/productSpecificationVersion",
        "lookDirection": f"{IDENTIFICATION_GROUP}/lookDirection",
    }
    return {key: read_scalar_hdf5(nc_file, path) for key, path in fields.items()}


def build_layers(
    gunw_file: str | Path,
    pol: str,
    radar_cube_index: int = 0,
) -> tuple[dict[str, xr.DataArray | None], dict[str, str]]:
    """Read the standard diagnostic GUNW layers used by ``plot_gunw``."""
    unw_group = UNWRAPPED_GROUP_TEMPLATE.format(pol=pol)
    wrap_group = WRAPPED_GROUP_TEMPLATE.format(pol=pol)
    off_group = PIXEL_OFFSET_GROUP_TEMPLATE.format(pol=pol)

    layers = {
        "unwrapped_phase": try_read(gunw_file, unw_group, "unwrappedPhase"),
        "coherence_unw": try_read(gunw_file, unw_group, "coherenceMagnitude"),
        "ionosphere": try_read(gunw_file, unw_group, "ionospherePhaseScreen"),
        "ionosphere_unc": try_read(
            gunw_file, unw_group, "ionospherePhaseScreenUncertainty"
        ),
        "connected_components": try_read(gunw_file, unw_group, "connectedComponents"),
        "wrapped_ifg": try_read(gunw_file, wrap_group, "wrappedInterferogram"),
        "coherence_wrapped": try_read(gunw_file, wrap_group, "coherenceMagnitude"),
        "along_track_offset": try_read(gunw_file, off_group, "alongTrackOffset"),
        "slant_range_offset": try_read(gunw_file, off_group, "slantRangeOffset"),
        "corr_peak": try_read(gunw_file, off_group, "correlationSurfacePeak"),
        "mask": try_read(gunw_file, UNWRAPPED_MASK_GROUP, "mask"),
        "incidence_angle": try_read_radar_grid(
            gunw_file, RADAR_GRID_GROUP, "incidenceAngle", radar_cube_index
        ),
        "parallel_baseline": try_read_radar_grid(
            gunw_file, RADAR_GRID_GROUP, "parallelBaseline", radar_cube_index
        ),
        "perpendicular_baseline": try_read_radar_grid(
            gunw_file, RADAR_GRID_GROUP, "perpendicularBaseline", radar_cube_index
        ),
        "reference_slant_range": try_read_radar_grid(
            gunw_file, RADAR_GRID_GROUP, "referenceSlantRange", radar_cube_index
        ),
        "hydro_tropo": try_read_radar_grid(
            gunw_file,
            RADAR_GRID_GROUP,
            "hydrostaticTroposphericPhaseScreen",
            radar_cube_index,
        ),
        "wet_tropo": try_read_radar_grid(
            gunw_file, RADAR_GRID_GROUP, "wetTroposphericPhaseScreen", radar_cube_index
        ),
    }

    dataset_attr_paths = {
        "unwrapped_phase": f"{unw_group}/unwrappedPhase",
        "coherence_unw": f"{unw_group}/coherenceMagnitude",
        "ionosphere": f"{unw_group}/ionospherePhaseScreen",
        "ionosphere_unc": f"{unw_group}/ionospherePhaseScreenUncertainty",
        "connected_components": f"{unw_group}/connectedComponents",
        "wrapped_ifg": f"{wrap_group}/wrappedInterferogram",
        "coherence_wrapped": f"{wrap_group}/coherenceMagnitude",
        "along_track_offset": f"{off_group}/alongTrackOffset",
        "slant_range_offset": f"{off_group}/slantRangeOffset",
        "corr_peak": f"{off_group}/correlationSurfacePeak",
        "mask": f"{UNWRAPPED_MASK_GROUP}/mask",
        "incidence_angle": f"{RADAR_GRID_GROUP}/incidenceAngle",
        "parallel_baseline": f"{RADAR_GRID_GROUP}/parallelBaseline",
        "perpendicular_baseline": f"{RADAR_GRID_GROUP}/perpendicularBaseline",
        "reference_slant_range": f"{RADAR_GRID_GROUP}/referenceSlantRange",
        "hydro_tropo": f"{RADAR_GRID_GROUP}/hydrostaticTroposphericPhaseScreen",
        "wet_tropo": f"{RADAR_GRID_GROUP}/wetTroposphericPhaseScreen",
    }
    return layers, dataset_attr_paths


def read_gunw_layers(
    gunw_file: str | Path,
    pol: str | None = None,
    layers: list[str] | tuple[str, ...] | None = None,
    radar_cube_index: int = 0,
) -> GunwLayers:
    """Read standardized NISAR GUNW layers without plotting or transforms.

    Parameters
    ----------
    gunw_file
        Local path to a NISAR GUNW ``.nc`` product.
    pol
        Optional polarization override. If omitted, HH then VV are detected.
    layers
        Optional subset of standardized layer names to return. Missing requested
        layers are included with value ``None``.
    radar_cube_index
        Height index for radar-grid metadata cubes such as incidence angle and
        tropospheric screens.

    Returns
    -------
    GunwLayers
        Dataclass containing layer arrays, product metadata, and HDF5 dataset
        paths used for attribute lookup.
    """
    gunw_path = Path(gunw_file).expanduser().resolve()
    if not gunw_path.exists():
        raise FileNotFoundError(f"GUNW file not found: {gunw_path}")

    pol_resolved = pol or detect_pol(gunw_path)
    if pol_resolved not in {"HH", "VV"}:
        raise ValueError("pol must be one of 'HH', 'VV', or None.")

    all_layers, dataset_attr_paths = build_layers(
        gunw_path, pol_resolved, radar_cube_index=radar_cube_index
    )

    requested = tuple(layers) if layers is not None else STANDARD_GUNW_LAYER_NAMES
    unknown = sorted(set(requested) - set(all_layers))
    if unknown:
        raise ValueError(
            "Unknown GUNW layer name(s): "
            + ", ".join(unknown)
            + ". Valid names include: "
            + ", ".join(sorted(all_layers))
        )

    selected = {name: all_layers.get(name) for name in requested}
    selected_paths = {
        name: dataset_attr_paths[name]
        for name in requested
        if name in dataset_attr_paths
    }

    metadata = read_identification_metadata(gunw_path)
    times = parse_acquisition_times_from_filename(gunw_path)
    metadata.update(
        {
            "gunw_file": str(gunw_path),
            "gunw_name": gunw_path.name,
            "polarization": pol_resolved,
            "ref_start": times.ref_start,
            "ref_end": times.ref_end,
            "sec_start": times.sec_start,
            "sec_end": times.sec_end,
            "days_between": times.days_between,
        }
    )

    return GunwLayers(
        gunw_file=gunw_path,
        polarization=pol_resolved,
        layers=selected,
        metadata=metadata,
        dataset_attr_paths=selected_paths,
    )
