"""Reference-phase strategies for InSAR snow workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from snowin.utils import validate_same_shape

ReferenceStrategy = Literal["none", "median_valid", "low_snow_mask", "user_mask"]


@dataclass(frozen=True)
class ReferencePhaseResult:
    """Phase after applying a reference-phase strategy."""

    phase_referenced: np.ndarray
    reference_value_rad: float | None
    strategy: str
    diagnostics: dict[str, Any]


def apply_reference_phase(
    phase_rad,
    *,
    strategy: ReferenceStrategy = "none",
    valid_mask=None,
    reference_mask=None,
) -> ReferencePhaseResult:
    """Apply an explicit reference-phase strategy.

    Whole-domain median referencing is available as ``median_valid`` for
    diagnostics, but science workflows should not use it as an implicit default.
    """
    phase = np.asarray(phase_rad, dtype=float)
    base_valid = np.isfinite(phase)
    if valid_mask is not None:
        validate_same_shape(phase, np.asarray(valid_mask))
        base_valid &= np.asarray(valid_mask, dtype=bool)

    if strategy == "none":
        return ReferencePhaseResult(
            phase_referenced=phase.copy(),
            reference_value_rad=None,
            strategy=strategy,
            diagnostics={"strategy": strategy, "reference_pixels": 0},
        )

    if strategy == "median_valid":
        ref_pixels = base_valid
    elif strategy in {"low_snow_mask", "user_mask"}:
        if reference_mask is None:
            raise ValueError(f"strategy='{strategy}' requires reference_mask.")
        ref_mask = np.asarray(reference_mask, dtype=bool)
        validate_same_shape(phase, ref_mask)
        ref_pixels = base_valid & ref_mask
    else:
        raise ValueError("strategy must be 'none', 'median_valid', 'low_snow_mask', or 'user_mask'.")

    if not np.any(ref_pixels):
        raise ValueError(f"Reference strategy '{strategy}' selected zero finite pixels.")

    reference_value = float(np.nanmedian(phase[ref_pixels]))
    referenced = phase - reference_value
    return ReferencePhaseResult(
        phase_referenced=referenced,
        reference_value_rad=reference_value,
        strategy=strategy,
        diagnostics={
            "strategy": strategy,
            "reference_value_rad": reference_value,
            "reference_pixels": int(ref_pixels.sum()),
            "reference_fraction": float(ref_pixels.sum() / phase.size) if phase.size else np.nan,
        },
    )
