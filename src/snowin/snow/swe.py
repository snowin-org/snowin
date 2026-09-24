"""Legacy NumPy dry-snow phase-to-dSWE relationships.

The stable xarray-native methods live in :mod:`snowin.snow.dswe`; the
``compute_dswe`` spelling is retained as the Leinss compatibility alias.
``phase_to_dswe`` remains for characterization and compatibility with the
Stage 0/1 prototype. Its method dispatcher and permissive NumPy inputs are not
the normalized SnowIn contract.

Scientific scope
----------------
These relationships are for dry-snow phase-based retrievals of *change* in
snow water equivalent (dSWE), not absolute SWE.

Units
-----
- phase_rad: radians
- incidence_angle_rad: radians
- wavelength_m: meters
- snow_density_g_cm3: g / cm^3
- returned dSWE: meters of water equivalent
"""

from __future__ import annotations

import math
from typing import Literal

import numpy as np

ArrayLike = float | int | np.ndarray
MethodName = Literal["guneriussen", "leinss", "oveisgharan"]
BandName = Literal["L", "S", "C", "X"]

# -----------------------------------------------------------------------------
# Sensor registry
# -----------------------------------------------------------------------------

RHO_WATER_G_CM3 = 1.0

# Wavelengths in meters. Named xarray methods consult this registry only when
# callers explicitly choose a sensor or band; they never infer the mission.
_SENSOR_WAVELENGTHS_M: dict[tuple[str, str | None], float] = {
    # NISAR dual-band mission
    ("nisar", "L"): 0.24,
    ("nisar", "S"): 0.10,
    # ESA Sentinel-1
    ("sentinel1", None): 0.05546668973172988,
    ("s1", None): 0.05546668973172988,
    # JPL airborne
    ("uavsar", None): 0.23840354572564613,
    # DLR X-band
    ("terrasarx", None): 0.031066576994818654,
    ("tsx", None): 0.031066576994818654,
    ("tandemx", None): 0.031066576994818654,
    ("tdx", None): 0.031066576994818654,
    # RADARSAT family
    ("radarsat1", None): 0.05656461471698113,
    ("radarsat2", None): 0.05546668973172988,
    ("radarsat", None): 0.05546668973172988,
    ("rcm", None): 0.05546668973172988,
    # JAXA L-band family
    ("alos_palsar", None): 0.23605626614173228,
    ("palsar", None): 0.23605626614173228,
    ("alos2_palsar2", None): 0.24982704833333335,
    ("palsar2", None): 0.24982704833333335,
    # CONAE
    ("saocom", None): 0.23513133960784314,
    # Historical/common C-band missions
    ("ers1", None): 0.05656461471698113,
    ("ers2", None): 0.05656461471698113,
    ("envisat_asar", None): 0.05623474812474207,
    ("asar", None): 0.05623474812474207,
}

# Generic band-only fallbacks for convenience. Mission-specific values are
# preferred whenever available.
_GENERIC_BAND_WAVELENGTHS_M: dict[str, float] = {
    "L": 0.24,
    "S": 0.10,
    "C": 0.05546668973172988,
    "X": 0.031066576994818654,
}


def list_supported_sensors() -> list[str]:
    """Return sorted supported sensor names."""
    return sorted({sensor for sensor, _ in _SENSOR_WAVELENGTHS_M})


# -----------------------------------------------------------------------------
# Validation/helpers
# -----------------------------------------------------------------------------


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
    """
    Resolve wavelength in meters.

    Resolution order:
    1. explicit `wavelength_m` (always wins)
    2. sensor-specific lookup, using `band` if required
    3. generic band lookup

    Parameters
    ----------
    sensor
        Sensor/mission name, e.g. "nisar", "s1", "uavsar", "terrasarx".
    band
        Optional band for multi-band missions, especially NISAR ("L" or "S").
    wavelength_m
        Explicit wavelength override in meters.

    Returns
    -------
    float
        Wavelength in meters.
    """
    if wavelength_m is not None:
        _validate_positive("wavelength_m", wavelength_m)
        return float(wavelength_m)

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


