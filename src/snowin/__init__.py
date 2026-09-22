"""SnowIn: snow-focused SAR and InSAR analysis tools."""

from __future__ import annotations

from snowin.quality import (
    build_support_dataset,
    compose_support_mask,
    compute_metrics,
    summarize_support,
)
from snowin.reference import reference_phase
from snowin.snow import compute_dswe
from snowin.temporal import accumulate_dswe

__version__ = "0.1.0"


def plot_gunw(*args, **kwargs):
    """Create NISAR GUNW quick-look plots and diagnostic CSVs.

    This lazy wrapper keeps the base ``snowin`` import lightweight. Install the
    plotting/GUNW optional dependencies before calling it.
    """
    from snowin.plotting import plot_gunw as _plot_gunw

    return _plot_gunw(*args, **kwargs)


def gunw_to_dswe(*args, **kwargs):
    """Run the legacy GUNW-to-dSWE compatibility workflow.

    Prefer the explicit ``snowin.io.open_gunw`` ->
    ``snowin.io.add_gunw_incidence`` -> ``snowin.compute_dswe`` path. This
    temporary root-level alias is retained for existing callers but is not
    part of the stable facade.
    """
    from snowin.workflows import gunw_to_dswe as _gunw_to_dswe

    return _gunw_to_dswe(*args, **kwargs)


__all__ = [
    "__version__",
    "accumulate_dswe",
    "build_support_dataset",
    "compose_support_mask",
    "compute_dswe",
    "compute_metrics",
    "plot_gunw",
    "reference_phase",
    "summarize_support",
]
