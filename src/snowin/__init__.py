"""SnowIn: snow-focused SAR and InSAR analysis tools."""

from __future__ import annotations

__version__ = "0.1.0"


def plot_gunw(*args, **kwargs):
    """Create NISAR GUNW quick-look plots and diagnostic CSVs.

    This lazy wrapper keeps the base ``snowin`` import lightweight. Install the
    plotting/GUNW optional dependencies before calling it.
    """
    from snowin.plotting import plot_gunw as _plot_gunw

    return _plot_gunw(*args, **kwargs)


__all__ = ["__version__", "plot_gunw"]
