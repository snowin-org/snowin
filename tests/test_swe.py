
import math

import numpy as np
import pytest

from snowin.snow import (
    cm_to_m,
    leinss_a_theta,
    list_supported_sensors,
    m_to_cm,
    maetzler_permittivity,
    phase_to_dswe,
    refraction_term,
    sensor_wavelength_m,
)


def test_supported_sensors_nonempty():
    sensors = list_supported_sensors()
    assert "nisar" in sensors
    assert "uavsar" in sensors


def test_nisar_requires_band_when_no_wavelength():
    with pytest.raises(ValueError, match="band is required when sensor='nisar'"):
        phase_to_dswe(
            phase_rad=-1.0,
            method="leinss",
            incidence_angle_rad=math.radians(35.0),
            sensor="nisar",
        )


def test_wavelength_override_beats_sensor():
    result = phase_to_dswe(
        phase_rad=-1.0,
        method="leinss",
        incidence_angle_rad=math.radians(35.0),
        sensor="nisar",
        band="L",
        wavelength_m=0.10,
    )
    assert isinstance(result, float)


def test_guneriussen_requires_density():
    with pytest.raises(ValueError, match="snow_density_g_cm3 is required"):
        phase_to_dswe(
            phase_rad=-1.0,
            method="guneriussen",
            incidence_angle_rad=math.radians(35.0),
            sensor="nisar",
            band="L",
        )


def test_leinss_works_for_s1():
    result = phase_to_dswe(
        phase_rad=-1.0,
        method="leinss",
        incidence_angle_rad=math.radians(35.0),
        sensor="s1",
    )
    assert isinstance(result, float)


def test_oveisgharan_vectorized_for_nisar_l():
    phase = np.array([-0.5, -1.0, -1.5])
    theta = np.radians(np.array([30.0, 35.0, 40.0]))
    dswe = phase_to_dswe(
        phase_rad=phase,
        method="oveisgharan",
        incidence_angle_rad=theta,
        sensor="nisar",
        band="L",
    )
    assert dswe.shape == phase.shape


def test_sensor_wavelengths_are_reasonable():
    wl_s1 = sensor_wavelength_m(sensor="s1")
    wl_tsx = sensor_wavelength_m(sensor="terrasarx")
    wl_nisar_l = sensor_wavelength_m(sensor="nisar", band="L")
    wl_nisar_s = sensor_wavelength_m(sensor="nisar", band="S")

    assert 0.05 < wl_s1 < 0.06
    assert 0.02 < wl_tsx < 0.04
    assert 0.20 < wl_nisar_l < 0.26
    assert 0.08 < wl_nisar_s < 0.12


def test_maetzler_permittivity_reasonable():
    eps = maetzler_permittivity(0.3)
    assert eps > 1.0
    assert eps < 3.0


def test_refraction_term_negative_for_typical_snow():
    c = refraction_term(math.radians(35.0), 0.3)
    assert c < 0


def test_leinss_a_theta_negative_in_typical_range():
    vals = leinss_a_theta(np.radians(np.array([20.0, 30.0, 40.0])))
    assert np.all(vals < 0)


def test_unit_helpers():
    assert cm_to_m(10.0) == pytest.approx(0.1)
    assert m_to_cm(0.1) == pytest.approx(10.0)
