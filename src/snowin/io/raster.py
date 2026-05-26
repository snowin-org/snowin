"""Raster export helpers with explicit grid assumptions."""

from __future__ import annotations

from pathlib import Path

import numpy as np


def infer_affine_from_xy(x, y):
    """Infer a rasterio affine transform from 1-D x/y cell-center coordinates."""
    try:
        from rasterio.transform import Affine
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError("infer_affine_from_xy requires rasterio.") from exc

    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)
    if x_arr.ndim != 1 or y_arr.ndim != 1:
        raise ValueError("x and y must be 1-D coordinate arrays.")
    if x_arr.size < 2 or y_arr.size < 2:
        raise ValueError("x and y must each contain at least two coordinates.")

    dxs = np.diff(x_arr)
    dys = np.diff(y_arr)
    if not np.allclose(dxs, dxs[0]):
        raise ValueError("x coordinates are not regularly spaced.")
    if not np.allclose(dys, dys[0]):
        raise ValueError("y coordinates are not regularly spaced.")

    dx = float(dxs[0])
    dy_step = float(dys[0])
    west = float(x_arr[0] - dx / 2.0)

    if dy_step < 0:
        # north-up: first row has highest y.
        north = float(y_arr[0] - dy_step / 2.0)
        dy = dy_step
    else:
        # y is south-to-north, but raster rows are top-to-bottom. The caller
        # must flip the array before writing, or choose coordinates matching the
        # array row order. We still return an affine matching row order.
        north = float(y_arr[0] - dy_step / 2.0)
        dy = dy_step

    return Affine.translation(west, north) * Affine.scale(dx, dy)


def write_geotiff(
    path,
    arr,
    x,
    y,
    epsg: int,
    *,
    nodata=np.nan,
) -> Path:
    """Write a single-band GeoTIFF from an array and 1-D x/y coordinates."""
    try:
        import rasterio
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError("write_geotiff requires rasterio.") from exc

    data = np.asarray(arr, dtype="float32")
    x_arr = np.asarray(x)
    y_arr = np.asarray(y)
    if data.ndim != 2:
        raise ValueError("arr must be 2-D.")
    if data.shape != (y_arr.size, x_arr.size):
        raise ValueError(
            f"arr shape {data.shape} does not match y/x sizes {(y_arr.size, x_arr.size)}."
        )

    transform = infer_affine_from_xy(x_arr, y_arr)
    out = Path(path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        out,
        "w",
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype="float32",
        crs=f"EPSG:{epsg}",
        transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(data, 1)
    return out


def write_cog_later_optional(*args, **kwargs):
    """Placeholder for future COG export after GeoTIFF behavior is tested."""
    raise NotImplementedError("COG export is reserved for a later tested implementation.")
