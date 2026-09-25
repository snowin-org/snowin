"""Scientific and xarray-contract tests for the Stage 2 dSWE kernel."""

from __future__ import annotations

import inspect
import json
import math
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

import snowin
from snowin.snow import compute_dswe

WAVELENGTH_M = 0.238403545


def _inputs(
    phase_data: float | np.ndarray = 1.0,
    incidence_data: float | np.ndarray = math.radians(35.0),
    *,
    dims: tuple[str, ...] = (),
    coords: dict[str, np.ndarray] | None = None,
    phase_units: str | None = "rad",
    incidence_units: str | None = "rad",
    incidence_reference: str | None = "local",
) -> tuple[xr.DataArray, xr.DataArray]:
    phase_attrs = {
        "units": phase_units,
        "phase_kind": "unwrapped_interferometric_phase",
        "grid_mapping": "spatial_ref",
        "phase_difference_definition": "secondary_minus_reference",
    }
    incidence_attrs = {
        "units": incidence_units,
        "incidence_angle_reference": incidence_reference,
        "grid_mapping": "spatial_ref",
    }
    phase = xr.DataArray(
        phase_data,
        dims=dims,
        coords=coords,
        attrs=phase_attrs,
        name="phase",
    )
    incidence = xr.DataArray(
        incidence_data,
        dims=dims,
        coords=coords,
        attrs=incidence_attrs,
        name="incidence_angle",
    )
    return phase, incidence


def test_compute_dswe_has_no_phase_sign_switch_or_method_selector():
    parameters = inspect.signature(compute_dswe).parameters
    assert "phase_sign" not in parameters
    assert "method" not in parameters
    assert parameters["wavelength_m"].default is inspect.Parameter.empty


def test_compute_dswe_is_available_from_top_level_and_snow_namespace():
    assert snowin.compute_dswe is compute_dswe


def test_zero_phase_gives_zero_dswe():
    phase, incidence = _inputs(phase_data=0.0)

    result = compute_dswe(phase, incidence, wavelength_m=WAVELENGTH_M)

    assert result.item() == pytest.approx(0.0)


@pytest.mark.parametrize("phase_value, expected_sign", [(1.0, 1), (-1.0, -1)])
def test_canonical_phase_sign_is_preserved(phase_value, expected_sign):
    phase, incidence = _inputs(phase_data=phase_value)

    result = compute_dswe(phase, incidence, wavelength_m=WAVELENGTH_M)

    assert np.sign(result.item()) == expected_sign


def test_known_scalar_calculation_matches_leinss_equation():
    phase_value = 0.75
    incidence_value = math.radians(35.0)
    phase, incidence = _inputs(
        phase_data=phase_value,
        incidence_data=incidence_value,
    )

    result = compute_dswe(phase, incidence, wavelength_m=WAVELENGTH_M)
    expected = (
        phase_value * WAVELENGTH_M / (2.0 * math.pi * (1.59 + incidence_value**2.5))
    )

    assert result.item() == pytest.approx(expected)
    assert result.item() == pytest.approx(0.01512359431622293)


def test_wavelength_dependence_is_linear():
    phase, incidence = _inputs()

    short = compute_dswe(phase, incidence, wavelength_m=0.10)
    long = compute_dswe(phase, incidence, wavelength_m=0.20)

    assert long.item() == pytest.approx(2.0 * short.item())


def test_incidence_angle_dependence_is_retained():
    phase_low, incidence_low = _inputs(incidence_data=0.0)
    phase_high, incidence_high = _inputs(incidence_data=math.radians(60.0))

    low = compute_dswe(phase_low, incidence_low, wavelength_m=WAVELENGTH_M)
    high = compute_dswe(phase_high, incidence_high, wavelength_m=WAVELENGTH_M)

    assert high.item() < low.item()


def test_nan_phase_and_incidence_propagate():
    phase, incidence = _inputs(
        phase_data=np.array([1.0, np.nan, 2.0]),
        incidence_data=np.array([math.radians(35.0), math.radians(35.0), np.nan]),
        dims=("pixel",),
    )

    result = compute_dswe(phase, incidence, wavelength_m=WAVELENGTH_M)

    assert np.isfinite(result[0])
    assert np.isnan(result[1])
    assert np.isnan(result[2])


def test_dimensions_coordinates_and_relevant_attrs_are_preserved():
    coords = {
        "y": np.array([4200.0, 4190.0]),
        "x": np.array([500000.0, 500010.0, 500020.0]),
    }
    phase, incidence = _inputs(
        phase_data=np.ones((2, 3)),
        incidence_data=np.full((2, 3), math.radians(35.0)),
        dims=("y", "x"),
        coords=coords,
    )
    phase.attrs["source_granule_id"] = "synthetic-granule"

    result = compute_dswe(phase, incidence, wavelength_m=WAVELENGTH_M)

    assert result.name == "dswe"
    assert result.dims == phase.dims
    assert result.sizes == phase.sizes
    for dim in phase.dims:
        assert result.coords[dim].equals(phase.coords[dim])
    assert result.attrs["source_granule_id"] == "synthetic-granule"
    assert result.attrs["units"] == "m"
    assert result.attrs["quantity"] == "pairwise_dSWE"
    assert result.attrs["phase_difference_definition"] == ("secondary_minus_reference")
    assert result.attrs["incidence_angle_reference"] == "local"
    assert result.attrs["wavelength_m"] == pytest.approx(WAVELENGTH_M)
    assert result.attrs["scientific_reference"] == "Leinss et al. (2015), Eq. 18"


