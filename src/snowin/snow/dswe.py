"""Canonical xarray-native phase-to-dSWE retrieval kernel.

The public function in this module accepts only SnowIn's canonical, already
normalized phase.  Product-specific phase conventions and wavelength metadata
belong at an adapter boundary, not in this scientific kernel.
"""

from __future__ import annotations

import math
from numbers import Real

import numpy as np
import xarray as xr

LEINSS_SNOW_PATH_CONSTANT = 1.59
"""Empirical dry-snow path constant in the Leinss approximation."""

CANONICAL_PHASE_DEFINITION = "secondary_minus_reference"
"""SnowIn's required normalized phase orientation."""

_VALID_ANGLE_UNITS = {"rad", "radian", "radians"}
_VALID_INCIDENCE_REFERENCES = {"ellipsoid", "local"}


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


def compute_dswe(
    phase: xr.DataArray,
    incidence_angle: xr.DataArray,
    *,
    wavelength_m: float,
    alpha: float = 1.0,
) -> xr.DataArray:
    r"""Compute pairwise dSWE from SnowIn canonical normalized phase.

    The implemented Leinss approximation is

    .. math::

       \Delta SWE = \frac{\Delta\Phi\,\lambda}
       {2\pi\,\alpha\,(1.59 + \theta^{5/2})}.

    ``phase`` must already be ``phi_secondary - phi_reference`` for the
    directed ``reference_time -> secondary_time`` edge.  The angle is the
    supplied radar incidence angle in radians; its ``incidence_angle_reference``
    attribute must identify whether it is local or ellipsoid-referenced.

    Parameters
    ----------
    phase
        Canonical unwrapped phase as an xarray.DataArray with ``units='rad'``.
    incidence_angle
        Aligned incidence angle DataArray with ``units='rad'`` and an
        ``incidence_angle_reference`` attribute equal to ``'local'`` or
        ``'ellipsoid'``.
    wavelength_m
        Radar wavelength in metres.  It is required explicitly; no sensor or
        mission default is used.
    alpha
        Dimensionless Leinss empirical path factor.  The usual approximation
        uses ``alpha=1``; calibrated values may be supplied explicitly.

    Returns
    -------
    xarray.DataArray
        Pairwise dSWE in metres water equivalent, with the phase dimensions,
        coordinates, missing values, and lazy backing preserved.

    Notes
    -----
    This function deliberately has no phase-sign or angle-unit switch.  Raw
    product phase normalization and unit conversion belong to adapters.
    """

    phase = _require_data_array("phase", phase)
    incidence_angle = _require_data_array("incidence_angle", incidence_angle)
    wavelength_m = _validate_positive_scalar("wavelength_m", wavelength_m)
    alpha = _validate_positive_scalar("alpha", alpha)

    _require_radians("phase", phase)
    _require_radians("incidence_angle", incidence_angle)
    incidence_reference = incidence_angle.attrs.get("incidence_angle_reference")
    if incidence_reference not in _VALID_INCIDENCE_REFERENCES:
        raise ValueError(
            "incidence_angle must declare incidence_angle_reference as "
            "'local' or 'ellipsoid'"
        )

    phase_definition = phase.attrs.get("phase_difference_definition")
    if phase_definition is not None and phase_definition != CANONICAL_PHASE_DEFINITION:
        raise ValueError(
            "phase must use SnowIn's canonical phase definition "
            "'secondary_minus_reference'"
        )

    _validate_alignment(phase, incidence_angle)
    _validate_eager_incidence_domain(incidence_angle)

    denominator = (
        2.0 * math.pi * alpha * (LEINSS_SNOW_PATH_CONSTANT + incidence_angle**2.5)
    )
    result = (phase * wavelength_m / denominator).rename("dswe")

    attrs = dict(phase.attrs)
    attrs.update(
        {
            "units": "m",
            "quantity": "pairwise_dSWE",
            "long_name": "pairwise change in snow water equivalent",
            "phase_difference_definition": CANONICAL_PHASE_DEFINITION,
            "incidence_angle_reference": incidence_reference,
            "wavelength_m": wavelength_m,
            "alpha": alpha,
            "snow_path_constant": LEINSS_SNOW_PATH_CONSTANT,
            "equation": (
                "dSWE = phase * wavelength_m / "
                "(2*pi*alpha*(1.59 + incidence_angle_rad**2.5))"
            ),
            "scientific_reference": "Leinss et al. (2015), Eq. 18",
        }
    )
    result.attrs = attrs
    return result
