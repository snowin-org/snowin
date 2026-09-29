"""Stock wavelength values for explicitly selected radar sensors and bands."""

from __future__ import annotations

import math
from numbers import Real

# Wavelengths are stock lookup values only. Product metadata or an explicit
# wavelength should be preferred whenever it is available.
_SENSOR_WAVELENGTHS_M: dict[tuple[str, str | None], float] = {
    ("nisar", "L"): 0.24,
    ("nisar", "S"): 0.10,
    ("sentinel1", None): 0.05546668973172988,
    ("s1", None): 0.05546668973172988,
    ("uavsar", None): 0.23840354572564613,
    ("terrasarx", None): 0.031066576994818654,
    ("tsx", None): 0.031066576994818654,
    ("tandemx", None): 0.031066576994818654,
    ("tdx", None): 0.031066576994818654,
    ("radarsat1", None): 0.05656461471698113,
    ("radarsat2", None): 0.05546668973172988,
    ("radarsat", None): 0.05546668973172988,
    ("rcm", None): 0.05546668973172988,
    ("alos_palsar", None): 0.23605626614173228,
    ("palsar", None): 0.23605626614173228,
    ("alos2_palsar2", None): 0.24982704833333335,
    ("palsar2", None): 0.24982704833333335,
    ("saocom", None): 0.23513133960784314,
    ("ers1", None): 0.05656461471698113,
    ("ers2", None): 0.05656461471698113,
    ("envisat_asar", None): 0.05623474812474207,
    ("asar", None): 0.05623474812474207,
}

_GENERIC_BAND_WAVELENGTHS_M = {
    "L": 0.24,
    "S": 0.10,
    "C": 0.05546668973172988,
    "X": 0.031066576994818654,
}


def list_supported_sensors() -> list[str]:
    """Return sorted stock sensor names accepted by the named retrievals."""
    return sorted({sensor for sensor, _ in _SENSOR_WAVELENGTHS_M})


def sensor_wavelength_m(
    sensor: str | None = None,
    band: str | None = None,
    wavelength_m: float | None = None,
) -> float:
    """Resolve an explicit wavelength or a caller-selected stock value."""
    if wavelength_m is not None:
        if not isinstance(wavelength_m, Real):
            raise TypeError("wavelength_m must be a finite positive scalar")
        value = float(wavelength_m)
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError("wavelength_m must be finite and > 0")
        return value

    band_norm = band.upper() if band is not None else None
    sensor_norm = sensor.lower() if sensor is not None else None

    if sensor_norm is not None:
        if sensor_norm == "nisar" and band_norm is None:
            raise ValueError(
                "band is required when sensor='nisar'. Use band='L' or band='S'."
            )
        if (sensor_norm, band_norm) in _SENSOR_WAVELENGTHS_M:
            return _SENSOR_WAVELENGTHS_M[(sensor_norm, band_norm)]
        if (sensor_norm, None) in _SENSOR_WAVELENGTHS_M:
            return _SENSOR_WAVELENGTHS_M[(sensor_norm, None)]
        raise ValueError(
            f"Unsupported sensor '{sensor}'. Use wavelength_m explicitly or one of: "
            + ", ".join(list_supported_sensors())
        )

    if band_norm is not None:
        if band_norm in _GENERIC_BAND_WAVELENGTHS_M:
            return _GENERIC_BAND_WAVELENGTHS_M[band_norm]
        raise ValueError("band must be one of 'L', 'S', 'C', or 'X'.")

    raise ValueError(
        "Provide wavelength_m explicitly, or provide sensor, or provide band."
    )
