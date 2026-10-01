"""Private raw HDF5 access for the NISAR product adapter."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any

import numpy as np

RADAR_GRID_GROUP = "/science/LSAR/GUNW/metadata/radarGrid"
IDENTIFICATION_GROUP = "/science/LSAR/identification"


def _require_h5py():
    try:
        return import_module("h5py")
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise ImportError(
            "NISAR HDF5 access requires SnowIn's optional 'nisar' extra"
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


def _read_radar_grid_incidence(
    gunw_file: str | Path, *, radar_cube_index: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    """Read one native ellipsoid-incidence plane and its projected grid."""
    h5py = _require_h5py()
    with h5py.File(gunw_file, "r") as h5:
        group = h5[RADAR_GRID_GROUP]
        if "incidenceAngle" not in group:
            raise ValueError(f"GUNW incidenceAngle is missing at {RADAR_GRID_GROUP}")
        source = group["incidenceAngle"]
        if source.ndim != 3:
            raise ValueError(
                f"incidenceAngle must be a height cube, got {source.shape}"
            )
        if radar_cube_index < 0 or radar_cube_index >= source.shape[0]:
            raise IndexError(
                f"radar_cube_index={radar_cube_index} is outside the height cube"
            )
        if "xCoordinates" not in group or "yCoordinates" not in group:
            raise ValueError(
                "GUNW radar grid is missing xCoordinates/yCoordinates at "
                f"{RADAR_GRID_GROUP}"
            )
        x = np.asarray(group["xCoordinates"][...], dtype=float)
        y = np.asarray(group["yCoordinates"][...], dtype=float)
        values = np.asarray(source[radar_cube_index, ...], dtype=float)
        if values.shape != (y.size, x.size):
            raise ValueError(
                "GUNW incidenceAngle plane shape does not match radar-grid coordinates"
            )
        attrs = {key: decode_hdf5_scalar(value) for key, value in source.attrs.items()}
    return values, x, y, attrs
