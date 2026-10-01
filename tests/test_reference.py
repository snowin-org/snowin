"""Tests for the xarray-native reference-phase API."""

from __future__ import annotations

import numpy as np
import pytest
import xarray as xr

from snowin import reference_phase
from snowin.reference import (
    MANUAL_OFFSET_METHOD,
    MEAN_OFFSET_METHOD,
    MEDIAN_OFFSET_METHOD,
    SINGLE_STATION_METHOD,
)


def _pair() -> xr.Dataset:
    phase = xr.DataArray(
        [[2.0, np.nan], [-1.0, 4.0]],
        dims=("y", "x"),
        coords={"y": [100.0, 80.0], "x": [10.0, 20.0]},
        name="phase",
        attrs={
            "units": "rad",
            "phase_difference_definition": "secondary_minus_reference",
        },
    )
    return xr.Dataset(
        {"phase": phase},
        coords={"spatial_ref": xr.DataArray(0)},
        attrs={"phase_difference_definition": "secondary_minus_reference"},
    )


def _contributors(
    observed: list[float], expected: list[float], weights: list[float]
) -> tuple[xr.DataArray, xr.DataArray, xr.DataArray, xr.DataArray]:
    coords = {"station": ["a", "b", "c"][: len(observed)]}
    attrs = {"units": "rad"}
    return (
        xr.DataArray(observed, dims=("station",), coords=coords, attrs=attrs),
        xr.DataArray(expected, dims=("station",), coords=coords, attrs=attrs),
        xr.DataArray(
            weights,
            dims=("station",),
            coords=coords,
            attrs={"units": "1"},
        ),
        xr.DataArray(
            coords["station"], dims=("station",), coords=coords, name="station_id"
        ),
    )


def test_zero_reference_offset_preserves_phase_and_metadata():
    observed, expected, weights, ids = _contributors([1.0, 2.0], [1.0, 2.0], [0.2, 0.8])
    result = reference_phase(_pair(), observed, expected, weights, contributor_id=ids)
    np.testing.assert_allclose(
        result.phase_referenced.values, result.phase.values, equal_nan=True
    )
    assert result.attrs["phase_reference_offset_rad"] == pytest.approx(0.0)
    assert bool(result.reference_estimate_supported) is True
    assert result.phase_referenced.dims == ("y", "x")
    np.testing.assert_array_equal(result.phase_referenced.coords["y"], [100.0, 80.0])
    np.testing.assert_array_equal(result.phase_referenced.coords["x"], [10.0, 20.0])
    assert result.phase_referenced.attrs["units"] == "rad"
    assert result.reference_contributor_id.dims == ("reference_contributor",)
    assert result.reference_contributor_id.values.tolist() == ["a", "b"]


@pytest.mark.parametrize("offset", [0.75, -0.75])
def test_known_positive_and_negative_reference_offsets_are_subtracted(offset):
    observed, expected, weights, ids = _contributors(
        [1.0 + offset, 2.0 + offset, 3.0 + offset],
        [1.0, 2.0, 3.0],
        [0.2, 0.5, 0.8],
    )
    result = reference_phase(_pair(), observed, expected, weights, contributor_id=ids)
    assert result.attrs["phase_reference_offset_rad"] == pytest.approx(offset)
    np.testing.assert_allclose(
        result.phase_referenced.values,
        result.phase.values - offset,
        equal_nan=True,
    )


def test_colorado_frozen_coherence_weighted_algebra_is_characterized():
    observed, expected, weights, ids = _contributors(
        [1.75, 2.75, 3.75], [1.0, 2.0, 3.0], [0.2, 0.5, 0.8]
    )
    result = reference_phase(_pair(), observed, expected, weights, contributor_id=ids)
    assert result.attrs["phase_reference_method"] == (
        "coherence_weighted_additive_offset"
    )
    assert result.attrs["phase_reference_offset_rad"] == pytest.approx(0.75)
    assert result.attrs["phase_reference_eligible_count"] == 3
    assert result.attrs["phase_reference_status"] == "SUPPORTED"
    assert result.reference_weighted_contribution.attrs["units"] == "rad"


def test_manual_offset_is_supported_without_contributors():
    result = reference_phase(
        _pair(),
        method=MANUAL_OFFSET_METHOD,
        offset_rad=0.5,
    )
    assert result.attrs["phase_reference_method"] == MANUAL_OFFSET_METHOD
    assert result.attrs["phase_reference_status"] == "SUPPORTED_MANUAL"
    assert bool(result.reference_estimate_supported) is True
    np.testing.assert_allclose(
        result.phase_referenced.values,
        result.phase.values - 0.5,
        equal_nan=True,
    )


def test_manual_offset_requires_a_finite_value():
    with pytest.raises(ValueError, match="finite offset_rad"):
        reference_phase(_pair(), method=MANUAL_OFFSET_METHOD)


def test_single_station_uses_one_residual_and_rejects_multiple():
    observed, expected, weights, ids = _contributors([1.75], [1.0], [0.8])
    result = reference_phase(
        _pair(),
        observed,
        expected,
        weights,
        contributor_id=ids,
        method=SINGLE_STATION_METHOD,
    )
    assert result.attrs["phase_reference_offset_rad"] == pytest.approx(0.75)

    observed, expected, weights, ids = _contributors(
        [1.75, 2.75], [1.0, 2.0], [0.8, 0.8]
    )
    result = reference_phase(
        _pair(),
        observed,
        expected,
        weights,
        contributor_id=ids,
        method=SINGLE_STATION_METHOD,
    )
    assert bool(result.reference_estimate_supported) is False
    assert result.attrs["phase_reference_status"] == (
        "UNSUPPORTED_SINGLE_STATION_REQUIRES_ONE_ELIGIBLE_CONTRIBUTOR"
    )


