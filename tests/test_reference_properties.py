"""Property checks for coherence-weighted phase-offset estimation."""

from __future__ import annotations

import hypothesis.strategies as st
import numpy as np
import pytest
import xarray as xr
from hypothesis import given, settings

from snowin.reference import estimate_reference_offset


@settings(max_examples=60, derandomize=True, deadline=None)
@given(
    residuals=st.lists(
        st.floats(min_value=-3.0, max_value=3.0, allow_nan=False),
        min_size=1,
        max_size=8,
    ),
    weights=st.lists(
        st.floats(min_value=0.01, max_value=1.0, allow_nan=False),
        min_size=1,
        max_size=8,
    ),
    common_shift=st.floats(min_value=-2.0, max_value=2.0, allow_nan=False),
)
def test_weighted_reference_offset_matches_independent_weighted_residual(
    residuals, weights, common_shift
):
    count = min(len(residuals), len(weights))
    residuals = np.asarray(residuals[:count], dtype=np.float64)
    weights = np.asarray(weights[:count], dtype=np.float64)
    expected_offset = np.sum(weights * residuals) / np.sum(weights)
    coords = {"station": np.arange(count)}
    observed = xr.DataArray(
        residuals + 1.25,
        dims=("station",),
        coords=coords,
        attrs={
            "units": "rad",
            "phase_difference_definition": "reference_minus_secondary",
        },
    )
    expected = xr.DataArray(
        np.full(count, 1.25),
        dims=("station",),
        coords=coords,
        attrs={
            "units": "rad",
            "phase_difference_definition": "reference_minus_secondary",
        },
    )
    weight = xr.DataArray(
        weights,
        dims=("station",),
        coords=coords,
        attrs={"units": "1"},
    )
    shifted_observed = xr.DataArray(
        observed.values + common_shift,
        dims=observed.dims,
        coords=observed.coords,
        attrs=dict(observed.attrs),
    )

    estimate = estimate_reference_offset(observed, expected, weight)
    shifted_estimate = estimate_reference_offset(
        shifted_observed,
        expected,
        weight,
    )

    assert estimate.reference_offset_rad.item() == pytest.approx(
        expected_offset, rel=2e-13, abs=2e-15
    )
    assert shifted_estimate.reference_offset_rad.item() == pytest.approx(
        expected_offset + common_shift,
        rel=2e-13,
        abs=2e-15,
    )
    assert estimate.attrs["reference_offset_units"] == "rad"
