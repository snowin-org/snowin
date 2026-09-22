"""Quality, support, and evaluation helpers."""

from .gunw import QualityMaskResult, build_gunw_quality_mask
from .metrics import SUPPORTED_METRICS, compute_metrics
from .support import (
    SUPPORT_CATEGORIES,
    build_support_dataset,
    compose_support_mask,
    summarize_support,
)

__all__ = [
    "SUPPORTED_METRICS",
    "SUPPORT_CATEGORIES",
    "QualityMaskResult",
    "build_gunw_quality_mask",
    "build_support_dataset",
    "compose_support_mask",
    "compute_metrics",
    "summarize_support",
]
