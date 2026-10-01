"""Named xarray-native phase-to-dSWE retrieval methods.

The public functions accept SnowIn's canonical, already normalized phase.
Product-specific phase conventions belong at an adapter boundary. Wavelength
is supplied explicitly or resolved from authoritative product metadata.
"""

from __future__ import annotations

import math
from numbers import Real
from typing import Literal

import numpy as np
import xarray as xr

LEINSS_SNOW_PATH_CONSTANT = 1.59
"""Empirical dry-snow path constant in the Leinss approximation."""

CANONICAL_PHASE_DEFINITION = "secondary_minus_reference"
"""SnowIn's required normalized phase orientation."""

_VALID_ANGLE_UNITS = {"rad", "radian", "radians"}
_VALID_INCIDENCE_REFERENCES = {"ellipsoid", "local"}
_VALID_DENSITY_UNITS = {"kg m-3", "kg/m3", "kg/m^3", "kg m^-3"}
DensityPermittivityModel = Literal["guneriussen2001", "webb2021", "maetzler"]

GUNERIUSSEN_WATER_DENSITY_KG_M3 = 1000.0
"""Stock water density used to convert snow-depth change to dSWE."""

OVEISGHARAN_A_THETA_COEFFICIENTS = (-0.6784, 0.2899, -0.8473)
"""Published Oveisgharan et al. (2024) polynomial coefficients, highest order first."""


def _validate_positive_scalar(name: str, value: object) -> float:
    if not isinstance(value, Real):
        raise TypeError(f"{name} must be a finite positive scalar in SI units")
    value_float = float(value)
    if not math.isfinite(value_float) or value_float <= 0.0:
        raise ValueError(f"{name} must be finite and > 0")
    return value_float


def _require_data_array(name: str, value: object) -> xr.DataArray:
    if not isinstance(value, xr.DataArray):
        raise TypeError(
            f"{name} must be an xarray.DataArray with explicit units; "
            "wrap scalar or NumPy inputs in a DataArray"
        )
    return value


def _require_radians(name: str, value: xr.DataArray) -> None:
    units = value.attrs.get("units")
    if units not in _VALID_ANGLE_UNITS:
        if units is None:
            detail = "units metadata is missing"
        else:
            detail = f"units={units!r} is not radians"
        raise ValueError(f"{name} has invalid or ambiguous angle units: {detail}")


def _validate_alignment(phase: xr.DataArray, incidence_angle: xr.DataArray) -> None:
    if phase.dims != incidence_angle.dims or phase.sizes != incidence_angle.sizes:
        raise ValueError(
            "phase and incidence_angle must have identical dimensions and sizes; "
            "align or resample them at an adapter boundary"
        )

    for dim in phase.dims:
        phase_coord = phase.coords.get(dim)
        incidence_coord = incidence_angle.coords.get(dim)
        if phase_coord is None or incidence_coord is None:
            if phase_coord is not None or incidence_coord is not None:
                raise ValueError(
                    f"phase and incidence_angle have mismatched coordinate metadata for {dim!r}"
                )
        elif not phase_coord.equals(incidence_coord):
            raise ValueError(
                f"phase and incidence_angle coordinates differ for dimension {dim!r}"
            )


def _validate_eager_incidence_domain(incidence_angle: xr.DataArray) -> None:
    """Validate eager angle values without computing a lazy array.

    Dask-backed incidence arrays are intentionally left lazy.  Their metadata
    is validated here and their values are evaluated only when the caller
    computes the returned DataArray.
    """

    data = incidence_angle.data
    if hasattr(data, "chunks"):
        return

    try:
        values = np.asarray(data, dtype=float)
    except (TypeError, ValueError) as exc:
        raise TypeError("incidence_angle must contain numeric radians") from exc

    invalid = np.isinf(values) | (values < 0.0) | (values >= math.pi / 2.0)
    if np.any(invalid):
        raise ValueError("incidence_angle values must be in [0, pi/2); NaN is allowed")


def _validate_common_inputs(
    phase: xr.DataArray,
    incidence_angle: xr.DataArray,
    wavelength_m: float,
) -> tuple[xr.DataArray, xr.DataArray, float, str, str]:
    phase = _require_data_array("phase", phase)
    incidence_angle = _require_data_array("incidence_angle", incidence_angle)
    _require_radians("phase", phase)
    _require_radians("incidence_angle", incidence_angle)

    incidence_reference = incidence_angle.attrs.get("incidence_angle_reference")
    if incidence_reference not in _VALID_INCIDENCE_REFERENCES:
        raise ValueError(
            "incidence_angle must declare incidence_angle_reference as "
            "'local' or 'ellipsoid'"
        )

    phase_definition = phase.attrs.get("phase_difference_definition")
    if phase_definition != CANONICAL_PHASE_DEFINITION:
        raise ValueError(
            "phase must use SnowIn's canonical phase definition "
            "'secondary_minus_reference'"
        )

    _validate_alignment(phase, incidence_angle)
    _validate_eager_incidence_domain(incidence_angle)
    resolved_wavelength = _validate_positive_scalar("wavelength_m", wavelength_m)
    wavelength_source = "explicit wavelength_m"
    return (
        phase,
        incidence_angle,
        _validate_positive_scalar("wavelength_m", resolved_wavelength),
        incidence_reference,
        wavelength_source,
    )


