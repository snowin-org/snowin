"""Optional product adapters for SnowIn-supported inputs."""

from .geometry import DEMSource, compute_local_incidence
from .nisar_product import (
    add_gunw_incidence,
    compute_gunw_incidence,
    open_gunw,
    read_gunw_wavelength_m,
)
from .phase_normalization import (
    NISAR_GUNW_PHASE_TRANSFORM,
    NISAR_GUNW_SOURCE_PHASE_DEFINITION,
    normalize_gunw_pair,
)

__all__ = [
    "NISAR_GUNW_PHASE_TRANSFORM",
    "NISAR_GUNW_SOURCE_PHASE_DEFINITION",
    "DEMSource",
    "add_gunw_incidence",
    "compute_gunw_incidence",
    "compute_local_incidence",
    "normalize_gunw_pair",
    "open_gunw",
    "read_gunw_wavelength_m",
]
