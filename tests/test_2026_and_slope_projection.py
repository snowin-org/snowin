"""Analytical checks of the printed 2026 equation and terrain projection."""

import numpy as np
import pytest
import xarray as xr

from snowin import (
    compute_oveisgharan_2026_dswe,
    compute_oveisgharan_dswe,
    project_swe_to_vertical,
)


def arrays():
    phase = xr.DataArray(
        [-2.0, 0.0, 3.0, np.nan],
        dims="x",
        coords={"x": [1, 2, 3, 4]},
        attrs={
            "units": "rad",
            "phase_difference_definition": "reference_minus_secondary",
        },
    )
    angle = phase.copy(data=np.deg2rad([10.0, 30.0, 65.0, 75.0]))
    angle.attrs = {"units": "rad", "incidence_angle_reference": "local"}
    return phase, angle


@pytest.mark.parametrize("wavelength", [0.055, 0.241963242938])
def test_printed_2026_equation(wavelength):
    phase, angle = arrays()
    actual = compute_oveisgharan_2026_dswe(phase, angle, wavelength_m=wavelength)
    theta = angle.values.astype(float)
    expected = (
        phase.values
        * wavelength
        / (-4 * np.pi * (-0.3385 * theta**2 + 0.0486 * theta - 0.8647))
    )
    # Float32 arithmetic in the public kernel sets the tolerance.
    np.testing.assert_allclose(actual.values, expected, rtol=4e-7, atol=1e-8)
    assert actual.dtype == np.float32
    assert actual.coords.equals(phase.coords)
    assert actual.attrs["dswe_difference_definition"] == "secondary_minus_reference"
    assert actual.attrs["retrieval_method"] == "oveisgharan_2026"
    earlier = compute_oveisgharan_dswe(phase, angle, wavelength_m=wavelength)
    assert not np.isclose(actual.values[2], earlier.values[2], rtol=0.01)


def test_projection_equation_metadata_and_missing_support():
    swe = xr.DataArray(
        [100.0, -100.0, 0.0, np.nan],
        dims="x",
        attrs={
            "units": "mm",
            "swe_thickness_reference": "slope_normal",
            "crs": "EPSG:32613",
        },
        name="dswe",
    )
    slope = xr.DataArray(
        np.deg2rad([0.0, 60.0, 45.0, 30.0]), dims="x", attrs={"units": "rad"}
    )
    actual = project_swe_to_vertical(swe, slope)
    np.testing.assert_allclose(
        actual.values, [100.0, -200.0, 0.0, np.nan], rtol=3e-7, atol=1e-6
    )
    assert actual.name == swe.name
    assert actual.dtype == np.float32
    assert actual.attrs["crs"] == swe.attrs["crs"]
    assert actual.attrs["swe_thickness_reference"] == "vertical"
    with pytest.raises(ValueError, match="slope_normal"):
        project_swe_to_vertical(actual, slope)


def test_2026_and_projection_preserve_lazy_arrays():
    pytest.importorskip("dask.array")
    phase, angle = arrays()
    eager = compute_oveisgharan_2026_dswe(phase, angle, wavelength_m=0.24)
    lazy = compute_oveisgharan_2026_dswe(
        phase.chunk(x=2), angle.chunk(x=2), wavelength_m=0.24
    )
    assert lazy.chunks is not None
    xr.testing.assert_allclose(lazy.compute(), eager, rtol=4e-7, atol=1e-8)
    eager.attrs["swe_thickness_reference"] = "slope_normal"
    slope = angle.copy()
    actual = project_swe_to_vertical(eager.chunk(x=2), slope.chunk(x=2))
    assert actual.chunks is not None
    xr.testing.assert_allclose(
        actual.compute(), project_swe_to_vertical(eager, slope), rtol=4e-7, atol=1e-8
    )


def test_projection_requires_explicit_units_and_aligned_geometry():
    swe, slope = arrays()
    swe.attrs = {"units": "m", "swe_thickness_reference": "slope_normal"}
    with pytest.raises(ValueError, match="coordinates"):
        project_swe_to_vertical(swe, slope.assign_coords(x=[2, 3, 4, 5]))
    slope.attrs["units"] = "degrees"
    with pytest.raises(ValueError, match="radians"):
        project_swe_to_vertical(swe, slope)
    slope.attrs["units"] = "rad"
    slope.values[0] = np.pi / 2
    with pytest.raises(ValueError, match="slope_angle"):
        project_swe_to_vertical(swe, slope)
