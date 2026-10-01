"""Scientific and xarray-contract tests for named dSWE retrieval methods."""

from __future__ import annotations

import inspect
import math

import numpy as np
import pytest
import xarray as xr

import snowin
from snowin.snow import (
    compute_guneriussen_dswe,
    compute_leinss_dswe,
    compute_oveisgharan_dswe,
)

WAVELENGTH_M = 0.23840354572564613
THETA = math.radians(35.0)


def _inputs(
    phase_values: float | np.ndarray = 0.75,
    incidence_values: float | np.ndarray = THETA,
    *,
    dims: tuple[str, ...] = (),
    coords: dict[str, np.ndarray] | None = None,
) -> tuple[xr.DataArray, xr.DataArray]:
    phase = xr.DataArray(
        phase_values,
        dims=dims,
        coords=coords,
        attrs={
            "units": "rad",
            "phase_difference_definition": "secondary_minus_reference",
            "source_product": "synthetic-test",
        },
        name="phase",
    )
    incidence = xr.DataArray(
        incidence_values,
        dims=dims,
        coords=coords,
        attrs={"units": "rad", "incidence_angle_reference": "local"},
        name="incidence_angle",
    )
    return phase, incidence


def _run_guneriussen(phase, incidence, *, snow_density_kg_m3=300.0, **kwargs):
    return compute_guneriussen_dswe(
        phase,
        incidence,
        snow_density_kg_m3=snow_density_kg_m3,
        wavelength_m=WAVELENGTH_M,
        **kwargs,
    )


@pytest.mark.parametrize(
    "function, extra_kwargs",
    [
        (compute_leinss_dswe, {}),
        (compute_guneriussen_dswe, {"snow_density_kg_m3": 300.0}),
        (compute_oveisgharan_dswe, {}),
    ],
)
def test_named_methods_preserve_xarray_contract(function, extra_kwargs):
    coords = {"y": np.array([4200.0, 4190.0]), "x": np.array([500000.0, 500010.0])}
    phase, incidence = _inputs(
        np.full((2, 2), 0.75), np.full((2, 2), THETA), dims=("y", "x"), coords=coords
    )

    result = function(phase, incidence, wavelength_m=WAVELENGTH_M, **extra_kwargs)

    assert result.name == "dswe"
    assert result.dims == phase.dims
    assert result.sizes == phase.sizes
    assert result.coords.equals(phase.coords)
    assert result.attrs["units"] == "m"
    assert result.attrs["quantity"] == "pairwise_dSWE"
    assert result.attrs["source_product"] == "synthetic-test"
    assert result.attrs["phase_difference_definition"] == "secondary_minus_reference"
    assert result.attrs["incidence_angle_reference"] == "local"
    assert result.attrs["wavelength_m"] == pytest.approx(WAVELENGTH_M)
    assert result.attrs["retrieval_method"] in {"leinss", "guneriussen", "oveisgharan"}


def test_leinss_matches_published_equation():
    phase, incidence = _inputs()
    expected = 0.75 * WAVELENGTH_M / (2.0 * math.pi * (1.59 + THETA**2.5))

    named = compute_leinss_dswe(phase, incidence, wavelength_m=WAVELENGTH_M)
    assert named.item() == pytest.approx(expected)
    assert named.attrs["alpha"] == 1.0
    assert named.attrs["snow_path_constant"] == 1.59
    assert named.attrs["retrieval_method"] == "leinss"
    assert compute_leinss_dswe is snowin.compute_leinss_dswe


