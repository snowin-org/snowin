"""Independent equation and round-trip checks for snow-depth conversions."""

from __future__ import annotations

import math

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

from snowin.snow.snow_depth import (
    phase_to_snow_depth_change,
    snow_depth_change_to_phase,
)


def _independent_refraction(angle_rad: float, density_g_cm3: float) -> float:
    if density_g_cm3 < 0.4:
        permittivity = 1.0 + 1.5995 * density_g_cm3 + 1.861 * density_g_cm3**3
    else:
        density_fraction = density_g_cm3 / 0.917
        permittivity = ((1.0 - density_fraction) + 1.4759 * density_fraction) ** 3
    return math.cos(angle_rad) - math.sqrt(permittivity - math.sin(angle_rad) ** 2)


@settings(max_examples=60, derandomize=True, deadline=None)
@given(
    phase=st.floats(min_value=-8.0, max_value=8.0, allow_nan=False),
    angle=st.floats(min_value=0.0, max_value=1.56, allow_nan=False),
    density=st.floats(min_value=0.02, max_value=0.9, allow_nan=False),
    wavelength=st.floats(min_value=0.05, max_value=0.4, allow_nan=False),
)
def test_phase_to_depth_matches_independent_guneriussen_equation(
    phase, angle, density, wavelength
):
    refraction = _independent_refraction(angle, density)
    expected_depth = phase / (-2.0 * (2.0 * math.pi / wavelength) * refraction)

    actual_depth = phase_to_snow_depth_change(
        phase,
        angle,
        wavelength_m=wavelength,
        snow_density_g_cm3=density,
    )

    assert actual_depth == pytest.approx(expected_depth, rel=2e-13, abs=2e-15)


@pytest.mark.parametrize("density", [0.2, 0.399999, 0.4, 0.7])
def test_maetzler_density_branch_boundary_matches_independent_equation(density):
    angle = math.radians(35.0)
    phase = -1.25
    wavelength = 0.238403545
    expected = phase / (
        -2.0 * (2.0 * math.pi / wavelength) * _independent_refraction(angle, density)
    )

    actual = phase_to_snow_depth_change(
        phase,
        angle,
        wavelength_m=wavelength,
        snow_density_g_cm3=density,
    )

    assert actual == pytest.approx(expected, rel=2e-13, abs=2e-15)


@settings(max_examples=60, derandomize=True, deadline=None)
@given(
    depth=st.floats(min_value=-2.0, max_value=2.0, allow_nan=False),
    angle=st.floats(min_value=0.0, max_value=1.56, allow_nan=False),
    density=st.floats(min_value=0.02, max_value=0.9, allow_nan=False),
    wavelength=st.floats(min_value=0.05, max_value=0.4, allow_nan=False),
)
def test_depth_to_phase_matches_forward_equation_and_inverts(
    depth, angle, density, wavelength
):
    refraction = _independent_refraction(angle, density)
    expected_phase = -2.0 * (2.0 * math.pi / wavelength) * refraction * depth

    actual_phase = snow_depth_change_to_phase(
        depth,
        angle,
        wavelength_m=wavelength,
        snow_density_g_cm3=density,
    )
    recovered_depth = phase_to_snow_depth_change(
        actual_phase,
        angle,
        wavelength_m=wavelength,
        snow_density_g_cm3=density,
    )

    assert actual_phase == pytest.approx(expected_phase, rel=2e-13, abs=2e-15)
    assert recovered_depth == pytest.approx(depth, rel=2e-13, abs=2e-15)


@pytest.mark.parametrize("density", [0.0, -0.1, 0.917, 1.0])
def test_snow_depth_rejects_nonphysical_snow_density(density):
    with pytest.raises(ValueError, match="snow_density_g_cm3"):
        phase_to_snow_depth_change(
            1.0,
            math.radians(35.0),
            wavelength_m=0.24,
            snow_density_g_cm3=density,
        )


def test_snow_depth_rejects_incidence_at_ninety_degrees():
    with pytest.raises(ValueError, match=r"\[0, pi/2\)"):
        phase_to_snow_depth_change(
            1.0,
            math.pi / 2.0,
            wavelength_m=0.24,
            snow_density_g_cm3=0.3,
        )