@pytest.mark.parametrize("wavelength", [0.0, -1.0, np.nan, np.inf])
def test_invalid_wavelength_fails(wavelength):
    phase, incidence = _inputs()

    with pytest.raises((TypeError, ValueError), match="wavelength_m"):
        compute_dswe(phase, incidence, wavelength_m=wavelength)


def test_missing_or_non_radian_angle_units_fail_without_guessing():
    phase, incidence = _inputs(incidence_units="degrees")
    with pytest.raises(ValueError, match="invalid or ambiguous angle units"):
        compute_dswe(phase, incidence, wavelength_m=WAVELENGTH_M)

    phase, incidence = _inputs(incidence_units=None)
    with pytest.raises(ValueError, match="invalid or ambiguous angle units"):
        compute_dswe(phase, incidence, wavelength_m=WAVELENGTH_M)


def test_missing_incidence_reference_fails():
    phase, incidence = _inputs(incidence_reference=None)

    with pytest.raises(ValueError, match="incidence_angle_reference"):
        compute_dswe(phase, incidence, wavelength_m=WAVELENGTH_M)


def test_invalid_incidence_domain_fails_but_nan_is_allowed():
    phase, incidence = _inputs(incidence_data=math.pi / 2.0)

    with pytest.raises(ValueError, match=r"\[0, pi/2\)"):
        compute_dswe(phase, incidence, wavelength_m=WAVELENGTH_M)


def test_mismatched_coordinates_fail_instead_of_implicitly_aligning():
    phase, _ = _inputs(
        phase_data=np.ones(2),
        incidence_data=np.full(2, math.radians(35.0)),
        dims=("pixel",),
        coords={"pixel": np.array([0, 1])},
    )
    _, incidence = _inputs(
        phase_data=np.ones(2),
        incidence_data=np.full(2, math.radians(35.0)),
        dims=("pixel",),
        coords={"pixel": np.array([1, 2])},
    )

    with pytest.raises(ValueError, match="coordinates differ"):
        compute_dswe(phase, incidence, wavelength_m=WAVELENGTH_M)


def test_representative_l_band_wavelength_matches_equation():
    """Check the equation at a representative stock L-band wavelength."""

    phase, incidence = _inputs(
        phase_data=1.0,
        incidence_data=math.radians(40.0),
    )

    result = compute_dswe(phase, incidence, wavelength_m=0.238403545, alpha=1.0)
    expected = 0.238403545 / (2.0 * math.pi * (1.59 + math.radians(40.0) ** 2.5))

    assert result.item() == pytest.approx(expected)


def test_colorado_phase_lineage_fixture_is_explicit_and_opposite():
    fixture_path = Path(__file__).parent / "fixtures" / "colorado_phase_lineage.json"
    fixture = json.loads(fixture_path.read_text())
    raw_phase = xr.DataArray(
        np.asarray(fixture["raw_phase_rad"], dtype=float),
        dims=("y", "x"),
        attrs={
            "units": "rad",
            "phase_difference_definition": fixture["source_definition"],
        },
    )
    incidence = xr.DataArray(
        np.asarray(fixture["incidence_rad"], dtype=float),
        dims=("y", "x"),
        attrs={"units": "rad", "incidence_angle_reference": "local"},
    )

    normalized_phase = (-raw_phase).rename("phase")
    normalized_phase.attrs = {
        "units": "rad",
        "phase_difference_definition": fixture["snowin_definition"],
        "phase_transform": "multiply_by_-1",
    }
    downstream_phase = raw_phase.rename("phase")
    downstream_phase.attrs = {
        "units": "rad",
        "phase_difference_definition": fixture["snowin_definition"],
        "phase_sign": fixture["downstream_phase_sign"],
    }

    snowin_dswe = compute_dswe(
        normalized_phase,
        incidence,
        wavelength_m=fixture["wavelength_m"],
    )
    downstream_dswe = compute_dswe(
        downstream_phase,
        incidence,
        wavelength_m=fixture["wavelength_m"],
    )
    assert normalized_phase.attrs["phase_transform"] == "multiply_by_-1"
    assert downstream_phase.attrs["phase_sign"] == 1
    np.testing.assert_allclose(snowin_dswe.values, -downstream_dswe.values)


def test_dask_backed_inputs_remain_lazy_and_match_eager_result():
    da = pytest.importorskip("dask.array")

    phase_values = np.array([[0.0, 1.0], [-1.0, np.nan]])
    incidence_values = np.full((2, 2), math.radians(35.0))
    phase, incidence = _inputs(
        phase_data=da.from_array(phase_values, chunks=(1, 2)),
        incidence_data=da.from_array(incidence_values, chunks=(1, 2)),
        dims=("y", "x"),
        coords={"y": np.array([0, 1]), "x": np.array([10, 20])},
    )

    lazy_result = compute_dswe(phase, incidence, wavelength_m=WAVELENGTH_M)
    eager_result = compute_dswe(
        xr.DataArray(
            phase_values, dims=("y", "x"), coords=phase.coords, attrs=phase.attrs
        ),
        xr.DataArray(
            incidence_values,
            dims=("y", "x"),
            coords=incidence.coords,
            attrs=incidence.attrs,
        ),
        wavelength_m=WAVELENGTH_M,
    )

    assert isinstance(lazy_result.data, da.Array)
    xr.testing.assert_allclose(lazy_result.compute(), eager_result)