@pytest.mark.parametrize(
    "model, expected_permittivity",
    [
        ("guneriussen2001", 1.0 + 1.6 * 0.3 + 1.8 * 0.3**3),
        ("webb2021", 1.0 + 0.0014 * 300.0 + 2.0e-7 * 300.0**2),
        (
            "maetzler",
            1.0 + 1.5995 * 0.3 + 1.861 * 0.3**3,
        ),
    ],
)
def test_guneriussen_matches_density_and_permittivity_equation(
    model, expected_permittivity
):
    density_kg_m3 = 300.0
    snow_depth_change_m = 0.08
    refraction = math.cos(THETA) - math.sqrt(
        expected_permittivity - math.sin(THETA) ** 2
    )
    phase_value = (
        -2.0 * (2.0 * math.pi / WAVELENGTH_M) * refraction * snow_depth_change_m
    )
    phase, incidence = _inputs(phase_values=phase_value)

    result = _run_guneriussen(phase, incidence, permittivity_model=model)
    expected = snow_depth_change_m * (density_kg_m3 / 1000.0)

    assert result.item() == pytest.approx(expected)
    assert result.attrs["permittivity_model"] == model
    assert result.attrs["snow_density_kg_m3"] == 300.0
    assert result.attrs["water_density_kg_m3"] == 1000.0
    assert result.attrs["units"] == "m"
    assert result.attrs["quantity"] == "pairwise_dSWE"
    assert "snow_depth_change" in result.attrs["equation"]
    assert "Guneriussen et al. (2001)" in result.attrs["scientific_reference"]


def test_guneriussen_density_dataarray_is_aligned_and_not_mutated():
    coords = {"pixel": np.array([0, 1, 2])}
    phase, incidence = _inputs(
        np.ones(3), np.full(3, THETA), dims=("pixel",), coords=coords
    )
    density = xr.DataArray(
        [250.0, 300.0, 350.0],
        dims=("pixel",),
        coords=coords,
        attrs={"units": "kg m-3", "source": "lidar"},
        name="measured_density",
    )

    result = compute_guneriussen_dswe(
        phase, incidence, snow_density_kg_m3=density, wavelength_m=WAVELENGTH_M
    )

    assert result.shape == (3,)
    assert np.isfinite(result.values).all()
    assert density.name == "measured_density"
    assert density.attrs == {"units": "kg m-3", "source": "lidar"}


def test_guneriussen_rejects_density_on_a_different_grid():
    coords = {"pixel": np.array([0, 1, 2])}
    phase, incidence = _inputs(
        np.ones(3), np.full(3, THETA), dims=("pixel",), coords=coords
    )
    density = xr.DataArray(
        [300.0, 300.0, 300.0],
        dims=("pixel",),
        coords={"pixel": np.array([2, 1, 0])},
        attrs={"units": "kg m-3"},
    )

    with pytest.raises(ValueError, match="coordinates differ"):
        compute_guneriussen_dswe(
            phase,
            incidence,
            snow_density_kg_m3=density,
            wavelength_m=WAVELENGTH_M,
        )


def test_oveisgharan_matches_published_polynomial():
    phase, incidence = _inputs()
    a_theta = -0.6784 * THETA**2 + 0.2899 * THETA - 0.8473
    expected = 0.75 / (-2.0 * (2.0 * math.pi / WAVELENGTH_M) * a_theta)

    result = compute_oveisgharan_dswe(phase, incidence, wavelength_m=WAVELENGTH_M)

    assert result.item() == pytest.approx(expected)
    assert result.attrs["retrieval_method"] == "oveisgharan"
    assert result.attrs["a_theta_coefficients"] == [-0.6784, 0.2899, -0.8473]


def test_oveisgharan_matches_analytical_equation():
    phase, incidence = _inputs()
    a_theta = -0.6784 * THETA**2 + 0.2899 * THETA - 0.8473
    expected = 0.75 / (-2.0 * (2.0 * math.pi / WAVELENGTH_M) * a_theta)

    result = compute_oveisgharan_dswe(phase, incidence, wavelength_m=WAVELENGTH_M)

    assert result.item() == pytest.approx(expected)


def test_named_signatures_keep_method_specific_parameters_separate():
    leinss_parameters = inspect.signature(compute_leinss_dswe).parameters
    guneriussen_parameters = inspect.signature(compute_guneriussen_dswe).parameters
    oveisgharan_parameters = inspect.signature(compute_oveisgharan_dswe).parameters

    assert leinss_parameters["alpha"].default == 1.0
    assert (
        guneriussen_parameters["snow_density_kg_m3"].default is inspect.Parameter.empty
    )
    assert guneriussen_parameters["permittivity_model"].default == "guneriussen2001"
    assert "snow_density_kg_m3" not in oveisgharan_parameters
    assert "alpha" not in oveisgharan_parameters