def test_multiple_station_mean_is_unweighted():
    observed, expected, weights, ids = _contributors(
        [1.0, 2.0, 4.0], [0.0, 1.0, 2.0], [0.1, 0.1, 100.0]
    )
    result = reference_phase(
        _pair(),
        observed,
        expected,
        weights,
        contributor_id=ids,
        method=MEAN_OFFSET_METHOD,
    )
    assert result.attrs["phase_reference_offset_rad"] == pytest.approx(4.0 / 3.0)


def test_multiple_station_median_is_robust():
    observed, expected, weights, ids = _contributors(
        [1.0, 2.0, 100.0], [0.0, 1.0, 2.0], [1.0, 1.0, 1.0]
    )
    result = reference_phase(
        _pair(),
        observed,
        expected,
        weights,
        contributor_id=ids,
        method=MEDIAN_OFFSET_METHOD,
    )
    assert result.attrs["phase_reference_offset_rad"] == pytest.approx(1.0)


def test_explicit_exclusion_reason_removes_contributor_from_support():
    observed, expected, weights, ids = _contributors([1.0, 3.0], [0.0, 0.0], [1.0, 1.0])
    reasons = xr.DataArray(
        ["eligible", "station_not_available"],
        dims=("station",),
        coords=observed.coords,
    )
    result = reference_phase(
        _pair(),
        observed,
        expected,
        weights,
        contributor_id=ids,
        exclusion_reason=reasons,
    )
    assert result.attrs["phase_reference_offset_rad"] == pytest.approx(1.0)
    assert result.reference_eligible.values.tolist() == [True, False]


def test_missing_contributors_are_excluded_and_recorded():
    observed, expected, weights, ids = _contributors(
        [1.0, np.nan, 3.0], [1.0, 2.0, 3.0], [1.0, 1.0, 0.0]
    )
    result = reference_phase(_pair(), observed, expected, weights, contributor_id=ids)
    assert result.attrs["phase_reference_eligible_count"] == 1
    assert result.reference_eligible.values.tolist() == [True, False, False]
    assert result.reference_exclusion_reason.values.tolist() == [
        "eligible",
        "observed_phase_nonfinite",
        "weight_nonpositive",
    ]


def test_reference_exclusions_never_mark_invalid_contributors_eligible():
    coords = {"station": ["a", "b", "c", "d"]}
    attrs = {"units": "rad"}
    observed = xr.DataArray(
        [np.nan, 2.0, 3.0, 4.0], dims=("station",), coords=coords, attrs=attrs
    )
    expected = xr.DataArray(
        [0.0, np.nan, 2.0, 3.0], dims=("station",), coords=coords, attrs=attrs
    )
    weights = xr.DataArray([1.0, 1.0, np.nan, 1.0], dims=("station",), coords=coords)
    ids = xr.DataArray(["a", "b", "c", "d"], dims=("station",), coords=coords)
    caller_reasons = xr.DataArray(
        ["caller_excluded", "eligible", "eligible", "eligible"],
        dims=("station",),
        coords=observed.coords,
    )
    result = reference_phase(
        _pair(),
        observed,
        expected,
        weights,
        contributor_id=ids,
        exclusion_reason=caller_reasons,
    )

    assert result.reference_eligible.values.tolist() == [False, False, False, True]
    assert result.reference_exclusion_reason.values.tolist() == [
        "caller_excluded",
        "expected_phase_nonfinite",
        "weight_nonfinite",
        "eligible",
    ]
    assert result.reference_caller_exclusion_reason.values.tolist() == [
        "caller_excluded",
        "eligible",
        "eligible",
        "eligible",
    ]


def test_insufficient_reference_support_produces_missing_referenced_phase():
    observed, expected, weights, ids = _contributors(
        [np.nan, 2.0], [1.0, 2.0], [0.0, np.nan]
    )
    result = reference_phase(_pair(), observed, expected, weights, contributor_id=ids)
    assert bool(result.reference_estimate_supported) is False
    assert result.attrs["phase_reference_status"] == (
        "UNSUPPORTED_NO_ELIGIBLE_CONTRIBUTORS"
    )
    assert np.isnan(result.phase_referenced.values).all()


def test_reference_requires_explicit_radian_metadata():
    observed, expected, weights, ids = _contributors([1.0], [1.0], [1.0])
    observed.attrs = {}
    with pytest.raises(ValueError, match="declare radians"):
        reference_phase(_pair(), observed, expected, weights, contributor_id=ids)


def test_dask_backed_phase_remains_lazy_and_equivalent():
    pytest.importorskip("dask.array")
    observed, expected, weights, ids = _contributors(
        [1.5, 2.5], [1.0, 2.0], [0.25, 0.75]
    )
    pair = _pair()
    pair["phase"] = pair.phase.chunk({"y": 1, "x": 1})
    result = reference_phase(pair, observed, expected, weights, contributor_id=ids)
    assert hasattr(result.phase_referenced.data, "chunks")
    np.testing.assert_allclose(
        result.phase_referenced.compute().values,
        [[1.5, np.nan], [-1.5, 3.5]],
        equal_nan=True,
    )
