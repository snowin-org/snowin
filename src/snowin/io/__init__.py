"""Input/output readers for SnowIn-supported products."""

from .cloud import is_s3_uri, stage_remote_file
from .gunw import (
    GunwAcquisitionTimes,
    GunwLayers,
    STANDARD_GUNW_LAYER_NAMES,
    build_layers,
    detect_grid_epsg,
    detect_pol,
    parse_acquisition_times_from_filename,
    read_gunw_layers,
    read_identification_metadata,
)

__all__ = [
    "GunwAcquisitionTimes",
    "GunwLayers",
    "STANDARD_GUNW_LAYER_NAMES",
    "build_layers",
    "detect_grid_epsg",
    "detect_pol",
    "is_s3_uri",
    "parse_acquisition_times_from_filename",
    "read_gunw_layers",
    "read_identification_metadata",
    "stage_remote_file",
]
