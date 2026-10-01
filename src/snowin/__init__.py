"""SnowIn: snow-focused SAR and InSAR analysis tools."""

from __future__ import annotations

from snowin.quality import (
    build_support_dataset,
    compose_support_mask,
    summarize_support,
)
from snowin.reference import reference_phase
from snowin.snow import (
    compute_guneriussen_dswe,
    compute_leinss_dswe,
    compute_oveisgharan_dswe,
)
from snowin.temporal import accumulate_dswe

__version__ = "0.1.0"


__all__ = [
    "__version__",
    "accumulate_dswe",
    "build_support_dataset",
    "compose_support_mask",
    "compute_guneriussen_dswe",
    "compute_leinss_dswe",
    "compute_oveisgharan_dswe",
    "reference_phase",
    "summarize_support",
]
