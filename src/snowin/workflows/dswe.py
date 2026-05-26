"""Raster-scale phase-to-dSWE conversion helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from snowin.snow import phase_to_dswe, sensor_wavelength_m
from snowin.utils import (
    angle_to_radians_if_needed,
    finite_fraction,
    validate_same_shape,
)

OutputUnit = Literal["m", "cm"]
IncidenceShapePolicy = Literal["fail", "median"]


@dataclass(frozen=True)
class DsweRasterResult:
    """Result from converting a phase raster to a dSWE raster."""

    dswe: np.ndarray
    unit: str
    method: str
    wavelength_m: float
    incidence_angle_unit_used: str
    valid_mask: np.ndarray
    diagnostics: dict[str, Any]


def phase_raster_to_dswe(
    phase_rad,
    incidence_angle,
    *,
    method: str = "oveisgharan",
    sensor: str | None = "nisar",
    band: str | None = "L",
    wavelength_m: float | None = None,
    incidence_angle_unit: str | None = "auto",
    snow_density_g_cm3=None,
    output_unit: OutputUnit = "cm",
    incidence_shape_policy: IncidenceShapePolicy = "fail",
) -> DsweRasterResult:
    """Convert unwrapped phase and incidence angle arrays to dSWE.

    This function performs only the physics/unit conversion. It does not apply
    quality masks, atmospheric corrections, reference-phase corrections,
    calibration, or clipping of negative values.
    """
    phase = np.asarray(phase_rad, dtype=float)
    incidence = np.asarray(incidence_angle, dtype=float)
    incidence_original_shape = tuple(incidence.shape)
    incidence_shape_handling = "same_shape"
    incidence_angle_median_used = None

    if incidence.shape != phase.shape:
        if incidence.size == 1:
            incidence_angle_median_used = float(np.asarray(incidence).reshape(-1)[0])
            incidence = np.full(phase.shape, incidence_angle_median_used, dtype=float)
            incidence_shape_handling = "scalar_expanded"
        elif incidence_shape_policy == "median":
            finite_incidence = incidence[np.isfinite(incidence)]
            if finite_incidence.size == 0:
                raise ValueError(
                    "incidence_angle shape does not match phase and has no finite "
                    "values for median expansion."
                )
            incidence_angle_median_used = float(np.nanmedian(finite_incidence))
            incidence = np.full(phase.shape, incidence_angle_median_used, dtype=float)
            incidence_shape_handling = "median_expanded_due_to_shape_mismatch"
        elif incidence_shape_policy == "fail":
            raise ValueError(
                "phase and incidence_angle shapes differ: "
                f"phase={phase.shape}, incidence_angle={incidence.shape}. "
                "Resample/interpolate incidence_angle onto the phase grid before "
                "science use, or explicitly set incidence_shape_policy='median' "
                "for a demo-only spatial-median approximation."
            )
        else:
            raise ValueError("incidence_shape_policy must be 'fail' or 'median'.")

    validate_same_shape(phase, incidence)

    incidence_rad, incidence_unit_used = angle_to_radians_if_needed(
        incidence, unit=incidence_angle_unit, name="incidence_angle"
    )
    resolved_wavelength = sensor_wavelength_m(
        sensor=sensor, band=band, wavelength_m=wavelength_m
    )

    dswe_m = np.asarray(
        phase_to_dswe(
            phase_rad=phase,
            method=method,
            incidence_angle_rad=incidence_rad,
            sensor=sensor,
            band=band,
            wavelength_m=wavelength_m,
            snow_density_g_cm3=snow_density_g_cm3,
        ),
        dtype=float,
    )

    if output_unit == "m":
        dswe = dswe_m
    elif output_unit == "cm":
        dswe = dswe_m * 100.0
    else:
        raise ValueError("output_unit must be 'm' or 'cm'.")

    valid_mask = np.isfinite(phase) & np.isfinite(incidence_rad) & np.isfinite(dswe)
    diagnostics = {
        "phase_finite_fraction": finite_fraction(phase),
        "incidence_finite_fraction": finite_fraction(incidence_rad),
        "dswe_finite_fraction": finite_fraction(dswe),
        "valid_fraction": finite_fraction(valid_mask.astype(float)),
        "output_unit": output_unit,
        "method": method,
        "sensor": sensor,
        "band": band,
        "wavelength_m": resolved_wavelength,
        "phase_shape": tuple(phase.shape),
        "incidence_original_shape": incidence_original_shape,
        "incidence_final_shape": tuple(incidence.shape),
        "incidence_shape_policy": incidence_shape_policy,
        "incidence_shape_handling": incidence_shape_handling,
        "incidence_angle_median_used": incidence_angle_median_used,
        "incidence_angle_unit_used": incidence_unit_used,
        "applied_quality_mask": False,
        "applied_atmospheric_corrections": False,
        "applied_reference_phase": False,
        "clipped_negative_values": False,
    }
    return DsweRasterResult(
        dswe=dswe,
        unit=output_unit,
        method=method,
        wavelength_m=resolved_wavelength,
        incidence_angle_unit_used=incidence_unit_used,
        valid_mask=valid_mask,
        diagnostics=diagnostics,
    )
