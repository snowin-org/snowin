import numpy as np
import pytest

from snowin.snow import phase_to_dswe
from snowin.workflows import phase_raster_to_dswe


def test_phase_raster_to_dswe_matches_scalar_function_cm():
    phase = np.array([[-1.0, -2.0]])
    theta = np.deg2rad(np.array([[35.0, 35.0]]))
    out = phase_raster_to_dswe(phase, theta, method="oveisgharan", sensor="nisar", band="L", incidence_angle_unit="radians")
    expected_m = phase_to_dswe(phase, "oveisgharan", theta, sensor="nisar", band="L")
    assert out.unit == "cm"
    assert np.allclose(out.dswe, expected_m * 100.0)
    assert out.valid_mask.all()


def test_phase_raster_to_dswe_degrees_equivalent_to_radians():
    phase = np.array([[-1.0]])
    out_deg = phase_raster_to_dswe(phase, np.array([[35.0]]), incidence_angle_unit="degrees")
    out_rad = phase_raster_to_dswe(phase, np.deg2rad(np.array([[35.0]])), incidence_angle_unit="radians")
    assert np.allclose(out_deg.dswe, out_rad.dswe)


def test_phase_raster_to_dswe_invalid_incidence_fails():
    with pytest.raises(ValueError):
        phase_raster_to_dswe(np.array([[1.0]]), np.array([[100.0]]), incidence_angle_unit="radians")


def test_phase_raster_to_dswe_guneriussen_requires_density():
    with pytest.raises(ValueError, match="snow_density_g_cm3 is required"):
        phase_raster_to_dswe(
            np.array([[1.0]]),
            np.deg2rad(np.array([[35.0]])),
            method="guneriussen",
            incidence_angle_unit="radians",
        )


def test_phase_raster_to_dswe_shape_mismatch_fails_by_default():
    with pytest.raises(ValueError, match="shapes differ"):
        phase_raster_to_dswe(
            np.ones((4, 5)),
            np.deg2rad(np.full((2, 2), 35.0)),
            incidence_angle_unit="radians",
        )


def test_phase_raster_to_dswe_shape_mismatch_median_policy_records_diagnostic():
    phase = -np.ones((4, 5))
    incidence = np.deg2rad(np.array([[30.0, 40.0], [50.0, 60.0]]))
    out = phase_raster_to_dswe(
        phase,
        incidence,
        incidence_angle_unit="radians",
        incidence_shape_policy="median",
    )
    assert out.dswe.shape == phase.shape
    assert np.isfinite(out.dswe).all()
    assert out.diagnostics["incidence_shape_handling"] == "median_expanded_due_to_shape_mismatch"
    assert out.diagnostics["incidence_original_shape"] == (2, 2)
    assert out.diagnostics["incidence_final_shape"] == (4, 5)
    assert np.isclose(out.diagnostics["incidence_angle_median_used"], np.nanmedian(incidence))
