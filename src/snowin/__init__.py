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


def gunw_to_dswe(*args, **kwargs):
    """Run the explicit GUNW-to-dSWE workflow scaffold."""
    from snowin.workflows import gunw_to_dswe as _gunw_to_dswe

    return _gunw_to_dswe(*args, **kwargs)


__all__ = ["__version__", "gunw_to_dswe", "plot_gunw"]