def test_guneriussen_maetzler_high_density_branch_matches_forward_equation():
    density_kg_m3 = 500.0
    density_g_cm3 = density_kg_m3 / 1000.0
    ice_fraction = density_g_cm3 / 0.917
    permittivity = ((1.0 - ice_fraction) + 1.4759 * ice_fraction) ** 3
    refraction = math.cos(THETA) - math.sqrt(permittivity - math.sin(THETA) ** 2)
    snow_depth_change_m = 0.04
    phase_value = (
        -2.0 * (2.0 * math.pi / WAVELENGTH_M) * refraction * snow_depth_change_m
    )
    phase, incidence = _inputs(phase_values=phase_value)

    result = _run_guneriussen(
        phase,
        incidence,
        snow_density_kg_m3=density_kg_m3,
        permittivity_model="maetzler",
    )

    assert result.item() == pytest.approx(snow_depth_change_m * density_kg_m3 / 1000.0)


def test_guneriussen_zero_phase_sign_reversal_and_density_dependence():
    snow_depth_change_m = 0.06
    phase_values = []
    expected_values = []
    for density_kg_m3 in (200.0, 400.0):
        density_g_cm3 = density_kg_m3 / 1000.0
        permittivity = 1.0 + 1.6 * density_g_cm3 + 1.8 * density_g_cm3**3
        refraction = math.cos(THETA) - math.sqrt(permittivity - math.sin(THETA) ** 2)
        phase_for_depth_increase = (
            -2.0 * (2.0 * math.pi / WAVELENGTH_M) * refraction * snow_depth_change_m
        )
        phase_values.append(phase_for_depth_increase)
        expected_values.append(snow_depth_change_m * density_kg_m3 / 1000.0)

    phase, incidence = _inputs(
        phase_values=np.array([0.0, phase_values[0], -phase_values[0]]),
        incidence_values=np.full(3, THETA),
        dims=("pixel",),
        coords={"pixel": np.arange(3)},
    )
    results = _run_guneriussen(phase, incidence, snow_density_kg_m3=200.0)
    assert results[0].item() == 0.0
    assert results[1].item() == pytest.approx(expected_values[0])
    assert results[2].item() == pytest.approx(-expected_values[0])

    dense_phase, dense_incidence = _inputs(
        phase_values=phase_values[1], incidence_values=THETA
    )
    dense_result = _run_guneriussen(
        dense_phase, dense_incidence, snow_density_kg_m3=400.0
    )
    assert dense_result.item() != pytest.approx(results[1].item())
    assert dense_result.item() == pytest.approx(
        phase_values[1]
        / (
            -2.0
            * (2.0 * math.pi / WAVELENGTH_M)
            * (math.cos(THETA) - math.sqrt(permittivity - math.sin(THETA) ** 2))
        )
        * 0.4
    )


@pytest.mark.parametrize(
    "function, extra_kwargs",
    [
        (compute_leinss_dswe, {}),
        (compute_guneriussen_dswe, {"snow_density_kg_m3": 300.0}),
        (compute_oveisgharan_dswe, {}),
    ],
)
def test_methods_reject_bad_angle_units_and_misaligned_grids(function, extra_kwargs):
    phase, incidence = _inputs()
    bad_phase = phase.copy(deep=False)
    bad_phase.attrs = {**phase.attrs, "units": "degrees"}
    with pytest.raises(ValueError, match="invalid or ambiguous angle units"):
        function(bad_phase, incidence, wavelength_m=WAVELENGTH_M, **extra_kwargs)

    misaligned = xr.DataArray(
        [THETA],
        dims=("pixel",),
        coords={"pixel": [1]},
        attrs={"units": "rad", "incidence_angle_reference": "local"},
    )
    with pytest.raises(ValueError, match="identical dimensions and sizes"):
        function(phase, misaligned, wavelength_m=WAVELENGTH_M, **extra_kwargs)


