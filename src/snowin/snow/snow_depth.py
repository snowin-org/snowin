"""
Core dry-snow phase-to-snow-depth relationships for SnowIn.

This module mirrors the API style of `swe.py`, but it is intentionally narrower:
it focuses on the Guneriussen-style exact dry-snow phase/depth relation.

Why only Guneriussen here?
--------------------------
Guneriussen et al. (2001) derives the phase change in terms of snow-depth change
and snow permittivity/density. By contrast, the Leinss/Oveisgharan-style forms
are convenient approximations for *change in SWE* rather than direct snow-depth
retrieval. Those methods belong in the dSWE module, not here.

Scientific scope
----------------
These relationships are for dry-snow phase-based retrievals of *change* in snow
depth, not absolute snow depth.

Units
-----
- phase_rad: radians
- incidence_angle_rad: radians
- wavelength_m: meters
- snow_density_g_cm3: g / cm^3
- returned snow-depth change: meters
"""

from __future__ import annotations

import math
from typing import Union

import numpy as np

ArrayLike = Union[float, int, np.ndarray]

RHO_WATER_G_CM3 = 1.0

# Wavelengths in meters.
_SENSOR_WAVELENGTHS_M: dict[tuple[str, str | None], float] = {
    ("nisar", None): 0.24,
    ("nisar", "S"): 0.10,
    ("sentinel1", None): 0.05546668973172988,
    ("s1", None): 0.05546668973172988,
    ("uavsar", None): 0.23840354572564613,
}

_GENERIC_BAND_WAVELENGTHS_M: dict[str, float] = {
    "L": 0.24,
    "S": 0.10,
    "C": 0.05546668973172988,
    "X": 0.031066576994818654,
}


def list_supported_sensors() -> list[str]:
    """Return sorted supported sensor names."""
    return sorted({sensor for sensor, _ in _SENSOR_WAVELENGTHS_M.keys()})


def _as_array(value: ArrayLike) -> np.ndarray:
    return np.asarray(value, dtype=float)


def _return_scalar_if_scalar(original: ArrayLike, arr: np.ndarray) -> ArrayLike:
    if np.isscalar(original):
        return float(np.asarray(arr))
    return arr


def _validate_positive(name: str, value: ArrayLike) -> None:
    arr = _as_array(value)
    if np.any(arr <= 0):
        raise ValueError(f"{name} must be > 0.")


def _validate_density_g_cm3(density_g_cm3: ArrayLike) -> None:
    density = _as_array(density_g_cm3)
    if np.any((density <= 0) | (density >= 0.917)):
        raise ValueError("snow_density_g_cm3 must be between 0 and 0.917 g/cm^3.")


def _validate_incidence_angle_rad(theta_rad: ArrayLike) -> None:
    theta = _as_array(theta_rad)
    if np.any((theta < 0) | (theta >= (math.pi / 2))):
        raise ValueError("incidence_angle_rad must be in [0, pi/2).")


def sensor_wavelength_m(
    sensor: str | None = None,
    band: str | None = None,
    wavelength_m: float | None = None,
) -> float:
    """Resolve wavelength in meters."""
    if wavelength_m is not None:
        _validate_positive("wavelength_m", wavelength_m)
        return float(wavelength_m)

    band_norm = band.upper() if band is not None else None
    sensor_norm = sensor.lower() if sensor is not None else None

    if sensor_norm is not None:
        if sensor_norm == "nisar" and band_norm is None:
            raise ValueError("band is required when sensor='nisar'. Use band='L' or band='S'.")

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

    raise ValueError("Provide wavelength_m explicitly, or provide sensor, or provide band.")


def incidence_wavenumber(wavelength_m: float) -> float:
    """Return radar wavenumber κ = 2π / λ in m^-1."""
    _validate_positive("wavelength_m", wavelength_m)
    return 2.0 * math.pi / float(wavelength_m)


def maetzler_permittivity(snow_density_g_cm3: ArrayLike) -> ArrayLike:
    """
    Dry-snow permittivity using the piecewise Mätzler model quoted in
    Oveisgharan et al. (2024).
    """
    _validate_density_g_cm3(snow_density_g_cm3)
    rho = _as_array(snow_density_g_cm3)

    epsilon = np.where(
        rho < 0.4,
        1.0 + 1.5995 * rho + 1.861 * rho**3,
        ((1.0 - rho / 0.917) + 1.4759 * (rho / 0.917)) ** 3,
    )
    return _return_scalar_if_scalar(snow_density_g_cm3, epsilon)


