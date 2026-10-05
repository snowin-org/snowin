"""Property checks for the xarray ΔSWE kernel."""

from __future__ import annotations

import math

import hypothesis.strategies as st
import numpy as np
import xarray as xr
from hypothesis import given, settings
from hypothesis.extra import numpy as hnp

from snowin import compute_leinss_dswe

WAVELENGTH_M = 0.238403545


@st.composite
def _physical_inputs(draw):
    dtype = draw(st.sampled_from([np.dtype("float32"), np.dtype("float64")]))
    shape = draw(st.sampled_from([(), (3,), (2, 2)]))
    float_width = 32 if dtype == np.dtype("float32") else 64
    max_angle = float(np.float32(1.56)) if float_width == 32 else 1.56
    phase_values = draw(
        hnp.arrays(
            dtype=dtype,
            shape=shape,
            elements=st.floats(
                min_value=-8.0,
                max_value=8.0,
                allow_nan=False,
                allow_infinity=False,
                width=float_width,
            ),
        )
    )
    angle_values = draw(
        hnp.arrays(
            dtype=dtype,
            shape=shape,
            elements=st.floats(
                min_value=0.0,
                max_value=max_angle,
                allow_nan=False,
                allow_infinity=False,
                width=float_width,
            ),
        )
    )
    if len(shape) == 2:
        dims = ("y", "x")
        coords = {"y": [4200.0, 4190.0], "x": [500000.0, 500010.0]}
    elif len(shape) == 1:
        dims = ("pixel",)
        coords = {"pixel": [0, 1, 2]}
    else:
        dims = ()
        coords = None
    phase = xr.DataArray(
        phase_values,
        dims=dims,
        coords=coords,
        name="phase",
        attrs={
            "units": "rad",
            "phase_difference_definition": "reference_minus_secondary",
        },
    )
    incidence = xr.DataArray(
        angle_values,
        dims=dims,
        coords=coords,
        name="incidence_angle",
        attrs={"units": "rad", "incidence_angle_reference": "local"},
    )
    return dtype, phase, incidence


def _tolerances(dtype: np.dtype) -> tuple[float, float]:
    # float32 arithmetic is rounded to about seven decimal digits; the absolute
    # floor only covers values near zero. Float64 retains a much tighter oracle.
    if dtype == np.dtype("float32"):
        return 2e-6, 2e-8
    return 2e-13, 2e-15


def _with_values(template: xr.DataArray, values: np.ndarray) -> xr.DataArray:
    return xr.DataArray(
        values,
        dims=template.dims,
        coords=template.coords,
        name=template.name,
        attrs=dict(template.attrs),
    )


@settings(max_examples=40, derandomize=True, deadline=None)
@given(inputs=_physical_inputs())
def test_dswe_matches_independent_leinss_equation_over_small_shapes(inputs):
    dtype, phase, incidence = inputs

    actual = compute_leinss_dswe(phase, incidence, wavelength_m=WAVELENGTH_M)
    phase64 = np.asarray(phase.data, dtype=np.float64)
    angle64 = np.asarray(incidence.data, dtype=np.float64)
    expected = phase64 * WAVELENGTH_M / (2.0 * math.pi * (1.59 + angle64**2.5))

    np.testing.assert_allclose(
        actual.values,
        expected,
        rtol=_tolerances(dtype)[0],
        atol=_tolerances(dtype)[1],
    )
    assert actual.dims == phase.dims
    assert actual.shape == phase.shape
    for dimension in phase.dims:
        xr.testing.assert_equal(actual.coords[dimension], phase.coords[dimension])


@settings(max_examples=40, derandomize=True, deadline=None)
@given(inputs=_physical_inputs())
def test_zero_phase_gives_zero_dswe_for_scalar_and_array_inputs(inputs):
    _, phase, incidence = inputs
    zero_phase = _with_values(phase, np.zeros(phase.shape, dtype=phase.dtype))

    actual = compute_leinss_dswe(zero_phase, incidence, wavelength_m=WAVELENGTH_M)

    np.testing.assert_array_equal(actual.values, np.zeros(phase.shape))