def test_guneriussen_requires_density_and_valid_density_metadata():
    phase, incidence = _inputs()
    with pytest.raises(TypeError, match="snow_density_kg_m3"):
        compute_guneriussen_dswe(phase, incidence, wavelength_m=WAVELENGTH_M)
    with pytest.raises(ValueError, match="units='kg m-3'"):
        compute_guneriussen_dswe(
            phase,
            incidence,
            snow_density_kg_m3=xr.DataArray(300.0),
            wavelength_m=WAVELENGTH_M,
        )
    with pytest.raises(ValueError, match="values must be in"):
        _run_guneriussen(phase, incidence, snow_density_kg_m3=917.0)
    with pytest.raises(ValueError, match="values must be in"):
        _run_guneriussen(phase, incidence, snow_density_kg_m3=1000.0)
    invalid_density = xr.DataArray(
        [0.0, -1.0, 917.0], dims=("pixel",), attrs={"units": "kg m-3"}
    )
    with pytest.raises(ValueError, match="values must be in"):
        compute_guneriussen_dswe(
            xr.DataArray(
                np.ones(3),
                dims=("pixel",),
                attrs={
                    "units": "rad",
                    "phase_difference_definition": "secondary_minus_reference",
                },
            ),
            xr.DataArray(
                np.full(3, THETA),
                dims=("pixel",),
                attrs={"units": "rad", "incidence_angle_reference": "local"},
            ),
            snow_density_kg_m3=invalid_density,
            wavelength_m=WAVELENGTH_M,
        )
    with pytest.raises(ValueError, match="permittivity_model"):
        _run_guneriussen(phase, incidence, permittivity_model="unknown")


@pytest.mark.parametrize(
    "invalid_kind, invalid_value",
    [
        ("incidence", -0.01),
        ("incidence", math.pi / 2.0),
        ("incidence", math.inf),
        ("density", 0.0),
        ("density", -1.0),
        ("density", 917.0),
        ("density", math.inf),
    ],
)
def test_eager_retrieval_rejects_invalid_physical_samples(invalid_kind, invalid_value):
    coords = {"pixel": np.arange(2)}
    phase, incidence = _inputs(
        phase_values=np.ones(2),
        incidence_values=np.full(2, THETA),
        dims=("pixel",),
        coords=coords,
    )
    density: float | xr.DataArray = 300.0
    if invalid_kind == "incidence":
        incidence = incidence.copy(data=np.array([THETA, invalid_value]))
    else:
        density = xr.DataArray(
            [300.0, invalid_value],
            dims=("pixel",),
            coords=coords,
            attrs={"units": "kg m-3"},
        )

    with pytest.raises(ValueError, match="values must be in"):
        compute_guneriussen_dswe(
            phase,
            incidence,
            snow_density_kg_m3=density,
            wavelength_m=WAVELENGTH_M,
        )


@pytest.mark.parametrize("missing_kind", ["incidence", "density"])
def test_missing_physical_samples_propagate_equally_eager_and_lazy(missing_kind):
    da = pytest.importorskip("dask.array")
    coords = {"pixel": np.arange(2)}
    phase, incidence = _inputs(
        phase_values=np.ones(2),
        incidence_values=np.full(2, THETA),
        dims=("pixel",),
        coords=coords,
    )
    density: float | xr.DataArray = 300.0
    if missing_kind == "incidence":
        incidence = incidence.copy(data=np.array([THETA, np.nan]))
        lazy_incidence = incidence.copy(data=da.from_array(incidence.data, chunks=1))
        lazy_density: float | xr.DataArray = density
    else:
        density = xr.DataArray(
            [300.0, np.nan],
            dims=("pixel",),
            coords=coords,
            attrs={"units": "kg m-3"},
        )
        lazy_incidence = incidence.copy(data=da.from_array(incidence.data, chunks=1))
        lazy_density = density.copy(data=da.from_array(density.data, chunks=1))

    eager = compute_guneriussen_dswe(
        phase,
        incidence,
        snow_density_kg_m3=density,
        wavelength_m=WAVELENGTH_M,
    )
    lazy = compute_guneriussen_dswe(
        phase.copy(data=da.from_array(phase.data, chunks=1)),
        lazy_incidence,
        snow_density_kg_m3=lazy_density,
        wavelength_m=WAVELENGTH_M,
    )

    assert lazy.chunks is not None
    np.testing.assert_allclose(lazy.compute().values, eager.values, equal_nan=True)


