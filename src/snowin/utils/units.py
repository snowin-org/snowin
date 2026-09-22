"""Unit conversion and validation helpers."""

from __future__ import annotations

import math
import warnings

import numpy as np


def angle_to_radians_if_needed(
    arr,
    *,
    unit: str | None = None,
    name: str = "angle",
) -> tuple[np.ndarray, str]:
    """Return angle values in radians plus the unit interpretation used.

    If ``unit`` is supplied, it is authoritative. If ``unit='auto'`` or None,
    values with median greater than pi/2 are treated as degrees. This inference
    is returned in metadata and emits a warning so workflows can record it.
    """
    values = np.asarray(arr, dtype=float)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        raise ValueError(f"{name} has no finite values.")

    unit_norm = "auto" if unit is None else unit.lower()
    if unit_norm in {"rad", "radian", "radians"}:
        out = values
        used = "radians"
    elif unit_norm in {"deg", "degree", "degrees"}:
        out = np.deg2rad(values)
        used = "degrees"
    elif unit_norm == "auto":
        median = float(np.nanmedian(finite))
        if median > math.pi / 2:
            warnings.warn(
                f"{name} appears to be in degrees; converting to radians.",
                RuntimeWarning,
                stacklevel=2,
            )
            out = np.deg2rad(values)
            used = "degrees_inferred"
        else:
            warnings.warn(
                f"{name} appears to be in radians; leaving unchanged.",
                RuntimeWarning,
                stacklevel=2,
            )
            out = values
            used = "radians_inferred"
    else:
        raise ValueError("unit must be one of None, 'auto', 'radians', or 'degrees'.")

    finite_out = out[np.isfinite(out)]
    if np.any((finite_out < 0) | (finite_out >= math.pi / 2)):
        raise ValueError(f"{name} must be in [0, pi/2) radians after conversion.")
    return out, used
