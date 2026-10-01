"""Quality, support, and evaluation helpers."""

from .support import (
    SUPPORT_CATEGORIES,
    build_support_dataset,
    compose_support_mask,
    summarize_support,
)

__all__ = [
    "SUPPORT_CATEGORIES",
    "build_support_dataset",
    "compose_support_mask",
    "summarize_support",
]