def test_methods_preserve_nan_support_and_sign():
    phase, incidence = _inputs(
        np.array([1.0, np.nan, -1.0]), np.full(3, THETA), dims=("pixel",)
    )

    for result in (
        compute_leinss_dswe(phase, incidence, wavelength_m=WAVELENGTH_M),
        compute_guneriussen_dswe(
            phase,
            incidence,
            snow_density_kg_m3=300.0,
            wavelength_m=WAVELENGTH_M,
        ),
        compute_oveisgharan_dswe(phase, incidence, wavelength_m=WAVELENGTH_M),
    ):
        assert result[0] > 0
        assert np.isnan(result[1])
        assert result[2] < 0


@pytest.mark.parametrize(
    "method",
    ["leinss", "guneriussen", "oveisgharan"],
)
def test_named_methods_preserve_dask_laziness_when_available(method):
    da = pytest.importorskip("dask.array")
    coords = {"pixel": np.arange(3)}
    phase_values = np.array([0.5, 0.75, 1.0])
    incidence_values = np.full(3, THETA)
    phase = xr.DataArray(
        da.from_array(phase_values, chunks=2),
        dims=("pixel",),
        coords=coords,
        attrs={
            "units": "rad",
            "phase_difference_definition": "secondary_minus_reference",
        },
    )
    incidence = xr.DataArray(
        da.from_array(incidence_values, chunks=2),
        dims=("pixel",),
        coords=coords,
        attrs={"units": "rad", "incidence_angle_reference": "local"},
    )

    if method == "leinss":
        result = compute_leinss_dswe(phase, incidence, wavelength_m=WAVELENGTH_M)
    elif method == "guneriussen":
        density = xr.DataArray(
            da.from_array(np.full(3, 300.0), chunks=2),
            dims=("pixel",),
            coords=coords,
            attrs={"units": "kg m-3"},
        )
        result = compute_guneriussen_dswe(
            phase,
            incidence,
            snow_density_kg_m3=density,
            wavelength_m=WAVELENGTH_M,
        )
    else:
        result = compute_oveisgharan_dswe(phase, incidence, wavelength_m=WAVELENGTH_M)

    assert result.chunks is not None
    assert np.isfinite(result.compute().values).all()


@pytest.mark.parametrize(
    "invalid_kind, invalid_value",
    [
        ("incidence", -0.01),
        ("incidence", math.pi / 2.0),
        ("incidence", math.inf),
        ("density", 0.0),
        ("density", -1.0),
        ("density", 917.0),
        ("density", math.inf),
    ],
)
def test_guneriussen_lazy_invalid_values_fail_when_computed(
    invalid_kind, invalid_value
):
    da = pytest.importorskip("dask.array")
    coords = {"pixel": np.arange(2)}
    phase, incidence = _inputs(
        phase_values=np.ones(2),
        incidence_values=np.full(2, THETA),
        dims=("pixel",),
        coords=coords,
    )
    phase = phase.copy(data=da.from_array(phase.data, chunks=1))
    if invalid_kind == "incidence":
        incidence = incidence.copy(
            data=da.from_array(np.array([THETA, invalid_value]), chunks=1)
        )
        density = 300.0
    else:
        incidence = incidence.copy(data=da.from_array(incidence.data, chunks=1))
        density = xr.DataArray(
            da.from_array(np.array([300.0, invalid_value]), chunks=1),
            dims=("pixel",),
            coords=coords,
            attrs={"units": "kg m-3"},
        )

    result = compute_guneriussen_dswe(
        phase,
        incidence,
        snow_density_kg_m3=density,
        wavelength_m=WAVELENGTH_M,
    )
    assert result.chunks is not None
    message = (
        "incidence_angle values must be in"
        if invalid_kind == "incidence"
        else "snow_density_kg_m3 values must be in"
    )
    with pytest.raises(ValueError, match=message):
        result.compute()
