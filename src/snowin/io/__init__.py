"""Input/output readers for SnowIn-supported products."""

from .cloud import is_s3_uri, stage_remote_file
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
from .nisar import (
    NISAR_GUNW_PHASE_TRANSFORM,
    NISAR_GUNW_SOURCE_PHASE_DEFINITION,
    SPEED_OF_LIGHT_M_S,
    compute_cop30_local_incidence,
    download_cop30_dem_for_gunw,
    normalize_gunw_pair,
    open_gunw,
    read_gunw_wavelength_m,
)

__all__ = [
    "NISAR_GUNW_PHASE_TRANSFORM",
    "NISAR_GUNW_SOURCE_PHASE_DEFINITION",
    "SPEED_OF_LIGHT_M_S",
    "STANDARD_GUNW_LAYER_NAMES",
    "GunwAcquisitionTimes",
    "GunwLayers",
    "build_layers",
    "compute_cop30_local_incidence",
    "detect_grid_epsg",
    "detect_pol",
    "download_cop30_dem_for_gunw",
    "is_s3_uri",
    "normalize_gunw_pair",
    "open_gunw",
    "parse_acquisition_times_from_filename",
    "read_gunw_layers",
    "read_gunw_wavelength_m",
    "read_identification_metadata",
    "stage_remote_file",
]
