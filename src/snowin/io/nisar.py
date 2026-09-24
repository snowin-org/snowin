"""Compatibility facade for the NISAR GUNW adapter.

The implementation is organized by domain in :mod:`nisar_product`,
:mod:`dem`, :mod:`geometry`, and :mod:`phase_normalization`.  This module is
kept as the historical import location so existing code continues to work.
New code should prefer :mod:`snowin.io` or the domain-specific modules.
"""

from .nisar_product import (
    NISAR_GUNW_PHASE_TRANSFORM,
    NISAR_GUNW_SOURCE_PHASE_DEFINITION,
    SPEED_OF_LIGHT_M_S,
    DEMSource,
    _nisar_dem_tile_url,  # noqa: F401
    _open_cop30_dem,  # noqa: F401
    _read_radar_los,  # noqa: F401
    add_gunw_incidence,
    compute_cop30_local_incidence,
    compute_gunw_incidence,
    download_cop30_dem_for_gunw,
    download_nisar_cop30_dem_for_gunw,
    normalize_gunw_pair,
    open_gunw,
    read_gunw_wavelength_m,
)

__all__ = [
    "NISAR_GUNW_PHASE_TRANSFORM",
    "NISAR_GUNW_SOURCE_PHASE_DEFINITION",
    "SPEED_OF_LIGHT_M_S",
    "DEMSource",
    "add_gunw_incidence",
    "compute_cop30_local_incidence",
    "compute_gunw_incidence",
    "download_cop30_dem_for_gunw",
    "download_nisar_cop30_dem_for_gunw",
    "normalize_gunw_pair",
    "open_gunw",
    "read_gunw_wavelength_m",
]
