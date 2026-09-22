"""Quality-mask construction for NISAR GUNW workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from snowin.utils import validate_same_shape


@dataclass(frozen=True)
class QualityMaskResult:
    """Combined valid mask and per-reason rejection masks."""

    valid_mask: np.ndarray
    reason_masks: dict[str, np.ndarray]
    diagnostics: dict[str, Any]


def _true_fraction(mask: np.ndarray) -> float:
    if mask.size == 0:
        return float("nan")
    return float(np.asarray(mask, dtype=bool).sum() / mask.size)


def _dominant_component(
    connected_components: np.ndarray, base_valid: np.ndarray
) -> int | None:
    cc = np.asarray(connected_components)
    valid = base_valid & np.isfinite(cc)
    if not np.any(valid):
        return None
    vals, counts = np.unique(cc[valid].astype(int), return_counts=True)
    keep = vals != 0
    if np.any(keep):
        vals = vals[keep]
        counts = counts[keep]
    if vals.size == 0:
        return None
    return int(vals[np.argmax(counts)])


def build_gunw_quality_mask(
    phase,
    *,
    coherence=None,
    connected_components=None,
    gunw_mask=None,
    coherence_min: float = 0.3,
    connected_component: str | int | None = "dominant",
    mask_fill_values: tuple[int | float, ...] = (255,),
) -> QualityMaskResult:
    """Build an explicit quality mask for GUNW dSWE demonstrations/workflows."""
    phase_arr = np.asarray(phase, dtype=float)
    arrays = [phase_arr]
    if coherence is not None:
        arrays.append(np.asarray(coherence))
    if connected_components is not None:
        arrays.append(np.asarray(connected_components))
    if gunw_mask is not None:
        arrays.append(np.asarray(gunw_mask))
    validate_same_shape(*arrays)

    reason_masks: dict[str, np.ndarray] = {}
    reason_masks["nonfinite_phase"] = ~np.isfinite(phase_arr)

    valid = ~reason_masks["nonfinite_phase"]

    if coherence is not None:
        coh = np.asarray(coherence, dtype=float)
        low_coherence = ~np.isfinite(coh) | (coh < coherence_min)
    else:
        low_coherence = np.zeros(phase_arr.shape, dtype=bool)
    reason_masks["low_coherence"] = low_coherence
    valid &= ~low_coherence

    selected_component: int | None = None
    if connected_components is not None and connected_component is not None:
        cc = np.asarray(connected_components)
        if connected_component == "dominant":
            selected_component = _dominant_component(cc, valid)
        elif isinstance(connected_component, int):
            selected_component = connected_component
        else:
            raise ValueError(
                "connected_component must be None, 'dominant', or an integer ID."
            )

        if selected_component is None:
            invalid_cc = np.isfinite(cc)
        else:
            invalid_cc = ~np.isfinite(cc) | (
                cc.astype(float) != float(selected_component)
            )
    else:
        invalid_cc = np.zeros(phase_arr.shape, dtype=bool)
    reason_masks["invalid_connected_component"] = invalid_cc
    valid &= ~invalid_cc

    if gunw_mask is not None:
        mask_arr = np.asarray(gunw_mask)
        fill = np.zeros(phase_arr.shape, dtype=bool)
        for value in mask_fill_values:
            fill |= mask_arr == value
        fill |= ~np.isfinite(mask_arr.astype(float, copy=False))
    else:
        fill = np.zeros(phase_arr.shape, dtype=bool)
    reason_masks["gunw_fill_mask"] = fill
    valid &= ~fill

    diagnostics: dict[str, Any] = {
        "total_pixels": int(phase_arr.size),
        "valid_pixels": int(valid.sum()),
        "valid_fraction": _true_fraction(valid),
        "coherence_min": coherence_min if coherence is not None else None,
        "connected_component_requested": connected_component,
        "connected_component_selected": selected_component,
        "mask_fill_values": tuple(mask_fill_values),
    }
    for name, mask in reason_masks.items():
        diagnostics[f"{name}_pixels"] = int(mask.sum())
        diagnostics[f"{name}_fraction"] = _true_fraction(mask)

    return QualityMaskResult(
        valid_mask=valid, reason_masks=reason_masks, diagnostics=diagnostics
    )
