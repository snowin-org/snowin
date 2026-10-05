"""Canonical precision for science values, independent of coordinate precision."""

import numpy as np
import xarray as xr

SCIENCE_FLOAT_DTYPE = np.dtype("float32")


def as_science_float(value: xr.DataArray) -> xr.DataArray:
    """Convert real science values without casting coordinates or computing Dask.

    Domain and metadata validation belong to the calling scientific boundary.
    Reject non-real storage rather than silently parsing strings or discarding
    imaginary components. Boolean/integer scientific inputs remain supported.
    """
    if value.dtype.kind not in "biuf":
        raise TypeError(
            f"{value.name or 'science array'} must contain real numeric values"
        )
    return value.astype(SCIENCE_FLOAT_DTYPE, copy=False, keep_attrs=True)
