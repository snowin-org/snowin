import math

import pytest

from snowin.snow import list_supported_sensors, sensor_wavelength_m


@pytest.mark.parametrize(
    ("sensor", "band", "expected"),
    [
        ("nisar", "L", 0.24),
        ("nisar", "S", 0.10),
        ("uavsar", None, 0.23840354572564613),
        ("sentinel1", None, 0.05546668973172988),
    ],
)
def test_explicit_sensor_lookup(sensor, band, expected):
    assert sensor_wavelength_m(sensor=sensor, band=band) == pytest.approx(expected)


def test_explicit_wavelength_takes_precedence():
    assert sensor_wavelength_m(sensor="nisar", band="L", wavelength_m=0.123) == 0.123


def test_registry_rejects_ambiguous_or_invalid_values():
    with pytest.raises(ValueError, match="band is required"):
        sensor_wavelength_m(sensor="nisar")
    with pytest.raises(ValueError, match="Unsupported sensor"):
        sensor_wavelength_m(sensor="unknown")
    with pytest.raises(ValueError, match="finite and > 0"):
        sensor_wavelength_m(wavelength_m=math.inf)
    assert "nisar" in list_supported_sensors()
