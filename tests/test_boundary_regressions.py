"""Small regression tests for scientific workflow boundaries."""

from __future__ import annotations

import math

import numpy as np
import pytest
import xarray as xr

from snowin import accumulate_dswe, compute_leinss_dswe, reference_phase


def _pair() -> xr.Dataset:
    phase = xr.DataArray(
        [[2.0]],
        dims=("y", "x"),
        coords={"y": [0.0], "x": [0.0]},
        name="phase",
        attrs={
            "units": "rad",
            "phase_difference_definition": "secondary_minus_reference",
        },
    )
    return xr.Dataset(
        {"phase": phase},
        attrs={
            "phase_difference_definition": "secondary_minus_reference",
            "reference_time": "2025-01-01T00:00:00Z",
            "secondary_time": "2025-01-13T00:00:00Z",
            "temporal_edge": "reference_to_secondary",
        },
    )


def _incidence(degrees: float) -> xr.DataArray:
    return xr.DataArray(
        [[math.radians(degrees)]],
        dims=("y", "x"),
        coords={"y": [0.0], "x": [0.0]},
        name="incidence_angle",
        attrs={"units": "rad", "incidence_angle_reference": "local"},
    )


def test_phase_sign_and_reference_offset_sign_are_not_silent():
    positive = reference_phase(_pair(), method="manual_offset", offset_rad=0.5)
    negative = reference_phase(_pair(), method="manual_offset", offset_rad=-0.5)

    assert positive.phase_referenced.item() == pytest.approx(1.5)
    assert negative.phase_referenced.item() == pytest.approx(2.5)
    assert positive.attrs["phase_reference_offset_rad"] == pytest.approx(0.5)
    assert negative.attrs["phase_reference_offset_rad"] == pytest.approx(-0.5)


def test_explicit_wavelength_is_used_by_the_xarray_kernel():
    result = compute_leinss_dswe(
        _pair().phase,
        _incidence(35.0),
        wavelength_m=0.238403545,
    )

    assert result.attrs["wavelength_m"] == pytest.approx(0.238403545)
    assert result.attrs["units"] == "m"


@pytest.mark.parametrize("degrees", [90.0, 100.0])
def test_incidence_at_or_above_ninety_degrees_is_unsupported(degrees):
    with pytest.raises(ValueError, match=r"\[0, pi/2\)"):
        compute_leinss_dswe(
            _pair().phase, _incidence(degrees), wavelength_m=0.238403545
        )


def test_reference_metadata_preserves_exclusion_class():
    observed = xr.DataArray([1.0, 3.0], dims=("station",), attrs={"units": "rad"})
    expected = xr.DataArray([0.0, 0.0], dims=("station",), attrs={"units": "rad"})
    weights = xr.DataArray([1.0, 1.0], dims=("station",), attrs={"units": "1"})
    ids = xr.DataArray(["380:CO:SNTL", "737:CO:SNTL"], dims=("station",))
    reasons = xr.DataArray(
        ["eligible", "heldout_input_gate_or_corrected_window_invalid"],
        dims=("station",),
    )

    result = reference_phase(
        _pair(),
        observed,
        expected,
        weights,
        contributor_id=ids,
        exclusion_reason=reasons,
    )

    assert result.attrs["phase_reference_eligible_count"] == 1
    assert result.reference_eligible.values.tolist() == [True, False]
    assert result.reference_exclusion_reason.values.tolist() == [
        "eligible",
        "heldout_input_gate_or_corrected_window_invalid",
    ]
    assert result.attrs["phase_reference_provenance"]


def test_temporal_missing_support_is_propagated_not_zero_filled():
    dswe = xr.DataArray(
        [[1.0, np.nan]],
        dims=("y", "x"),
        attrs={"units": "m", "quantity": "pairwise_dSWE"},
    )
    edge = xr.Dataset(
        {"dswe": dswe},
        attrs={
            "reference_time": "2025-01-01T00:00:00Z",
            "secondary_time": "2025-01-13T00:00:00Z",
            "temporal_edge": "reference_to_secondary",
        },
    )

    result = accumulate_dswe([edge])

    assert np.isfinite(result.cumulative_dswe.values[0, 0, 0])
    assert np.isnan(result.cumulative_dswe.values[0, 0, 1])
    assert not bool(result.temporal_path_supported.values[0, 0, 1])
    assert result.attrs["missing_support_policy"].startswith("propagate_missing")