@settings(max_examples=40, derandomize=True, deadline=None)
@given(inputs=_physical_inputs())
def test_phase_sign_reversal_reverses_dswe(inputs):
    dtype, phase, incidence = inputs
    baseline = compute_leinss_dswe(phase, incidence, wavelength_m=WAVELENGTH_M)
    reversed_phase = _with_values(phase, -np.asarray(phase.data))
    reversed_result = compute_leinss_dswe(
        reversed_phase, incidence, wavelength_m=WAVELENGTH_M
    )

    np.testing.assert_allclose(
        reversed_result.values,
        -baseline.values,
        rtol=_tolerances(dtype)[0],
        atol=_tolerances(dtype)[1],
    )


@settings(max_examples=40, derandomize=True, deadline=None)
@given(
    inputs=_physical_inputs(),
    phase_scale=st.floats(min_value=0.1, max_value=5.0, allow_nan=False),
)
def test_dswe_is_linear_in_phase(inputs, phase_scale):
    dtype, phase, incidence = inputs
    baseline = compute_leinss_dswe(phase, incidence, wavelength_m=WAVELENGTH_M)
    scaled_phase = _with_values(phase, np.asarray(phase.data) * phase_scale)
    scaled = compute_leinss_dswe(scaled_phase, incidence, wavelength_m=WAVELENGTH_M)

    np.testing.assert_allclose(
        scaled.values,
        baseline.values * phase_scale,
        rtol=_tolerances(dtype)[0],
        atol=_tolerances(dtype)[1],
    )


@settings(max_examples=40, derandomize=True, deadline=None)
@given(
    inputs=_physical_inputs(),
    wavelength_scale=st.floats(min_value=0.1, max_value=5.0, allow_nan=False),
)
def test_dswe_is_linear_in_wavelength(inputs, wavelength_scale):
    dtype, phase, incidence = inputs
    baseline = compute_leinss_dswe(phase, incidence, wavelength_m=WAVELENGTH_M)
    scaled = compute_leinss_dswe(
        phase,
        incidence,
        wavelength_m=WAVELENGTH_M * wavelength_scale,
    )

    np.testing.assert_allclose(
        scaled.values,
        baseline.values * wavelength_scale,
        rtol=_tolerances(dtype)[0],
        atol=_tolerances(dtype)[1],
    )


@settings(max_examples=40, derandomize=True, deadline=None)
@given(
    inputs=_physical_inputs(),
    alpha=st.floats(min_value=0.1, max_value=5.0, allow_nan=False),
)
def test_dswe_scales_inversely_with_leinss_alpha(inputs, alpha):
    dtype, phase, incidence = inputs
    baseline = compute_leinss_dswe(phase, incidence, wavelength_m=WAVELENGTH_M)
    scaled = compute_leinss_dswe(
        phase,
        incidence,
        wavelength_m=WAVELENGTH_M,
        alpha=alpha,
    )

    np.testing.assert_allclose(
        scaled.values,
        baseline.values / alpha,
        rtol=_tolerances(dtype)[0],
        atol=_tolerances(dtype)[1],
    )


@settings(max_examples=40, derandomize=True, deadline=None)
@given(
    inputs=_physical_inputs(),
    lower_angle=st.floats(min_value=0.0, max_value=1.4, allow_nan=False),
    angle_increment=st.floats(min_value=1e-4, max_value=0.15, allow_nan=False),
)
def test_positive_phase_dswe_decreases_with_valid_incidence_angle(
    inputs, lower_angle, angle_increment
):
    dtype, phase, _ = inputs
    positive_phase = _with_values(phase, np.abs(np.asarray(phase.data)))
    lower = np.full(phase.shape, lower_angle, dtype=dtype)
    higher = np.full(phase.shape, lower_angle + angle_increment, dtype=dtype)
    lower_incidence = _with_values(
        xr.DataArray(
            lower,
            dims=phase.dims,
            coords=phase.coords,
            attrs={"units": "rad", "incidence_angle_reference": "local"},
        ),
        lower,
    )
    higher_incidence = _with_values(lower_incidence, higher)

    lower_dswe = compute_leinss_dswe(
        positive_phase, lower_incidence, wavelength_m=WAVELENGTH_M
    )
    higher_dswe = compute_leinss_dswe(
        positive_phase, higher_incidence, wavelength_m=WAVELENGTH_M
    )
    rtol, atol = _tolerances(dtype)

    assert np.all(
        higher_dswe.values
        <= lower_dswe.values + atol + rtol * np.abs(lower_dswe.values)
    )