def _validate_density(
    phase: xr.DataArray, snow_density_kg_m3: xr.DataArray | Real
) -> xr.DataArray:
    if isinstance(snow_density_kg_m3, xr.DataArray):
        density = snow_density_kg_m3
        units = density.attrs.get("units")
        if units not in _VALID_DENSITY_UNITS:
            raise ValueError("snow_density_kg_m3 DataArray must declare units='kg m-3'")
        if density.ndim == 0:
            density = density.broadcast_like(phase)
        else:
            _validate_alignment(phase, density)
    else:
        density_value = _validate_positive_scalar(
            "snow_density_kg_m3", snow_density_kg_m3
        )
        density = xr.full_like(phase, density_value, dtype=float)

    data = density.data
    if not hasattr(data, "chunks"):
        try:
            values = np.asarray(data, dtype=float)
        except (TypeError, ValueError) as exc:
            raise TypeError("snow_density_kg_m3 must contain numeric values") from exc
        invalid = np.isinf(values) | (values <= 0.0) | (values >= 917.0)
        if np.any(invalid):
            raise ValueError(
                "snow_density_kg_m3 values must be in (0, 917); NaN is allowed"
            )
    density = density.copy(deep=False).rename("snow_density")
    density.attrs = {"units": "kg m-3"}
    return density


def _result(
    source_phase: xr.DataArray,
    dswe: xr.DataArray,
    incidence_reference: str,
    wavelength_m: float,
    wavelength_source: str,
    *,
    method: str,
    equation: str,
    scientific_reference: str,
    method_attrs: dict[str, object] | None = None,
) -> xr.DataArray:
    result = dswe.rename("dswe")
    attrs = dict(source_phase.attrs)
    attrs.update(
        {
            "units": "m",
            "quantity": "pairwise_dSWE",
            "long_name": "pairwise change in snow water equivalent",
            "phase_difference_definition": CANONICAL_PHASE_DEFINITION,
            "incidence_angle_reference": incidence_reference,
            "wavelength_m": wavelength_m,
            "wavelength_source": wavelength_source,
            "retrieval_method": method,
            "equation": equation,
            "scientific_reference": scientific_reference,
        }
    )
    if method_attrs:
        attrs.update(method_attrs)
    result.attrs = attrs
    return result


def compute_leinss_dswe(
    phase: xr.DataArray,
    incidence_angle: xr.DataArray,
    *,
    wavelength_m: float,
    alpha: float = 1.0,
) -> xr.DataArray:
    r"""Compute pairwise dSWE with the Leinss et al. approximation.

    ``phase`` must be SnowIn's normalized secondary-minus-reference phase in
    radians. ``incidence_angle`` must be aligned radians and declare whether it
    is local or ellipsoid-referenced. Supply wavelength explicitly in metres.

    The stock values are ``alpha=1`` and the empirical path constant ``1.59``.
    Product adapters should resolve wavelength from authoritative metadata.
    """
    phase, incidence_angle, wavelength_m, incidence_reference, wavelength_source = (
        _validate_common_inputs(
            phase,
            incidence_angle,
            wavelength_m,
        )
    )
    alpha = _validate_positive_scalar("alpha", alpha)
    dswe = (
        phase
        * wavelength_m
        / (2.0 * math.pi * alpha * (LEINSS_SNOW_PATH_CONSTANT + incidence_angle**2.5))
    )
    result = _result(
        phase,
        dswe,
        incidence_reference,
        wavelength_m,
        wavelength_source,
        method="leinss",
        equation=(
            "dSWE = phase * wavelength_m / "
            "(2*pi*alpha*(1.59 + incidence_angle_rad**2.5))"
        ),
        scientific_reference="Leinss et al. (2015), Eq. 18",
        method_attrs={"alpha": alpha, "snow_path_constant": LEINSS_SNOW_PATH_CONSTANT},
    )
    return result


