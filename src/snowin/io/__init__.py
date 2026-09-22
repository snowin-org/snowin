"""Input/output readers for SnowIn-supported products."""

from .cloud import is_s3_uri, stage_remote_file
from .dem import (
    DEMSource,
    download_cop30_dem_for_gunw,
    download_nisar_cop30_dem_for_gunw,
)
from .geometry import compute_cop30_local_incidence
from .gunw import (
    STANDARD_GUNW_LAYER_NAMES,
    GunwAcquisitionTimes,
    GunwLayers,
    build_layers,
    detect_grid_epsg,
    detect_pol,
    parse_acquisition_times_from_filename,
    read_gunw_layers,
    read_identification_metadata,
)
from .nisar_product import add_gunw_incidence, compute_gunw_incidence, open_gunw
from .phase_normalization import (
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
    "STANDARD_GUNW_LAYER_NAMES",
    "DEMSource",
    "GunwAcquisitionTimes",
    "GunwLayers",
    "add_gunw_incidence",
    "build_layers",
    "compute_cop30_local_incidence",
    "compute_gunw_incidence",
    "detect_grid_epsg",
    "detect_pol",
    "download_cop30_dem_for_gunw",
    "download_nisar_cop30_dem_for_gunw",
    "is_s3_uri",
    "normalize_gunw_pair",
    "open_gunw",
    "parse_acquisition_times_from_filename",
    "read_gunw_layers",
    "read_gunw_wavelength_m",
    "read_identification_metadata",
    "stage_remote_file",
]