def refraction_term(
    incidence_angle_rad: ArrayLike,
    snow_density_g_cm3: ArrayLike,
) -> ArrayLike:
    """
    Return C(theta, rho) = cos(theta) - sqrt(epsilon - sin(theta)^2).

    In the Guneriussen-style depth relation:
        dphi = -2 * kappa * C(theta, rho) * d_depth
    """
    _validate_incidence_angle_rad(incidence_angle_rad)
    _validate_density_g_cm3(snow_density_g_cm3)

    theta = _as_array(incidence_angle_rad)
    eps = _as_array(maetzler_permittivity(snow_density_g_cm3))
    term = np.cos(theta) - np.sqrt(eps - np.sin(theta) ** 2)
    return _return_scalar_if_scalar(incidence_angle_rad, term)


def phase_to_snow_depth_change(
    phase_rad: ArrayLike,
    incidence_angle_rad: ArrayLike,
    *,
    sensor: str | None = None,
    band: str | None = None,
    wavelength_m: float | None = None,
    snow_density_g_cm3: ArrayLike,
) -> ArrayLike:
    """
    Convert interferometric phase change to dry-snow depth change.

    Uses the exact Guneriussen-style dry-snow depth relation:
        dphi = -2 * kappa * C(theta, rho) * d_depth

    Parameters
    ----------
    phase_rad
        Interferometric phase change in radians.
    incidence_angle_rad
        Incidence angle in radians.
    sensor
        Optional mission/sensor name, e.g. "nisar", "s1", "uavsar".
    band
        Optional band, mainly needed for multi-band missions such as NISAR.
    wavelength_m
        Explicit wavelength override in meters. If provided, it overrides
        sensor/band defaults.
    snow_density_g_cm3
        Dry-snow density in g/cm^3, used to compute permittivity.

    Returns
    -------
    ArrayLike
        Snow-depth change in meters.
    """
    resolved_wavelength_m = sensor_wavelength_m(
        sensor=sensor,
        band=band,
        wavelength_m=wavelength_m,
    )
    _validate_density_g_cm3(snow_density_g_cm3)
    _validate_incidence_angle_rad(incidence_angle_rad)

    phase = _as_array(phase_rad)
    theta = _as_array(incidence_angle_rad)
    kappa = incidence_wavenumber(resolved_wavelength_m)
    c_term = _as_array(refraction_term(theta, snow_density_g_cm3))

    depth_change_m = phase / (-2.0 * kappa * c_term)
    return _return_scalar_if_scalar(phase_rad, depth_change_m)


def snow_depth_change_to_phase(
    snow_depth_change_m: ArrayLike,
    incidence_angle_rad: ArrayLike,
    *,
    sensor: str | None = None,
    band: str | None = None,
    wavelength_m: float | None = None,
    snow_density_g_cm3: ArrayLike,
) -> ArrayLike:
    """
    Forward model: convert dry-snow depth change to interferometric phase change.

    Uses:
        dphi = -2 * kappa * C(theta, rho) * d_depth
    """
    resolved_wavelength_m = sensor_wavelength_m(
        sensor=sensor,
        band=band,
        wavelength_m=wavelength_m,
    )
    _validate_density_g_cm3(snow_density_g_cm3)
    _validate_incidence_angle_rad(incidence_angle_rad)

    depth_change_m = _as_array(snow_depth_change_m)
    theta = _as_array(incidence_angle_rad)
    kappa = incidence_wavenumber(resolved_wavelength_m)
    c_term = _as_array(refraction_term(theta, snow_density_g_cm3))

    phase = -2.0 * kappa * c_term * depth_change_m
    return _return_scalar_if_scalar(snow_depth_change_m, phase)


def cm_to_m(value_cm: ArrayLike) -> ArrayLike:
    """Convert centimeters to meters."""
    arr = _as_array(value_cm) / 100.0
    return _return_scalar_if_scalar(value_cm, arr)


def m_to_cm(value_m: ArrayLike) -> ArrayLike:
    """Convert meters to centimeters."""
    arr = _as_array(value_m) * 100.0
    return _return_scalar_if_scalar(value_m, arr)
