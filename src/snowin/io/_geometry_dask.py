"""Private Dask execution helpers for opt-in geometry chunking."""

from __future__ import annotations

import numpy as np


def _normalize_geometry_chunks(
    geometry_chunks: int | tuple[int, int], shape: tuple[int, int]
) -> tuple[int, int]:
    """Validate a two-dimensional chunk shape for prototype geometry work."""
    if isinstance(geometry_chunks, bool):
        raise TypeError("geometry_chunks must be an integer or a (y, x) pair")
    if isinstance(geometry_chunks, int):
        chunks = (geometry_chunks, geometry_chunks)
    elif isinstance(geometry_chunks, tuple) and len(geometry_chunks) == 2:
        chunks = geometry_chunks
    else:
        raise TypeError("geometry_chunks must be an integer or a (y, x) pair")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in chunks):
        raise TypeError("geometry_chunks values must be positive integers")
    if any(value <= 0 for value in chunks):
        raise ValueError("geometry_chunks values must be positive integers")
    return tuple(min(value, size) for value, size in zip(chunks, shape))


def _build_los_interpolators(
    sorted_height: np.ndarray,
    sorted_y: np.ndarray,
    sorted_x: np.ndarray,
    arrays: tuple[np.ndarray, np.ndarray, np.ndarray],
):
    """Build reusable SciPy interpolators inside one Dask graph task."""
    from scipy.interpolate import RegularGridInterpolator

    return tuple(
        RegularGridInterpolator(
            (sorted_height, sorted_y, sorted_x),
            values,
            bounds_error=False,
            fill_value=np.nan,
        )
        for values in arrays
    )


def _interpolate_incidence_chunk(
    elevation: np.ndarray,
    normal_x: np.ndarray,
    normal_y: np.ndarray,
    normal_z: np.ndarray,
    y: np.ndarray,
    x: np.ndarray,
    interpolators,
) -> np.ndarray:
    """Evaluate one incidence chunk for the optional Dask geometry path."""
    yy, xx = np.meshgrid(y, x, indexing="ij")
    points = np.column_stack((elevation.ravel(), yy.ravel(), xx.ravel()))
    interpolated = [interpolator(points) for interpolator in interpolators]
    with np.errstate(invalid="ignore", divide="ignore"):
        dot = np.clip(
            interpolated[0].reshape(elevation.shape) * normal_x
            + interpolated[1].reshape(elevation.shape) * normal_y
            + interpolated[2].reshape(elevation.shape) * normal_z,
            -1.0,
            1.0,
        )
        angle = np.where(dot > 0.0, np.arccos(dot), np.nan)
    return angle.astype("float32")


def _dask_incidence_array(
    elevation: np.ndarray,
    normal_x: np.ndarray,
    normal_y: np.ndarray,
    normal_z: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    *,
    chunk_shape: tuple[int, int],
    sorted_height: np.ndarray,
    sorted_y: np.ndarray,
    sorted_x: np.ndarray,
    arrays: tuple[np.ndarray, np.ndarray, np.ndarray],
):
    """Build a chunked incidence array without a full-grid point cloud."""
    try:
        import dask.array as da
        from dask import delayed
    except ImportError as exc:
        raise ImportError(
            "geometry_chunks requires optional Dask; install SnowIn with the "
            "'dask' extra or omit geometry_chunks"
        ) from exc

    interpolators = delayed(_build_los_interpolators)(
        sorted_height, sorted_y, sorted_x, arrays
    )
    row_arrays = []
    for row_start in range(0, elevation.shape[0], chunk_shape[0]):
        row_end = min(row_start + chunk_shape[0], elevation.shape[0])
        column_arrays = []
        for column_start in range(0, elevation.shape[1], chunk_shape[1]):
            column_end = min(column_start + chunk_shape[1], elevation.shape[1])
            chunk = delayed(_interpolate_incidence_chunk)(
                elevation[row_start:row_end, column_start:column_end],
                normal_x[row_start:row_end, column_start:column_end],
                normal_y[row_start:row_end, column_start:column_end],
                normal_z[row_start:row_end, column_start:column_end],
                y[row_start:row_end],
                x[column_start:column_end],
                interpolators,
            )
            column_arrays.append(
                da.from_delayed(
                    chunk,
                    shape=(row_end - row_start, column_end - column_start),
                    dtype=np.float32,
                )
            )
        row_arrays.append(da.concatenate(column_arrays, axis=1))
    return da.concatenate(row_arrays, axis=0)
