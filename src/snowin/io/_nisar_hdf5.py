"""Private raw HDF5 access for the NISAR product adapter."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

RADAR_GRID_GROUP = "/science/LSAR/GUNW/metadata/radarGrid"
IDENTIFICATION_GROUP = "/science/LSAR/identification"


def _require_h5py():
    try:
        return import_module("h5py")
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise ImportError(
            "NISAR HDF5 access requires SnowIn's optional 'nisar' extra"
        ) from exc


def _require_h5netcdf():
    try:
        return import_module("h5netcdf")
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise ImportError(
            "NISAR GUNW reading requires SnowIn's optional 'nisar' extra"
        ) from exc


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
    h5py = _require_h5py()
    with h5py.File(nc_file, "r") as h5:
        if dataset_path not in h5:
            return None
        value = h5[dataset_path][()]
    return decode_hdf5_scalar(value)


def read_attrs_hdf5(nc_file: str | Path, dataset_path: str) -> dict[str, Any]:
    """Read attributes for a dataset/group, returning an empty dict if absent."""
    nc_file = Path(nc_file)
    h5py = _require_h5py()
    with h5py.File(nc_file, "r") as h5:
        if dataset_path not in h5:
            return {}
        return {
            key: decode_hdf5_scalar(val) for key, val in h5[dataset_path].attrs.items()
        }


def _read_radar_los(gunw_file: Path) -> tuple[np.ndarray, ...]:
    import h5py

    with h5py.File(gunw_file, "r") as h5:
        group = h5[RADAR_GRID_GROUP]
        required = (
            "heightAboveEllipsoid",
            "xCoordinates",
            "yCoordinates",
            "losUnitVectorX",
            "losUnitVectorY",
        )
        missing = [name for name in required if name not in group]
        if missing:
            raise ValueError(
                f"GUNW radar grid is missing LOS datasets: {', '.join(missing)}"
            )
        heights = np.asarray(group["heightAboveEllipsoid"][...], dtype=float)
        x_radar = np.asarray(group["xCoordinates"][...], dtype=float)
        y_radar = np.asarray(group["yCoordinates"][...], dtype=float)
        los_x = np.asarray(group["losUnitVectorX"][...], dtype=float)
        los_y = np.asarray(group["losUnitVectorY"][...], dtype=float)
        if "losUnitVectorZ" in group:
            los_z = np.asarray(group["losUnitVectorZ"][...], dtype=float)
        else:
            horizontal_squared = los_x**2 + los_y**2
            if np.any(horizontal_squared > 1.0 + 1e-6):
                raise ValueError(
                    "GUNW is missing losUnitVectorZ and its X/Y vectors cannot "
                    "define a real unit-vector Z component"
                )
            los_z = np.sqrt(np.maximum(1.0 - horizontal_squared, 0.0))
    return heights, x_radar, y_radar, los_x, los_y, los_z


def _open_group(
    gunw_file: Path,
    group: str,
    *,
    chunks: dict[str, int] | str | None,
) -> xr.Dataset:
    _require_h5netcdf()
    kwargs: dict[str, Any] = {
        "group": group,
        "engine": "h5netcdf",
        "phony_dims": "sort",
        "decode_cf": True,
        "mask_and_scale": True,
    }
    if chunks is not None:
        kwargs["chunks"] = chunks
    try:
        return xr.open_dataset(gunw_file, **kwargs)
    except (ImportError, ValueError) as exc:
        if chunks is not None and "dask" in str(exc).lower():
            raise ImportError(
                "lazy GUNW opening requires optional Dask; pass chunks=None for "
                "eager opening or install SnowIn with the 'dask' extra"
            ) from exc
        raise
