import numpy as np
import pytest
import xarray as xr

from snowin.utils import (
    angle_to_radians_if_needed,
    dataarray_to_numpy,
    finite_fraction,
    validate_same_shape,
)


def test_dataarray_to_numpy_complex_magnitude():
    da = xr.DataArray(np.array([[3 + 4j]]))
    out = dataarray_to_numpy(da, magnitude=True)
    assert out[0, 0] == pytest.approx(5.0)


def test_dataarray_to_numpy_complex_angle():
    da = xr.DataArray(np.array([[1 + 1j]]))
    out = dataarray_to_numpy(da, angle=True)
    assert out[0, 0] == pytest.approx(np.pi / 4)


@pytest.mark.parametrize(
    "values, expected_shape",
    [
        (np.array(3.0), (1, 1)),
        (np.array([1.0, 2.0, 3.0]), (1, 3)),
        (np.arange(24.0).reshape(2, 3, 4), (3, 4)),
    ],
)
def test_dataarray_to_numpy_reduces_higher_rank_and_adds_two_dimensional_shape(
    values, expected_shape
):
    out = dataarray_to_numpy(values)

    assert out.shape == expected_shape
    if values.ndim == 3:
        np.testing.assert_array_equal(out, values[0])


def test_dataarray_to_numpy_decibels_clamp_nonpositive_magnitude():
    out = dataarray_to_numpy(np.array([1.0, 0.0, -2.0]), db=True)

    assert out[0, 0] == pytest.approx(0.0)
    assert out[0, 1] == pytest.approx(20.0 * np.log10(1e-12))
    assert out[0, 2] == pytest.approx(20.0 * np.log10(1e-12))


def test_array_validators_handle_empty_and_missing_inputs():
    assert validate_same_shape(None, np.zeros((2, 3))) == (2, 3)
    with pytest.raises(ValueError, match="At least one array"):
        validate_same_shape(None, None)
    assert np.isnan(finite_fraction(None))
    assert np.isnan(finite_fraction(np.array([], dtype=float)))

    with pytest.raises(ValueError, match="da must not be None"):
        dataarray_to_numpy(None)


def test_angle_degrees_to_radians():
    out, unit = angle_to_radians_if_needed(np.array([30.0, 40.0]), unit="degrees")
    assert unit == "degrees"
    assert out[0] == pytest.approx(np.deg2rad(30.0))


def test_angle_radians_unchanged():
    inp = np.array([0.3, 0.5])
    out, unit = angle_to_radians_if_needed(inp, unit="radians")
    assert unit == "radians"
    assert np.allclose(out, inp)


def test_angle_invalid_raises():
    with pytest.raises(ValueError):
        angle_to_radians_if_needed(np.array([100.0]), unit="radians")


def test_angle_auto_mode_warns_about_each_inferred_interpretation():
    with pytest.warns(RuntimeWarning, match="appears to be in degrees"):
        degrees, degrees_used = angle_to_radians_if_needed(
            np.array([30.0, 40.0, 50.0]), unit=None
        )
    assert degrees_used == "degrees_inferred"
    assert degrees[1] == pytest.approx(np.deg2rad(40.0))

    with pytest.warns(RuntimeWarning, match="appears to be in radians"):
        radians, radians_used = angle_to_radians_if_needed(
            np.array([0.3, 0.5]), unit="auto"
        )
    assert radians_used == "radians_inferred"
    np.testing.assert_allclose(radians, [0.3, 0.5])


def test_angle_conversion_requires_finite_input_and_known_unit():
    with pytest.raises(ValueError, match="no finite values"):
        angle_to_radians_if_needed(np.array([np.nan, np.inf]), unit="radians")
    with pytest.raises(ValueError, match="unit must be one of"):
        angle_to_radians_if_needed(np.array([0.3]), unit="grads")


def test_validate_same_shape():
    assert validate_same_shape(np.zeros((2, 2)), np.ones((2, 2))) == (2, 2)
    with pytest.raises(ValueError):
        validate_same_shape(np.zeros((2, 2)), np.ones((3, 2)))


def test_finite_fraction():
    assert finite_fraction(np.array([1.0, np.nan, 3.0])) == pytest.approx(2 / 3)
