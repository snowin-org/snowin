"""Array conversion and validation helpers."""

from __future__ import annotations

import numpy as np

AMPLITUDE_DB_EPS = 1e-12


def dataarray_to_numpy(
    da,
    *,
    magnitude: bool = False,
    angle: bool = False,
    db: bool = False,
) -> np.ndarray:
    """Convert an xarray-like object to a NumPy array with optional transforms.

    Parameters are mutually composable for common SAR products: ``magnitude``
    extracts complex magnitude, ``angle`` extracts complex phase angle, and
    ``db`` converts a positive magnitude to decibels using 20 log10.
    """
    if da is None:
        raise ValueError("da must not be None.")
    arr = np.asarray(da.values if hasattr(da, "values") else da)
    while arr.ndim > 2:
        arr = np.squeeze(arr)
        if arr.ndim > 2:
            arr = arr[0]
    if arr.ndim == 0:
        arr = arr.reshape((1, 1))
    elif arr.ndim == 1:
        arr = arr.reshape((1, arr.size))
    if arr.ndim != 2:
        raise ValueError(f"Expected a 2-D array after squeezing, got shape {arr.shape}.")

    if angle:
        arr = np.angle(arr)
    elif magnitude:
        arr = np.abs(arr)
    else:
        arr = arr.astype(float, copy=False) if not np.iscomplexobj(arr) else np.abs(arr)

    if db:
        arr = 20.0 * np.log10(np.maximum(np.asarray(arr, dtype=float), AMPLITUDE_DB_EPS))
    return np.asarray(arr, dtype=float)


def validate_same_shape(*arrays: np.ndarray | None) -> tuple[int, ...]:
    """Validate that all non-None arrays have the same shape and return it."""
    shapes = [np.shape(arr) for arr in arrays if arr is not None]
    if not shapes:
        raise ValueError("At least one array is required.")
    first = shapes[0]
    for shape in shapes[1:]:
        if shape != first:
            raise ValueError(f"Array shapes differ: {shapes}")
    return first


def finite_fraction(arr: np.ndarray | None) -> float:
    """Return the fraction of finite pixels in an array."""
    if arr is None:
        return float("nan")
    arr = np.asarray(arr)
    if arr.size == 0:
        return float("nan")
    return float(np.isfinite(arr).sum() / arr.size)
