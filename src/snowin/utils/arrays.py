"""Array conversion and validation helpers."""

from __future__ import annotations

import numpy as np


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
