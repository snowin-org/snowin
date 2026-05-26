"""Raster diagnostic summaries used by SnowIn plotting and workflows."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np


def finite_values(arr: np.ndarray) -> np.ndarray:
    """Return finite values from an array as a flat float array."""
    values = np.asarray(arr, dtype=float).ravel()
    return values[np.isfinite(values)]


def numeric_summary(arr: np.ndarray | None) -> dict[str, float | int | None]:
    """Summarize a numeric raster-like array.

    The output is intentionally CSV-friendly. Missing arrays return a row with
    ``None`` values so batch reports can preserve layer order.
    """
    if arr is None:
        return {
            "total_n": None,
            "valid_n": None,
            "valid_fraction": None,
            "nan_fraction": None,
            "mean": None,
            "std": None,
            "min": None,
            "p01": None,
            "p05": None,
            "p50": None,
            "p95": None,
            "p99": None,
            "max": None,
        }

    values = np.asarray(arr, dtype=float)
    total_n = int(values.size)
    valid = values[np.isfinite(values)]
    valid_n = int(valid.size)

    if valid_n == 0:
        return {
            "total_n": total_n,
            "valid_n": 0,
            "valid_fraction": 0.0,
            "nan_fraction": 1.0 if total_n else None,
            "mean": None,
            "std": None,
            "min": None,
            "p01": None,
            "p05": None,
            "p50": None,
            "p95": None,
            "p99": None,
            "max": None,
        }

    p01, p05, p50, p95, p99 = np.nanpercentile(valid, [1, 5, 50, 95, 99])
    return {
        "total_n": total_n,
        "valid_n": valid_n,
        "valid_fraction": float(valid_n / total_n) if total_n else None,
        "nan_fraction": float(1.0 - (valid_n / total_n)) if total_n else None,
        "mean": float(np.nanmean(valid)),
        "std": float(np.nanstd(valid)),
        "min": float(np.nanmin(valid)),
        "p01": float(p01),
        "p05": float(p05),
        "p50": float(p50),
        "p95": float(p95),
        "p99": float(p99),
        "max": float(np.nanmax(valid)),
    }


def connected_component_summary(
    arr: np.ndarray | None,
) -> dict[str, float | int | None]:
    """Summarize a connected-component raster."""
    if arr is None:
        return {
            "cc_valid_n": None,
            "cc_n_unique": None,
            "cc_dominant_component": None,
            "cc_dominant_fraction": None,
        }

    valid = finite_values(arr)
    if valid.size == 0:
        return {
            "cc_valid_n": 0,
            "cc_n_unique": 0,
            "cc_dominant_component": None,
            "cc_dominant_fraction": None,
        }

    vals, counts = np.unique(valid.astype(np.int64), return_counts=True)
    idx = int(np.argmax(counts))
    return {
        "cc_valid_n": int(valid.size),
        "cc_n_unique": int(vals.size),
        "cc_dominant_component": int(vals[idx]),
        "cc_dominant_fraction": float(counts[idx] / valid.size),
    }


def mask_summary(arr: np.ndarray | None) -> dict[str, Any]:
    """Summarize a mask/QA raster."""
    if arr is None:
        return {
            "mask_valid_n": None,
            "mask_unique_values": None,
            "mask_fill_255_fraction": None,
        }

    valid = finite_values(arr)
    if valid.size == 0:
        return {
            "mask_valid_n": 0,
            "mask_unique_values": "",
            "mask_fill_255_fraction": None,
        }

    vals, counts = np.unique(valid.astype(np.int64), return_counts=True)
    fill_fraction = 0.0
    if 255 in vals:
        fill_fraction = float(counts[np.where(vals == 255)[0][0]] / valid.size)

    return {
        "mask_valid_n": int(valid.size),
        "mask_unique_values": ";".join(str(int(v)) for v in vals),
        "mask_fill_255_fraction": fill_fraction,
    }


def merge_summaries(*parts: Mapping[str, Any]) -> dict[str, Any]:
    """Merge multiple summary dictionaries into one CSV-friendly row."""
    merged: dict[str, Any] = {}
    for part in parts:
        merged.update(dict(part))
    return merged
