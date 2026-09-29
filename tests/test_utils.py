import numpy as np
import pytest

from snowin.utils import finite_fraction, validate_same_shape


def test_validate_same_shape():
    assert validate_same_shape(np.zeros((2, 2)), np.ones((2, 2))) == (2, 2)
    with pytest.raises(ValueError, match="Array shapes differ"):
        validate_same_shape(np.zeros((2, 2)), np.ones((3, 2)))


def test_validate_same_shape_handles_missing_inputs():
    assert validate_same_shape(None, np.zeros((2, 3))) == (2, 3)
    with pytest.raises(ValueError, match="At least one array"):
        validate_same_shape(None, None)


def test_finite_fraction():
    assert finite_fraction(np.array([1.0, np.nan, 3.0])) == pytest.approx(2 / 3)
    assert np.isnan(finite_fraction(None))
    assert np.isnan(finite_fraction(np.array([], dtype=float)))
