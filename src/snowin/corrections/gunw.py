"""Explicit phase-correction helpers for NISAR GUNW workflows."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

import numpy as np

from snowin.utils import finite_fraction, validate_same_shape

CorrectionSign = Literal["subtract", "add"]


@dataclass(frozen=True)
class PhaseCorrectionConfig:
    """Configuration for optional phase-screen corrections.

    No correction sign is assumed. If a correction is requested, the sign must
    be supplied explicitly and recorded in provenance.
    """

    apply_ionosphere: bool = False
    ionosphere_sign: CorrectionSign | None = None
    apply_wet_tropo: bool = False
    wet_tropo_sign: CorrectionSign | None = None
    apply_hydro_tropo: bool = False
    hydro_tropo_sign: CorrectionSign | None = None
    remove_planar_ramp: bool = False


@dataclass(frozen=True)
class PhaseCorrectionResult:
    """Corrected phase and correction diagnostics."""

    phase_corrected: np.ndarray
    applied_terms: dict[str, np.ndarray]
    config: PhaseCorrectionConfig
    diagnostics: dict[str, Any]


def _apply_term(phase: np.ndarray, term: np.ndarray, sign: CorrectionSign, name: str) -> np.ndarray:
    validate_same_shape(phase, term)
    if sign == "subtract":
        return phase - term
    if sign == "add":
        return phase + term
    raise ValueError(f"{name}_sign must be 'subtract' or 'add'.")


def _stats(arr: np.ndarray, valid_mask: np.ndarray | None = None) -> dict[str, float | int]:
    data = np.asarray(arr, dtype=float)
    if valid_mask is not None:
        validate_same_shape(data, valid_mask)
        data = data[np.asarray(valid_mask, dtype=bool)]
    finite = data[np.isfinite(data)]
    if finite.size == 0:
        return {"valid_n": 0, "mean": np.nan, "std": np.nan, "min": np.nan, "max": np.nan}
    return {
        "valid_n": int(finite.size),
        "mean": float(np.nanmean(finite)),
        "std": float(np.nanstd(finite)),
        "min": float(np.nanmin(finite)),
        "max": float(np.nanmax(finite)),
    }


def apply_phase_corrections(
    phase_rad,
    *,
    ionosphere=None,
    wet_tropo=None,
    hydro_tropo=None,
    config: PhaseCorrectionConfig | None = None,
    valid_mask=None,
) -> PhaseCorrectionResult:
    """Apply explicitly configured phase corrections.

    The default leaves the phase unchanged. Requested corrections require both
    the correction layer and an explicit sign.
    """
    cfg = config or PhaseCorrectionConfig()
    phase = np.asarray(phase_rad, dtype=float)
    corrected = phase.copy()
    applied: dict[str, np.ndarray] = {}

    if valid_mask is not None:
        validate_same_shape(phase, np.asarray(valid_mask))

    requests = [
        ("ionosphere", cfg.apply_ionosphere, ionosphere, cfg.ionosphere_sign),
        ("wet_tropo", cfg.apply_wet_tropo, wet_tropo, cfg.wet_tropo_sign),
        ("hydro_tropo", cfg.apply_hydro_tropo, hydro_tropo, cfg.hydro_tropo_sign),
    ]
    for name, apply, term, sign in requests:
        if not apply:
            continue
        if term is None:
            raise ValueError(f"{name} correction requested but no {name} layer was provided.")
        if sign is None:
            raise ValueError(f"{name} correction requested but no explicit sign was provided.")
        term_arr = np.asarray(term, dtype=float)
        corrected = _apply_term(corrected, term_arr, sign, name)
        applied[name] = term_arr

    if cfg.remove_planar_ramp:
        raise NotImplementedError("Planar ramp removal is reserved for a later tested implementation.")

    diagnostics: dict[str, Any] = {
        "config": asdict(cfg),
        "phase_raw_finite_fraction": finite_fraction(phase),
        "phase_corrected_finite_fraction": finite_fraction(corrected),
        "applied_terms": tuple(applied.keys()),
    }
    for name, term in applied.items():
        diagnostics[f"{name}_stats"] = _stats(term, valid_mask)
    diagnostics["phase_corrected_stats"] = _stats(corrected, valid_mask)

    return PhaseCorrectionResult(
        phase_corrected=corrected,
        applied_terms=applied,
        config=cfg,
        diagnostics=diagnostics,
    )