def incidence_wavenumber(wavelength_m: float) -> float:
    """Return radar wavenumber κ = 2π / λ in m^-1."""
    _validate_positive("wavelength_m", wavelength_m)
    return 2.0 * math.pi / float(wavelength_m)


# -----------------------------------------------------------------------------
# Physics helpers
# -----------------------------------------------------------------------------


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
    """
    _validate_incidence_angle_rad(incidence_angle_rad)
    _validate_density_g_cm3(snow_density_g_cm3)

    theta = _as_array(incidence_angle_rad)
    eps = _as_array(maetzler_permittivity(snow_density_g_cm3))
    term = np.cos(theta) - np.sqrt(eps - np.sin(theta) ** 2)
    return _return_scalar_if_scalar(incidence_angle_rad, term)


def leinss_a_theta(incidence_angle_rad: ArrayLike) -> ArrayLike:
    """
    Legacy compatibility alias for :func:`oveisgharan_a_theta`.

    This historical helper name is retained only so the prototype API remains
    characterizable.  The polynomial is the Oveisgharan approximation, not the
    Leinss path-constant approximation used by the canonical Stage 2 kernel.

    """
    return oveisgharan_a_theta(incidence_angle_rad)


def oveisgharan_a_theta(incidence_angle_rad: ArrayLike) -> ArrayLike:
    """Return the Oveisgharan et al. (2024) fitted ``A(theta)`` polynomial.

    Notes
    -----
    This implementation assumes `incidence_angle_rad` is in radians, matching
    the rest of the module.
    """
    _validate_incidence_angle_rad(incidence_angle_rad)
    theta = _as_array(incidence_angle_rad)
    a = -0.6784 * theta**2 + 0.2899 * theta - 0.8473
    return _return_scalar_if_scalar(incidence_angle_rad, a)


# -----------------------------------------------------------------------------
# Internal method implementations
# -----------------------------------------------------------------------------


def _phase_to_dswe_guneriussen(
    phase_rad: ArrayLike,
    wavelength_m: float,
    incidence_angle_rad: ArrayLike,
    snow_density_g_cm3: ArrayLike,
) -> ArrayLike:
    """
    Exact density-dependent relation:

        dphi = -2 * kappa * C(theta, rho) * (rho / rho_water) * dSWE
    """
    _validate_positive("wavelength_m", wavelength_m)
    _validate_incidence_angle_rad(incidence_angle_rad)
    _validate_density_g_cm3(snow_density_g_cm3)

    phase = _as_array(phase_rad)
    theta = _as_array(incidence_angle_rad)
    rho = _as_array(snow_density_g_cm3)

    kappa = incidence_wavenumber(wavelength_m)
    c_term = _as_array(refraction_term(theta, rho))
    denom = -2.0 * kappa * c_term * (rho / RHO_WATER_G_CM3)
    dswe = phase / denom
    return _return_scalar_if_scalar(phase_rad, dswe)


def _phase_to_dswe_leinss(
    phase_rad: ArrayLike,
    wavelength_m: float,
    incidence_angle_rad: ArrayLike,
    alpha: float = 1.0,
) -> ArrayLike:
    """
    Leinss density-independent approximation:

        dphi = kappa * alpha * (1.59 + theta**2.5) * dSWE
    """
    _validate_positive("wavelength_m", wavelength_m)
    _validate_positive("alpha", alpha)
    _validate_incidence_angle_rad(incidence_angle_rad)

    phase = _as_array(phase_rad)
    theta = _as_array(incidence_angle_rad)
    kappa = incidence_wavenumber(wavelength_m)
    dswe = phase / (kappa * alpha * (1.59 + theta**2.5))
    return _return_scalar_if_scalar(phase_rad, dswe)


def _phase_to_dswe_oveisgharan(
    phase_rad: ArrayLike,
    wavelength_m: float,
    incidence_angle_rad: ArrayLike,
    alpha: float = 1.0,
) -> ArrayLike:
    """
    Oveisgharan et al. (2024) density-independent approximation.

        dphi = -2 * kappa * A(theta) * dSWE

    The optional ``alpha`` is retained for a uniform legacy call signature but
    is not part of the Oveisgharan fit and must remain its default value.
    """
    _validate_positive("wavelength_m", wavelength_m)
    if alpha != 1.0:
        raise ValueError("alpha is not a parameter of the Oveisgharan fit")
    _validate_incidence_angle_rad(incidence_angle_rad)

    phase = _as_array(phase_rad)
    theta = _as_array(incidence_angle_rad)
    kappa = incidence_wavenumber(wavelength_m)
    a = _as_array(oveisgharan_a_theta(theta))
    dswe = phase / (-2.0 * kappa * a)
    return _return_scalar_if_scalar(phase_rad, dswe)


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------


def phase_to_dswe(
    phase_rad: ArrayLike,
    method: MethodName,
    incidence_angle_rad: ArrayLike,
    *,
    sensor: str | None = None,
    band: str | None = None,
    wavelength_m: float | None = None,
    snow_density_g_cm3: ArrayLike | None = None,
    alpha: float = 1.0,
) -> ArrayLike:
    """
    Convert interferometric phase change to dry-snow dSWE (legacy API).

    Use :func:`snowin.snow.compute_dswe` for new code.  This compatibility
    function retains the prototype's sensor/band wavelength resolution and
    method selector; it is not the canonical normalized SnowIn API.

    Parameters
    ----------
    phase_rad
        Interferometric phase change in radians.
    method
        One of: "guneriussen", "leinss", "oveisgharan".
    incidence_angle_rad
        Incidence angle in radians.
    sensor
        Optional mission/sensor name, e.g. "nisar", "s1", "uavsar", "terrasarx".
    band
        Optional band, mainly needed for multi-band missions such as NISAR.
    wavelength_m
        Explicit wavelength override in meters. If provided, it overrides
        sensor/band defaults.
    snow_density_g_cm3
        Required for method="guneriussen". Ignored by density-independent methods.
    alpha
        Legacy Leinss empirical path factor.  It is ignored for Guneriussen and
        must remain 1 for the Oveisgharan fit.

    Returns
    -------
    ArrayLike
        dSWE in meters of water equivalent.
    """
    resolved_wavelength_m = sensor_wavelength_m(
        sensor=sensor,
        band=band,
        wavelength_m=wavelength_m,
    )

    if method == "guneriussen":
        if snow_density_g_cm3 is None:
            raise ValueError(
                "snow_density_g_cm3 is required when method='guneriussen'."
            )
        return _phase_to_dswe_guneriussen(
            phase_rad=phase_rad,
            wavelength_m=resolved_wavelength_m,
            incidence_angle_rad=incidence_angle_rad,
            snow_density_g_cm3=snow_density_g_cm3,
        )

    if method == "leinss":
        return _phase_to_dswe_leinss(
            phase_rad=phase_rad,
            wavelength_m=resolved_wavelength_m,
            incidence_angle_rad=incidence_angle_rad,
            alpha=alpha,
        )

    if method == "oveisgharan":
        return _phase_to_dswe_oveisgharan(
            phase_rad=phase_rad,
            wavelength_m=resolved_wavelength_m,
            incidence_angle_rad=incidence_angle_rad,
            alpha=alpha,
        )

    raise ValueError("method must be one of: 'guneriussen', 'leinss', 'oveisgharan'.")


def cm_to_m(value_cm: ArrayLike) -> ArrayLike:
    """Convert centimeters to meters."""
    arr = _as_array(value_cm) / 100.0
    return _return_scalar_if_scalar(value_cm, arr)


def m_to_cm(value_m: ArrayLike) -> ArrayLike:
    """Convert meters to centimeters."""
    arr = _as_array(value_m) * 100.0
    return _return_scalar_if_scalar(value_m, arr)
