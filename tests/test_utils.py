import numpy as np
import pytest
import xarray as xr

from snowin.utils import angle_to_radians_if_needed, dataarray_to_numpy, finite_fraction, validate_same_shape


def test_dataarray_to_numpy_complex_magnitude():
    da = xr.DataArray(np.array([[3 + 4j]]))
    out = dataarray_to_numpy(da, magnitude=True)
    assert out[0, 0] == pytest.approx(5.0)


def test_dataarray_to_numpy_complex_angle():
    da = xr.DataArray(np.array([[1 + 1j]]))
    out = dataarray_to_numpy(da, angle=True)
    assert out[0, 0] == pytest.approx(np.pi / 4)


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


def test_validate_same_shape():
    assert validate_same_shape(np.zeros((2, 2)), np.ones((2, 2))) == (2, 2)
    with pytest.raises(ValueError):
        validate_same_shape(np.zeros((2, 2)), np.ones((3, 2)))


def test_finite_fraction():
    assert finite_fraction(np.array([1.0, np.nan, 3.0])) == pytest.approx(2 / 3)