def compute_guneriussen_dswe(
    phase: xr.DataArray,
    incidence_angle: xr.DataArray,
    *,
    snow_density_kg_m3: xr.DataArray | Real,
    wavelength_m: float,
    permittivity_model: DensityPermittivityModel = "guneriussen2001",
) -> xr.DataArray:
    r"""Compute pairwise dSWE with the density-dependent Guneriussen model.

    Snow density is required because the phase response depends on both snow
    permittivity and the snow-to-water density ratio. Scalar density values use
    kg m-3; a density DataArray must be aligned with ``phase`` and declare
    ``units='kg m-3'``. The stock density-to-permittivity model is
    ``guneriussen2001``; alternatives are ``webb2021`` and ``maetzler``.

    The published conversion uses water density 1000 kg m-3. Wavelength is
    supplied explicitly in metres.
    """
    phase, incidence_angle, wavelength_m, incidence_reference, wavelength_source = (
        _validate_common_inputs(
            phase,
            incidence_angle,
            wavelength_m,
        )
    )
    if permittivity_model not in {"guneriussen2001", "webb2021", "maetzler"}:
        raise ValueError(
            "permittivity_model must be 'guneriussen2001', 'webb2021', or 'maetzler'"
        )

    density = _validate_density(phase, snow_density_kg_m3)
    density_g_cm3 = density / 1000.0
    if permittivity_model == "guneriussen2001":
        permittivity = 1.0 + 1.6 * density_g_cm3 + 1.8 * density_g_cm3**3
        permittivity_reference = "Guneriussen et al. (2001), Eq. 7"
    elif permittivity_model == "webb2021":
        permittivity = 1.0 + 0.0014 * density + 2.0e-7 * density**2
        permittivity_reference = "Webb et al. (2021)"
    else:
        permittivity = xr.where(
            density_g_cm3 < 0.4,
            1.0 + 1.5995 * density_g_cm3 + 1.861 * density_g_cm3**3,
            ((1.0 - density_g_cm3 / 0.917) + 1.4759 * (density_g_cm3 / 0.917)) ** 3,
        )
        permittivity_reference = "Mätzler dry-snow permittivity model"

    theta = incidence_angle
    refraction = np.cos(theta) - np.sqrt(permittivity - np.sin(theta) ** 2)
    kappa = 2.0 * math.pi / wavelength_m
    density_ratio = density / GUNERIUSSEN_WATER_DENSITY_KG_M3
    dswe = phase / (-2.0 * kappa * refraction * density_ratio)
    density_source = (
        f"DataArray:{snow_density_kg_m3.name or 'snow_density'}"
        if isinstance(snow_density_kg_m3, xr.DataArray)
        else "scalar parameter"
    )
    method_attrs: dict[str, object] = {
        "snow_density_source": density_source,
        "snow_density_units": "kg m-3",
        "water_density_kg_m3": GUNERIUSSEN_WATER_DENSITY_KG_M3,
        "permittivity_model": permittivity_model,
    }
    if not isinstance(snow_density_kg_m3, xr.DataArray):
        method_attrs["snow_density_kg_m3"] = float(snow_density_kg_m3)
    return _result(
        phase,
        dswe,
        incidence_reference,
        wavelength_m,
        wavelength_source,
        method="guneriussen",
        equation=(
            "dSWE = phase / (-2*kappa*(cos(theta)-sqrt(epsilon-sin(theta)^2))"
            "*(snow_density_kg_m3/1000)); kappa=2*pi/wavelength_m"
        ),
        scientific_reference=("Guneriussen et al. (2001); " + permittivity_reference),
        method_attrs=method_attrs,
    )


def compute_oveisgharan_dswe(
    phase: xr.DataArray,
    incidence_angle: xr.DataArray,
    *,
    wavelength_m: float,
) -> xr.DataArray:
    r"""Compute pairwise dSWE with the Oveisgharan et al. fitted model.

    This density-independent method uses the published incidence polynomial;
    it has no snow-density or Leinss ``alpha`` parameter. Supply a wavelength
    explicitly in metres.
    """
    phase, incidence_angle, wavelength_m, incidence_reference, wavelength_source = (
        _validate_common_inputs(
            phase,
            incidence_angle,
            wavelength_m,
        )
    )
    c2, c1, c0 = OVEISGHARAN_A_THETA_COEFFICIENTS
    a_theta = c2 * incidence_angle**2 + c1 * incidence_angle + c0
    kappa = 2.0 * math.pi / wavelength_m
    dswe = phase / (-2.0 * kappa * a_theta)
    return _result(
        phase,
        dswe,
        incidence_reference,
        wavelength_m,
        wavelength_source,
        method="oveisgharan",
        equation=(
            "dSWE = phase / (-2*kappa*A(theta)); "
            "A(theta)=-0.6784*theta**2+0.2899*theta-0.8473; "
            "kappa=2*pi/wavelength_m"
        ),
        scientific_reference="Oveisgharan et al. (2024)",
        method_attrs={"a_theta_coefficients": list(OVEISGHARAN_A_THETA_COEFFICIENTS)},
    )
