"""Public phase-normalization boundary for NISAR products.

The implementation remains co-located with the product adapter while the
adapter is being decomposed.  Keeping this domain module explicit gives
callers and future maintainers a stable home for source-convention handling.
"""

from .nisar_product import (
    NISAR_GUNW_PHASE_TRANSFORM,
    NISAR_GUNW_SOURCE_PHASE_DEFINITION,
    SPEED_OF_LIGHT_M_S,
    normalize_gunw_pair,
    read_gunw_wavelength_m,
)

__all__ = [
    "NISAR_GUNW_PHASE_TRANSFORM",
    "NISAR_GUNW_SOURCE_PHASE_DEFINITION",
    "SPEED_OF_LIGHT_M_S",
    "normalize_gunw_pair",
    "read_gunw_wavelength_m",
]
