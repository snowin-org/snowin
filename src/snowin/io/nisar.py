"""NISAR GUNW to SnowIn normalized-Dataset adapter.

This module is the product boundary for NISAR GUNW semantics.  The generic
scientific kernel in :mod:`snowin.snow.dswe` receives only the normalized
phase and geometry produced here; it does not know NISAR source conventions.
"""

from __future__ import annotations

import json
import math
import shutil
import urllib.request
from collections.abc import Mapping
from datetime import UTC, datetime
from numbers import Real
from pathlib import Path
from typing import Any, Literal

import numpy as np
import xarray as xr

from .gunw import (
    IDENTIFICATION_GROUP,
    RADAR_GRID_GROUP,
    UNWRAPPED_GROUP_TEMPLATE,
    decode_hdf5_scalar,
    read_attrs_hdf5,
    read_scalar_hdf5,
)

SPEED_OF_LIGHT_M_S = 299_792_458.0
"""Defined speed of light used to convert product center frequency to metres."""

NISAR_GUNW_SOURCE_PHASE_DEFINITION = "reference_minus_secondary"
"""The source phase orientation encoded by the NISAR/ISCE3 GUNW product."""

NISAR_GUNW_PHASE_TRANSFORM = "multiply_by_-1"
"""Transformation from the NISAR source phase to SnowIn canonical phase."""

_CANONICAL_PHASE_DEFINITION = "secondary_minus_reference"
_KNOWN_PHASE_DEFINITIONS = {
    "secondary_minus_reference",
    "reference_minus_secondary",
}
_KNOWN_SOURCE_ANGLE_UNITS = {"degree", "degrees", "deg"}
_COP30_S3_BASE_URL = "https://copernicus-dem-30m.s3.amazonaws.com"
_NISAR_DEM_BASE_URL = (
    "https://nisar.asf.earthdatacloud.nasa.gov/NISAR/DEM/v1.2/EPSG4326"
)
DEMSource = Literal["nisar_cop30", "cop30", "tandem30", "srtm30"]
"""Named DEM inputs supported by the NISAR adapter."""

_DEM_SOURCE_METADATA: dict[DEMSource, dict[str, str]] = {
    "nisar_cop30": {
        "label": "NISAR Copernicus DEM",
        "product": "Modified Copernicus DEM for NISAR",
        "vertical_datum": "WGS84 ellipsoid",
        "height_reference": "ellipsoidal",
    },
    "cop30": {
        "label": "COP30 DEM",
        "product": "Copernicus DEM GLO-30",
        "vertical_datum": "EGM2008",
        "height_reference": "orthometric",
    },
    "tandem30": {
        "label": "TanDEM-X 30 m DEM",
        "product": "TanDEM-X 30 m DEM",
        "vertical_datum": "WGS84-G1150",
        "height_reference": "ellipsoidal",
    },
    "srtm30": {
        "label": "SRTM 30 m DEM",
        "product": "SRTM 30 m DEM",
        "vertical_datum": "EGM96",
        "height_reference": "orthometric",
    },
}


def _validate_dem_source(source: str) -> DEMSource:
    if source not in _DEM_SOURCE_METADATA:
        supported = ", ".join(_DEM_SOURCE_METADATA)
        raise ValueError(f"dem_source must be one of: {supported}")
    return source  # type: ignore[return-value]


def _sorted_axis(
    coordinate: np.ndarray, values: np.ndarray, axis: int
) -> tuple[np.ndarray, np.ndarray]:
    coordinate = np.asarray(coordinate, dtype=float)
    if coordinate.ndim != 1 or coordinate.size < 2:
        raise ValueError(
            "interpolation coordinates must be one-dimensional with at least two values"
        )
    difference = np.diff(coordinate)
    if np.all(difference > 0):
        return coordinate, values
    if np.all(difference < 0):
        return coordinate[::-1], np.flip(values, axis=axis)
    raise ValueError("interpolation coordinates must be strictly monotonic")


def compute_cop30_local_incidence(
    dem: xr.DataArray,
    los_x: np.ndarray,
    los_y: np.ndarray,
    los_z: np.ndarray,
    heights: np.ndarray,
    x_radar: np.ndarray,
    y_radar: np.ndarray,
    *,
    epsg_code: int | None = None,
    vertical_correction_m: xr.DataArray | str | Path | None = None,
    require_vertical_datum_match: bool = False,
    dem_source: DEMSource = "cop30",
) -> xr.DataArray:
    """Compute terrain-surface incidence from a named DEM and GUNW LOS.

    The calculation is an independent xarray-facing reimplementation of the
    verified Colorado method: a projected-metre DEM supplies a local surface
    normal, and the GUNW target-to-sensor LOS vectors are interpolated through
    their height/y/x lookup cube at each DEM surface elevation.  The returned
    angle is in SnowIn's required radians and is explicitly local.

    The DEM and LOS lookup are intentionally materialized for this geometry
    operation because SciPy's regular-grid interpolation is the numerical
    primitive.  The phase and other product layers remain lazy in
    :func:`open_gunw`.
    """
    dem_source = _validate_dem_source(dem_source)
    source_label = _DEM_SOURCE_METADATA[dem_source]["label"]
    if dem.dims != ("y", "x"):
        raise ValueError(f"{source_label} must use dimensions ('y', 'x')")
    dem_height_reference = str(dem.attrs.get("height_reference", "unknown")).lower()
    if vertical_correction_m is not None and isinstance(
        vertical_correction_m, (str, Path)
    ):
        vertical_correction_m = _open_vertical_correction(
            vertical_correction_m,
            x=np.asarray(dem.coords["x"].data, dtype=float),
            y=np.asarray(dem.coords["y"].data, dtype=float),
            epsg_code=dem.attrs.get("epsg_code"),
        )
    correction_applied = vertical_correction_m is not None
    if (
        require_vertical_datum_match
        and not correction_applied
        and dem_height_reference
        not in {
            "ellipsoid",
            "ellipsoidal",
            "wgs84 ellipsoid",
        }
    ):
        raise ValueError(
            f"{source_label} heights are not declared WGS84 ellipsoidal; provide "
            "vertical_correction_m (geoid undulation added to orthometric height) "
            "or disable require_vertical_datum_match for provisional geometry"
        )
    if vertical_correction_m is not None:
        if not isinstance(vertical_correction_m, xr.DataArray):
            raise TypeError("vertical_correction_m must be an xarray.DataArray")
        if vertical_correction_m.dims != ("y", "x"):
            raise ValueError("vertical_correction_m must use dimensions ('y', 'x')")
        if vertical_correction_m.sizes != dem.sizes:
            raise ValueError("vertical_correction_m must match the DEM grid")
        if not vertical_correction_m.coords["x"].equals(dem.coords["x"]):
            raise ValueError("vertical_correction_m x coordinates must match the DEM")
        if not vertical_correction_m.coords["y"].equals(dem.coords["y"]):
            raise ValueError("vertical_correction_m y coordinates must match the DEM")
        correction_units = vertical_correction_m.attrs.get("units")
        if correction_units not in {"m", "meter", "meters"}:
            raise ValueError("vertical_correction_m must declare units of metres")
        elevation = np.asarray(dem.data, dtype=float) + np.asarray(
            vertical_correction_m.data, dtype=float
        )
        vertical_datum_status = "corrected_with_supplied_geoid_undulation"
    else:
        elevation = np.asarray(dem.data, dtype=float)
        vertical_datum_status = (
            "matched"
            if dem_height_reference in {"ellipsoid", "ellipsoidal", "wgs84 ellipsoid"}
            else "mismatch_not_corrected"
        )
    x = np.asarray(dem.coords["x"].data, dtype=float)
    y = np.asarray(dem.coords["y"].data, dtype=float)
    if elevation.shape != (y.size, x.size) or x.size < 2 or y.size < 2:
        raise ValueError(
            f"{source_label} coordinates must match a 2-D grid with at least two cells"
        )

    arrays = [np.asarray(value, dtype=float) for value in (los_x, los_y, los_z)]
    heights = np.asarray(heights, dtype=float)
    x_radar = np.asarray(x_radar, dtype=float)
    y_radar = np.asarray(y_radar, dtype=float)
    expected_shape = (heights.size, y_radar.size, x_radar.size)
    if any(value.shape != expected_shape for value in arrays):
        raise ValueError(f"LOS arrays must all have shape {expected_shape}")

    from scipy.interpolate import RegularGridInterpolator

    sorted_height, _ = _sorted_axis(heights, arrays[0], 0)
    sorted_y, _ = _sorted_axis(y_radar, arrays[0], 1)
    sorted_x, _ = _sorted_axis(x_radar, arrays[0], 2)
    yy, xx = np.meshgrid(y, x, indexing="ij")
    points = np.column_stack((elevation.ravel(), yy.ravel(), xx.ravel()))
    point_axes = (points[:, 0], points[:, 1], points[:, 2])
    lookup_axes = (sorted_height, sorted_y, sorted_x)
    if any(
        np.nanmin(point_axis) < lookup_axis[0]
        or np.nanmax(point_axis) > lookup_axis[-1]
        for point_axis, lookup_axis in zip(point_axes, lookup_axes)
    ):
        raise ValueError(
            f"{source_label} surface or target grid extends outside the GUNW LOS lookup cube"
        )

    interpolated = []
    for values in arrays:
        _, values = _sorted_axis(heights, values, 0)
        _, values = _sorted_axis(y_radar, values, 1)
        _, values = _sorted_axis(x_radar, values, 2)
        interpolator = RegularGridInterpolator(
            (sorted_height, sorted_y, sorted_x),
            values,
            bounds_error=False,
            fill_value=np.nan,
        )
        interpolated.append(interpolator(points).reshape(elevation.shape))

    dx = float(x[1] - x[0])
    dy = float(y[1] - y[0])
    if dx == 0 or dy == 0:
        raise ValueError(f"{source_label} coordinates must have nonzero spacing")
    dz_dy, dz_dx = np.gradient(elevation, dy, dx)
    normal_x = -dz_dx
    normal_y = -dz_dy
    normal_z = np.ones_like(elevation)
    magnitude = np.sqrt(normal_x**2 + normal_y**2 + normal_z**2)
    with np.errstate(invalid="ignore", divide="ignore"):
        normal_x /= magnitude
        normal_y /= magnitude
        normal_z /= magnitude
        dot = np.clip(
            interpolated[0] * normal_x
            + interpolated[1] * normal_y
            + interpolated[2] * normal_z,
            -1.0,
            1.0,
        )
        angle = np.arccos(dot)

    result = xr.DataArray(
        angle.astype("float32"),
        dims=("y", "x"),
        coords={"y": dem.coords["y"], "x": dem.coords["x"]},
        name="incidence_angle",
        attrs={
            "units": "rad",
            "incidence_angle_reference": "local",
            "source_units": "degrees",
            "long_name": f"{source_label} terrain-surface local incidence angle",
            "valid_min": 0.0,
            "valid_max": float(np.pi),
            "los_vector_direction": "target_to_sensor",
            "dem_vertical_datum": dem.attrs.get("vertical_datum", "unknown"),
            "los_height_reference": "WGS84 ellipsoid",
            "vertical_datum_status": vertical_datum_status,
            "vertical_correction_definition": (
                "ellipsoidal_height = orthometric_height + geoid_undulation"
                if correction_applied
                else "not applied"
            ),
            "vertical_correction_source": (
                vertical_correction_m.attrs.get("source", "supplied DataArray")
                if correction_applied
                else "none"
            ),
            "definition": (
                f"angle between target-to-sensor GUNW LOS and {source_label}-derived "
                "local terrain normal"
            ),
        },
    )
    if epsg_code is not None:
        result.attrs["epsg_code"] = int(epsg_code)
    return result


def _coordinate_transform(x: np.ndarray, y: np.ndarray):
    from rasterio.transform import from_origin

    for name, coordinate in (("x", x), ("y", y)):
        coordinate = np.asarray(coordinate, dtype=float)
        if coordinate.ndim != 1 or coordinate.size < 2:
            raise ValueError(f"{name} coordinates must be 1-D with at least two values")
        difference = np.diff(coordinate)
        if not (np.all(difference > 0) or np.all(difference < 0)):
            raise ValueError(f"{name} coordinates must be strictly monotonic")
    dx = float(np.median(np.abs(np.diff(x))))
    dy = float(np.median(np.abs(np.diff(y))))
    if not np.isfinite(dx) or not np.isfinite(dy) or dx <= 0 or dy <= 0:
        raise ValueError("target grid coordinates must have finite nonzero spacing")
    return from_origin(float(np.min(x) - dx / 2), float(np.max(y) + dy / 2), dx, dy)


def _open_vertical_correction(
    correction: str | Path | xr.DataArray,
    *,
    x: np.ndarray,
    y: np.ndarray,
    epsg_code: int | None,
) -> xr.DataArray:
    """Load geoid undulation and align it to the DEM grid.

    The correction is an elevation difference in metres, not an alternate DEM.
    A positive EGM2008 geoid undulation is added to COP30 orthometric height
    according to ``h = H + N``.  Raster inputs must carry a CRS; xarray inputs
    must carry ``epsg_code`` and metre units.
    """
    if isinstance(correction, xr.DataArray):
        if correction.dims != ("y", "x"):
            raise ValueError("vertical_correction_m must use dimensions ('y', 'x')")
        if correction.attrs.get("units") not in {"m", "meter", "meters"}:
            raise ValueError("vertical_correction_m must declare units of metres")
        if epsg_code is None:
            raise ValueError(
                "DEM must declare epsg_code when loading a vertical correction"
            )
        correction_epsg = correction.attrs.get("epsg_code")
        if correction_epsg is None:
            raise ValueError("vertical_correction_m DataArray must declare epsg_code")
        if (
            int(correction_epsg) == int(epsg_code)
            and np.array_equal(correction.coords["x"].data, x)
            and np.array_equal(correction.coords["y"].data, y)
        ):
            return correction
        source_values = np.asarray(correction.data, dtype=float)
        source_x = np.asarray(correction.coords["x"].data, dtype=float)
        source_y = np.asarray(correction.coords["y"].data, dtype=float)
        source_crs = int(correction_epsg)
        source_transform = _coordinate_transform(source_x, source_y)
        source_label = "xarray.DataArray"
    else:
        import rasterio

        with rasterio.open(Path(correction).expanduser()) as source:
            source_values = source.read(1).astype(float)
            source_crs = source.crs
            source_transform = source.transform
            source_nodata = source.nodata
            if source_crs is None:
                raise ValueError("vertical correction raster is missing its CRS")
            if source_nodata is not None and np.isfinite(source_nodata):
                source_values[source_values == source_nodata] = np.nan
        source_label = str(Path(correction).expanduser().resolve())

    if epsg_code is None:
        raise ValueError(
            "DEM must declare epsg_code when loading a vertical correction"
        )
    import rasterio
    from rasterio.crs import CRS
    from rasterio.enums import Resampling
    from rasterio.warp import reproject

    target = np.full((y.size, x.size), np.nan, dtype=float)
    valid_source = np.isfinite(source_values).astype("float32")
    source_filled = np.where(np.isfinite(source_values), source_values, 0.0)
    target_transform = _coordinate_transform(x, y)
    weights = np.zeros_like(target, dtype="float32")
    reproject(
        source_filled,
        target,
        src_transform=source_transform,
        src_crs=source_crs,
        dst_transform=target_transform,
        dst_crs=CRS.from_epsg(int(epsg_code)),
        resampling=Resampling.bilinear,
    )
    reproject(
        valid_source,
        weights,
        src_transform=source_transform,
        src_crs=source_crs,
        dst_transform=target_transform,
        dst_crs=CRS.from_epsg(int(epsg_code)),
        resampling=Resampling.bilinear,
    )
    with np.errstate(divide="ignore", invalid="ignore"):
        target = target / weights
    target[weights <= 0] = np.nan
    if not np.isfinite(target).any():
        raise ValueError("vertical correction raster does not overlap the DEM grid")
    return xr.DataArray(
        target,
        dims=("y", "x"),
        coords={"y": y, "x": x},
        name="geoid_undulation",
        attrs={
            "units": "m",
            "epsg_code": int(epsg_code),
            "vertical_datum": "EGM2008 geoid undulation",
            "source": source_label,
        },
    )


def _open_dem(
    dem: str | Path | xr.DataArray,
    *,
    x: np.ndarray,
    y: np.ndarray,
    epsg_code: int,
    dem_source: DEMSource = "cop30",
) -> xr.DataArray:
    """Read/reproject a named DEM onto the exact GUNW phase grid."""
    dem_source = _validate_dem_source(dem_source)
    metadata = _DEM_SOURCE_METADATA[dem_source]
    source_label = metadata["label"]
    if isinstance(dem, xr.DataArray):
        if dem.dims != ("y", "x"):
            raise ValueError(f"{source_label} must use dimensions ('y', 'x')")
        dem_epsg = dem.attrs.get("epsg_code")
        if dem_epsg is None:
            raise ValueError(f"{source_label} DataArray must declare epsg_code")
        if (
            int(dem_epsg) == epsg_code
            and dem.coords["x"].equals(xr.DataArray(x))
            and dem.coords["y"].equals(xr.DataArray(y))
        ):
            result = dem.copy()
            result.attrs.setdefault("horizontal_datum", "WGS84")
            result.attrs.setdefault("vertical_datum", metadata["vertical_datum"])
            result.attrs.setdefault("height_reference", metadata["height_reference"])
            result.attrs.setdefault("dem_source", dem_source)
            result.attrs.setdefault("dem_product", metadata["product"])
            return result
        source_values = np.asarray(dem.data, dtype=float)
        source_x = np.asarray(dem.coords["x"].data, dtype=float)
        source_y = np.asarray(dem.coords["y"].data, dtype=float)
        source_crs = int(dem_epsg)
    else:
        import rasterio

        with rasterio.open(Path(dem).expanduser()) as source:
            source_values = source.read(1).astype(float)
            source_x = None
            source_y = None
            source_crs = source.crs
            source_transform = source.transform
            source_nodata = source.nodata
            if source_crs is None:
                raise ValueError(f"{source_label} raster is missing its CRS")
            if source_nodata is not None and np.isfinite(source_nodata):
                source_values[source_values == source_nodata] = np.nan

    from rasterio.crs import CRS
    from rasterio.enums import Resampling
    from rasterio.warp import reproject

    if source_x is not None:
        source_transform = _coordinate_transform(source_x, source_y)
        source_crs = CRS.from_epsg(int(source_crs))
    destination = np.full((y.size, x.size), np.nan, dtype=float)
    valid_source = np.isfinite(source_values).astype("float32")
    source_filled = np.where(np.isfinite(source_values), source_values, 0.0)
    target_transform = _coordinate_transform(x, y)
    target_crs = CRS.from_epsg(epsg_code)
    weights = np.zeros_like(destination, dtype="float32")
    reproject(
        source_filled,
        destination,
        src_transform=source_transform,
        src_crs=source_crs,
        dst_transform=target_transform,
        dst_crs=target_crs,
        resampling=Resampling.bilinear,
    )
    reproject(
        valid_source,
        weights,
        src_transform=source_transform,
        src_crs=source_crs,
        dst_transform=target_transform,
        dst_crs=target_crs,
        resampling=Resampling.bilinear,
    )
    with np.errstate(divide="ignore", invalid="ignore"):
        destination = destination / weights
    destination[weights <= 0] = np.nan
    if not np.isfinite(destination).any():
        raise ValueError(f"{source_label} does not overlap the GUNW phase grid")
    return xr.DataArray(
        destination,
        dims=("y", "x"),
        coords={"y": y, "x": x},
        name=f"{dem_source}_elevation",
        attrs={
            "units": "m",
            "epsg_code": epsg_code,
            "horizontal_datum": "WGS84",
            "vertical_datum": metadata["vertical_datum"],
            "height_reference": metadata["height_reference"],
            "dem_source": dem_source,
            "dem_product": metadata["product"],
        },
    )


def _open_cop30_dem(
    dem: str | Path | xr.DataArray,
    *,
    x: np.ndarray,
    y: np.ndarray,
    epsg_code: int,
) -> xr.DataArray:
    """Backward-compatible COP30-specific DEM opener."""
    return _open_dem(dem, x=x, y=y, epsg_code=epsg_code, dem_source="cop30")


def _read_radar_los(gunw_file: Path) -> tuple[np.ndarray, ...]:
    import h5py

    with h5py.File(gunw_file, "r") as h5:
        group = h5[RADAR_GRID_GROUP]
        required = (
            "heightAboveEllipsoid",
            "xCoordinates",
            "yCoordinates",
            "losUnitVectorX",
            "losUnitVectorY",
        )
        missing = [name for name in required if name not in group]
        if missing:
            raise ValueError(
                f"GUNW radar grid is missing LOS datasets: {', '.join(missing)}"
            )
        heights = np.asarray(group["heightAboveEllipsoid"][...], dtype=float)
        x_radar = np.asarray(group["xCoordinates"][...], dtype=float)
        y_radar = np.asarray(group["yCoordinates"][...], dtype=float)
        los_x = np.asarray(group["losUnitVectorX"][...], dtype=float)
        los_y = np.asarray(group["losUnitVectorY"][...], dtype=float)
        if "losUnitVectorZ" in group:
            los_z = np.asarray(group["losUnitVectorZ"][...], dtype=float)
        else:
            horizontal_squared = los_x**2 + los_y**2
            if np.any(horizontal_squared > 1.0 + 1e-6):
                raise ValueError(
                    "GUNW is missing losUnitVectorZ and its X/Y vectors cannot "
                    "define a real unit-vector Z component"
                )
            los_z = np.sqrt(np.maximum(1.0 - horizontal_squared, 0.0))
    return heights, x_radar, y_radar, los_x, los_y, los_z


def _positive_scalar(name: str, value: object) -> float:
    if not isinstance(value, Real):
        raise TypeError(f"{name} must be a finite positive scalar")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{name} must be finite and > 0")
    return result


def _cop30_tile_name(latitude: int, longitude: int) -> str:
    lat_prefix = "N" if latitude >= 0 else "S"
    lon_prefix = "E" if longitude >= 0 else "W"
    return (
        f"Copernicus_DSM_COG_10_{lat_prefix}{abs(latitude):02d}_00_"
        f"{lon_prefix}{abs(longitude):03d}_00_DEM"
    )


def _nisar_dem_tile_name(latitude: int, longitude: int) -> str:
    lat_prefix = "N" if latitude >= 0 else "S"
    lon_prefix = "E" if longitude >= 0 else "W"
    return (
        f"DEM_{lat_prefix}{abs(latitude):02d}_00_"
        f"{lon_prefix}{abs(longitude):03d}_00_C01.tif"
    )


def _nisar_dem_tile_url(latitude: int, longitude: int) -> str:
    latitude_band = math.floor(latitude / 10) * 10
    longitude_band = math.floor((longitude + 180) / 20) * 20 - 180
    lat_prefix = "N" if latitude_band >= 0 else "S"
    lon_prefix = "E" if longitude_band >= 0 else "W"
    latitude_directory = f"{lat_prefix}{abs(latitude_band):02d}"
    longitude_directory = f"{lon_prefix}{abs(longitude_band):03d}"
    directory = f"{latitude_directory}_{longitude_directory}"
    tile_name = _nisar_dem_tile_name(latitude, longitude)
    return f"{_NISAR_DEM_BASE_URL}/{latitude_directory}/{directory}/{tile_name}"


def _open_nisar_dem_url(url: str, *, timeout: int = 120):
    """Open an ASF Earthdata URL, using a standard netrc when available."""
    from urllib.parse import urlparse

    hostname = urlparse(url).hostname
    if hostname is None:
        raise ValueError(f"invalid DEM URL: {url}")
    try:
        import netrc

        credential_file = netrc.netrc()
    except (FileNotFoundError, OSError, netrc.NetrcParseError):
        credential_file = None
    if credential_file is None or not any(
        credential_file.authenticators(auth_host) is not None
        for auth_host in (hostname, "urs.earthdata.nasa.gov")
    ):
        return urllib.request.urlopen(url, timeout=timeout)

    manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    for auth_host in (hostname, "urs.earthdata.nasa.gov"):
        auth = credential_file.authenticators(auth_host)
        if auth is not None:
            login, _, password = auth
            manager.add_password(None, f"https://{auth_host}", login, password)
    opener = urllib.request.build_opener(urllib.request.HTTPBasicAuthHandler(manager))
    return opener.open(url, timeout=timeout)


def _download_nisar_dem_tile(url: str, destination: Path) -> None:
    """Download one NISAR tile using Earthdata auth when available."""
    try:
        import earthaccess
    except ImportError:
        earthaccess = None

    if earthaccess is not None:
        try:
            earthaccess.login(strategy="netrc", persist=False)
            downloaded = earthaccess.download(
                url,
                local_path=destination.parent,
                threads=1,
                show_progress=False,
            )
            if downloaded:
                downloaded_path = Path(downloaded[0])
                if downloaded_path != destination:
                    downloaded_path.replace(destination)
                return
        except Exception:
            # Fall through to the lightweight urllib/netrc path.  The caller
            # adds the URL and credential guidance to the final error.
            pass

    partial = destination.with_suffix(".part")
    with (
        _open_nisar_dem_url(url) as response,
        partial.open("wb") as output,
    ):
        shutil.copyfileobj(response, output)
    partial.replace(destination)


def download_nisar_cop30_dem_for_gunw(
    gunw_file: str | Path,
    *,
    cache_dir: str | Path | None = None,
    output_path: str | Path | None = None,
    frequency: str = "frequencyA",
    polarization: str | None = None,
) -> Path:
    """Download and mosaic the modified Copernicus DEM used by NISAR.

    The ASF/NASA NISAR DEM is a WGS84 EPSG:4326, 1-degree tiled COG dataset.
    Its elevations are re-referenced to the WGS84 ellipsoid for SAR
    processing.  Earthdata credentials may be supplied through the standard
    ``~/.netrc`` file; callers may also provide a local ``nisar_cop30_dem``
    path to avoid network access.
    """
    import rasterio
    from rasterio.merge import merge

    path = Path(gunw_file).expanduser().resolve()
    pol = polarization or _detect_pol_without_loading(path)
    min_lon, min_lat, max_lon, max_lat = _gunw_geographic_bounds(
        path,
        frequency=frequency,
        polarization=pol,
    )
    latitudes = range(math.floor(min_lat), math.floor(max_lat) + 1)
    longitudes = range(math.floor(min_lon), math.floor(max_lon) + 1)
    root = (
        Path(cache_dir).expanduser()
        if cache_dir is not None
        else Path("~/.cache/snowin/nisar_cop30").expanduser()
    )
    root.mkdir(parents=True, exist_ok=True)
    tile_paths: list[Path] = []
    for latitude in latitudes:
        for longitude in longitudes:
            tile_name = _nisar_dem_tile_name(latitude, longitude)
            tile_path = root / tile_name
            if not tile_path.exists():
                url = _nisar_dem_tile_url(latitude, longitude)
                try:
                    _download_nisar_dem_tile(url, tile_path)
                except Exception as exc:
                    tile_path.unlink(missing_ok=True)
                    tile_path.with_suffix(".part").unlink(missing_ok=True)
                    raise RuntimeError(
                        f"could not download NISAR DEM tile {tile_name} from {url}; "
                        "provide Earthdata credentials in ~/.netrc or a local "
                        "nisar_cop30_dem raster"
                    ) from exc
            tile_paths.append(tile_path)

    destination = (
        Path(output_path).expanduser()
        if output_path is not None
        else root / f"{path.stem}_nisar_cop30.tif"
    )
    if destination.exists():
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    sources = [rasterio.open(tile_path) for tile_path in tile_paths]
    try:
        mosaic, transform = merge(
            sources,
            bounds=(min_lon, min_lat, max_lon, max_lat),
        )
        profile = sources[0].profile.copy()
        profile.update(
            height=mosaic.shape[1],
            width=mosaic.shape[2],
            transform=transform,
            compress="deflate",
            tiled=True,
        )
        partial = destination.with_suffix(".part")
        with rasterio.open(partial, "w", **profile) as output:
            output.write(mosaic)
            output.update_tags(
                source_product="Modified Copernicus DEM for NISAR",
                source_url=_NISAR_DEM_BASE_URL,
                source_gunw=str(path),
                vertical_datum="WGS84 ellipsoid",
                height_reference="ellipsoidal",
                footprint="GUNW projected phase-grid footprint transformed to EPSG:4326",
            )
        partial.replace(destination)
    finally:
        for source in sources:
            source.close()
    return destination


def _gunw_geographic_bounds(
    gunw_file: str | Path,
    *,
    frequency: str,
    polarization: str,
) -> tuple[float, float, float, float]:
    """Return the GUNW phase-grid footprint as lon/lat bounds."""
    from pyproj import Transformer

    phase_group = (
        f"/science/LSAR/GUNW/grids/{frequency}/unwrappedInterferogram/{polarization}"
    )
    phase_ds = _open_group(Path(gunw_file), phase_group, chunks=None)
    try:
        if "projection" not in phase_ds:
            raise ValueError("GUNW phase group is missing its projection metadata")
        epsg_code = phase_ds["projection"].attrs.get("epsg_code")
        if epsg_code is None:
            raise ValueError("GUNW projection metadata is missing epsg_code")
        x = np.asarray(phase_ds["xCoordinates"].load().data, dtype=float)
        y = np.asarray(phase_ds["yCoordinates"].load().data, dtype=float)
    finally:
        phase_ds.close()

    transformer = Transformer.from_crs(
        int(epsg_code),
        4326,
        always_xy=True,
    )
    corners = [
        transformer.transform(float(x_value), float(y_value))
        for x_value in (x.min(), x.max())
        for y_value in (y.min(), y.max())
    ]
    longitudes, latitudes = zip(*corners)
    return (
        min(longitudes),
        min(latitudes),
        max(longitudes),
        max(latitudes),
    )


def download_cop30_dem_for_gunw(
    gunw_file: str | Path,
    *,
    cache_dir: str | Path | None = None,
    output_path: str | Path | None = None,
    frequency: str = "frequencyA",
    polarization: str | None = None,
) -> Path:
    """Download and mosaic public COP30 tiles covering a GUNW phase grid.

    The GUNW projected phase-grid footprint is transformed to geographic
    bounds, the required one-degree Copernicus DEM tiles are downloaded from
    the public AWS distribution, and a cropped GeoTIFF mosaic is written to a
    cache.  :func:`_open_cop30_dem` subsequently reprojects that mosaic onto
    the exact GUNW phase grid before local incidence is calculated.

    COP30 is a digital surface model.  Public tile availability and license
    terms are external to SnowIn; download failures are reported rather than
    silently substituting another elevation product.
    """
    import rasterio
    from rasterio.merge import merge

    path = Path(gunw_file).expanduser().resolve()
    pol = polarization or _detect_pol_without_loading(path)
    min_lon, min_lat, max_lon, max_lat = _gunw_geographic_bounds(
        path,
        frequency=frequency,
        polarization=pol,
    )
    # Include the tile at an exact integer boundary.  An extra adjacent tile
    # is harmless and avoids edge omission caused by floating-point rounding.
    latitudes = range(math.floor(min_lat), math.floor(max_lat) + 1)
    longitudes = range(math.floor(min_lon), math.floor(max_lon) + 1)

    root = (
        Path(cache_dir).expanduser()
        if cache_dir is not None
        else Path("~/.cache/snowin/cop30").expanduser()
    )
    root.mkdir(parents=True, exist_ok=True)
    tile_paths: list[Path] = []
    for latitude in latitudes:
        for longitude in longitudes:
            tile_name = _cop30_tile_name(latitude, longitude)
            tile_dir = root / tile_name
            tile_dir.mkdir(parents=True, exist_ok=True)
            tile_path = tile_dir / f"{tile_name}.tif"
            if not tile_path.exists():
                url = f"{_COP30_S3_BASE_URL}/{tile_name}/{tile_name}.tif"
                partial = tile_path.with_suffix(".part")
                try:
                    with (
                        urllib.request.urlopen(url, timeout=120) as response,
                        partial.open("wb") as destination,
                    ):
                        shutil.copyfileobj(response, destination)
                    partial.replace(tile_path)
                except Exception as exc:
                    partial.unlink(missing_ok=True)
                    raise RuntimeError(
                        f"could not download public COP30 tile {tile_name} from {url}"
                    ) from exc
            tile_paths.append(tile_path)

    destination = (
        Path(output_path).expanduser()
        if output_path is not None
        else root / f"{path.stem}_cop30.tif"
    )
    if destination.exists():
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    sources = [rasterio.open(tile_path) for tile_path in tile_paths]
    try:
        mosaic, transform = merge(
            sources,
            bounds=(min_lon, min_lat, max_lon, max_lat),
        )
        profile = sources[0].profile.copy()
        profile.update(
            height=mosaic.shape[1],
            width=mosaic.shape[2],
            transform=transform,
            compress="deflate",
            tiled=True,
        )
        partial = destination.with_suffix(".part")
        with rasterio.open(partial, "w", **profile) as output:
            output.write(mosaic)
            output.update_tags(
                source_product="Copernicus DEM GLO-30 Public",
                source_url=_COP30_S3_BASE_URL,
                source_gunw=str(path),
                footprint="GUNW projected phase-grid footprint transformed to EPSG:4326",
            )
        partial.replace(destination)
    finally:
        for source in sources:
            source.close()
    return destination


def _iso_utc(value: object, name: str) -> str:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(f"{name} must be an ISO 8601 timestamp") from exc
    else:
        raise TypeError(f"{name} must be an ISO 8601 timestamp")

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _serializable_attrs(attrs: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in attrs.items():
        decoded = decode_hdf5_scalar(value)
        if isinstance(decoded, (str, int, float, bool)) or decoded is None:
            result[str(key)] = decoded
        else:
            result[str(key)] = json.dumps(decoded, default=str)
    return result


def _require_2d(name: str, value: xr.DataArray) -> None:
    if value.dims != ("y", "x"):
        raise ValueError(
            f"{name} must use normalized dimensions ('y', 'x'); got {value.dims!r}"
        )


def _require_aligned(phase: xr.DataArray, incidence_angle: xr.DataArray) -> None:
    _require_2d("phase", phase)
    _require_2d("incidence_angle", incidence_angle)
    if phase.sizes != incidence_angle.sizes:
        raise ValueError("phase and incidence_angle must have the same grid shape")
    for dim in ("y", "x"):
        if not phase.coords[dim].equals(incidence_angle.coords[dim]):
            raise ValueError(
                f"phase and incidence_angle coordinates differ for {dim!r}"
            )


def _validate_source_convention(source: object) -> str:
    if source not in _KNOWN_PHASE_DEFINITIONS:
        raise ValueError(
            "source_phase_difference_definition is missing or unknown; expected "
            "'reference_minus_secondary' or 'secondary_minus_reference'"
        )
    return str(source)


def normalize_gunw_pair(
    phase: xr.DataArray,
    incidence_angle: xr.DataArray,
    *,
    wavelength_m: float,
    reference_time: str | datetime,
    secondary_time: str | datetime,
    source_phase_difference_definition: str,
    spatial_ref: xr.DataArray,
    source_product_type: str = "NISAR_GUNW",
    source_granule_id: str | None = None,
    additional_variables: Mapping[str, xr.DataArray] | None = None,
    provenance: Mapping[str, Any] | None = None,
) -> xr.Dataset:
    """Normalize phase and geometry into the SnowIn pair Dataset contract.

    The source convention is deliberately required.  A product adapter may
    supply a documented product-specific value, but this function never
    guesses from phase values or from a numerical sign.
    """
    if not isinstance(phase, xr.DataArray) or not isinstance(
        incidence_angle, xr.DataArray
    ):
        raise TypeError("phase and incidence_angle must be xarray.DataArray objects")
    if not isinstance(spatial_ref, xr.DataArray) or spatial_ref.ndim != 0:
        raise TypeError("spatial_ref must be a scalar xarray.DataArray")

    source_definition = _validate_source_convention(source_phase_difference_definition)
    wavelength_m = _positive_scalar("wavelength_m", wavelength_m)
    reference_time = _iso_utc(reference_time, "reference_time")
    secondary_time = _iso_utc(secondary_time, "secondary_time")

    if phase.attrs.get("units") not in {"rad", "radian", "radians"}:
        raise ValueError("source phase must declare radians in its units metadata")
    if incidence_angle.attrs.get("units") not in {"rad", "radian", "radians"}:
        raise ValueError("incidence_angle must declare radians in its units metadata")
    if incidence_angle.attrs.get("incidence_angle_reference") not in {
        "ellipsoid",
        "local",
    }:
        raise ValueError(
            "incidence_angle must declare incidence_angle_reference as "
            "'ellipsoid' or 'local'"
        )
    _require_aligned(phase, incidence_angle)

    if source_definition == "reference_minus_secondary":
        canonical_phase = -phase
        transform = NISAR_GUNW_PHASE_TRANSFORM
    else:
        canonical_phase = phase
        transform = "identity"

    canonical_phase = canonical_phase.rename("phase")
    phase_attrs = _serializable_attrs(phase.attrs)
    phase_attrs.update(
        {
            "units": "rad",
            "phase_difference_definition": _CANONICAL_PHASE_DEFINITION,
            "source_phase_difference_definition": source_definition,
            "phase_transform": transform,
            "source_variable": phase.name or "unwrappedPhase",
            "grid_mapping": "spatial_ref",
        }
    )
    canonical_phase.attrs = phase_attrs

    incidence = incidence_angle.rename("incidence_angle")
    incidence_attrs = _serializable_attrs(incidence_angle.attrs)
    incidence_attrs.update({"units": "rad", "grid_mapping": "spatial_ref"})
    incidence.attrs = incidence_attrs

    attrs: dict[str, Any] = {
        "snowin_schema_version": "0.1-draft",
        "product_kind": "pairwise_interferogram",
        "reference_time": reference_time,
        "secondary_time": secondary_time,
        "temporal_edge": "reference_to_secondary",
        "phase_difference_definition": _CANONICAL_PHASE_DEFINITION,
        "source_phase_difference_definition": source_definition,
        "phase_transform": transform,
        "wavelength_m": wavelength_m,
        "source_product_type": source_product_type,
    }
    if source_granule_id is not None:
        attrs["source_granule_id"] = source_granule_id
    if provenance:
        attrs.update(_serializable_attrs(provenance))

    variables: dict[str, xr.DataArray] = {
        "phase": canonical_phase,
        "incidence_angle": incidence,
    }
    for name, variable in (additional_variables or {}).items():
        _require_2d(name, variable)
        if variable.sizes != phase.sizes:
            raise ValueError(
                f"additional variable {name!r} does not match the phase grid"
            )
        for dim in ("y", "x"):
            if not phase.coords[dim].equals(variable.coords[dim]):
                raise ValueError(f"additional variable {name!r} is not grid-aligned")
        copied = variable.rename(name)
        copied.attrs = _serializable_attrs(variable.attrs)
        copied.attrs.setdefault("grid_mapping", "spatial_ref")
        variables[name] = copied

    result = xr.Dataset(
        variables,
        coords={
            "y": phase.coords["y"],
            "x": phase.coords["x"],
            "spatial_ref": spatial_ref.rename("spatial_ref"),
        },
        attrs=attrs,
    )
    result["x"].attrs.setdefault("units", "m")
    result["y"].attrs.setdefault("units", "m")
    return result


def read_gunw_wavelength_m(
    gunw_file: str | Path,
    *,
    frequency: str = "frequencyA",
) -> float:
    """Resolve wavelength from the GUNW authoritative center-frequency field."""
    path = f"/science/LSAR/GUNW/grids/{frequency}/centerFrequency"
    center_frequency = read_scalar_hdf5(gunw_file, path)
    attrs = read_attrs_hdf5(gunw_file, path)
    if center_frequency is None or attrs.get("units") not in {"hertz", "Hz"}:
        raise ValueError(
            f"GUNW center-frequency metadata is missing or has unknown units at {path}"
        )
    frequency_hz = _positive_scalar("center_frequency_hz", center_frequency)
    return SPEED_OF_LIGHT_M_S / frequency_hz


def _open_group(
    gunw_file: Path,
    group: str,
    *,
    chunks: dict[str, int] | str | None,
) -> xr.Dataset:
    kwargs: dict[str, Any] = {
        "group": group,
        "engine": "h5netcdf",
        "phony_dims": "sort",
        "decode_cf": True,
        "mask_and_scale": True,
    }
    if chunks is not None:
        kwargs["chunks"] = chunks
    try:
        return xr.open_dataset(gunw_file, **kwargs)
    except (ImportError, ValueError) as exc:
        if chunks is not None and "dask" in str(exc).lower():
            raise ImportError(
                "lazy GUNW opening requires optional Dask; pass chunks=None for "
                "eager opening or install the SnowIn dev/GUNW dependencies"
            ) from exc
        raise


def _grid_data(
    data_array: xr.DataArray,
    source_dataset: xr.Dataset,
    *,
    name: str,
) -> xr.DataArray:
    if data_array.ndim != 2:
        raise ValueError(f"{name} must be two-dimensional, got {data_array.dims}")
    if "yCoordinates" not in source_dataset or "xCoordinates" not in source_dataset:
        raise ValueError(f"{name} source group is missing xCoordinates/yCoordinates")
    y = source_dataset["yCoordinates"].load().data
    x = source_dataset["xCoordinates"].load().data
    return xr.DataArray(
        data_array.data,
        dims=("y", "x"),
        coords={"y": y, "x": x},
        attrs=_serializable_attrs(data_array.attrs),
        name=name,
    )


def _radar_grid_slice(
    data_array: xr.DataArray,
    source_dataset: xr.Dataset,
    *,
    radar_cube_index: int,
) -> xr.DataArray:
    if data_array.ndim != 3:
        raise ValueError(f"incidenceAngle must be a height cube, got {data_array.dims}")
    height_dim = data_array.dims[0]
    if radar_cube_index < 0 or radar_cube_index >= data_array.sizes[height_dim]:
        raise IndexError(
            f"radar_cube_index={radar_cube_index} is outside the height cube"
        )
    return _grid_data(
        data_array.isel({height_dim: radar_cube_index}),
        source_dataset,
        name="incidence_angle",
    )


def _identification_time(gunw_file: Path, role: str) -> str:
    path = f"{IDENTIFICATION_GROUP}/{role}ZeroDopplerStartTime"
    value = read_scalar_hdf5(gunw_file, path)
    if value is None:
        raise ValueError(f"GUNW is missing required {role} acquisition time metadata")
    return _iso_utc(str(value), f"{role}_time")


def _detect_pol_without_loading(gunw_file: Path) -> str:
    import h5py

    for pol in ("HH", "VV"):
        group = UNWRAPPED_GROUP_TEMPLATE.format(pol=pol)
        with h5py.File(gunw_file, "r") as h5:
            if group.lstrip("/") in h5:
                return pol
    raise ValueError("GUNW does not contain an HH or VV unwrapped phase layer")


def open_gunw(
    gunw_file: str | Path,
    *,
    dem_source: DEMSource = "nisar_cop30",
    nisar_cop30_dem: str | Path | xr.DataArray | Literal["auto"] | None = "auto",
    cop30_dem: str | Path | xr.DataArray | Literal["auto"] | None = None,
    tandem30_dem: str | Path | xr.DataArray | None = None,
    srtm30_dem: str | Path | xr.DataArray | None = None,
    dem_cache_dir: str | Path | None = None,
    cop30_cache_dir: str | Path | None = None,
    dem_vertical_correction_m: xr.DataArray | str | Path | None = None,
    cop30_vertical_correction_m: xr.DataArray | str | Path | None = None,
    require_vertical_datum_match: bool = False,
    wavelength_m: float | None = None,
    incidence_source: str = "cop30_local",
    polarization: str | None = None,
    frequency: str = "frequencyA",
    radar_cube_index: int = 0,
    incidence_resampling: str = "linear",
    chunks: dict[str, int] | str | None = "auto",
) -> xr.Dataset:
    """Open and normalize a NISAR GUNW as a lazy SnowIn Dataset.

    By default, the incidence field is generated from the downloaded or cached
    modified Copernicus DEM used by NISAR and the GUNW radar-grid LOS vectors using
    :func:`compute_cop30_local_incidence`.  Pass a local DEM path or DataArray
    to avoid network access. ``cop30_dem`` remains a compatibility input for
    the original public orthometric Copernicus tiles; set
    ``dem_source='cop30'`` when using it. TanDEM-X and SRTM remain explicit
    local-only alternatives and are not part of the default path. Use
    ``dem_cache_dir`` to control the cache location; the legacy
    ``cop30_cache_dir`` spelling remains accepted.
    This is the terrain-surface angle required by the snow retrieval.  The
    product's ellipsoid-normal ``incidenceAngle`` is available only through
    the explicit ``incidence_source='product_ellipsoid'`` compatibility path;
    it is not silently substituted for local incidence.

    ``chunks='auto'`` preserves lazy Dask-backed arrays.  Pass ``chunks=None``
    for an eager read when Dask is not installed.

    The default NISAR-modified Copernicus DEM is already re-referenced to the
    WGS84 ellipsoid used by GUNW. Raw COP30 heights are EGM2008 orthometric,
    while SRTM30 is also orthometric (normally EGM96), and TanDEM-X 30 m is
    ellipsoidal WGS84-G1150. For orthometric inputs, supply a
    ``dem_vertical_correction_m`` same-grid xarray DataArray or a
    CRS-bearing raster containing EGM2008 geoid undulation in metres. The
    correction is added to the selected orthometric height as ``h = H + N``.
    ``cop30_vertical_correction_m`` is retained as a COP30-compatible alias;
    use ``dem_vertical_correction_m`` for a generic named source. Set
    ``require_vertical_datum_match=True`` to reject uncorrected geometry.
    """
    path = Path(gunw_file).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"GUNW file not found: {path}")
    if polarization is not None and polarization not in {"HH", "VV"}:
        raise ValueError("polarization must be 'HH', 'VV', or None")
    dem_source = _validate_dem_source(dem_source)
    if (
        dem_source == "nisar_cop30"
        and nisar_cop30_dem == "auto"
        and cop30_dem is not None
        and (isinstance(cop30_dem, xr.DataArray) or cop30_dem != "auto")
    ):
        # Preserve the pre-source-selection API for callers that passed a
        # local COP30 path without an explicit dem_source.
        dem_source = "cop30"
    if (
        dem_vertical_correction_m is not None
        and cop30_vertical_correction_m is not None
    ):
        raise ValueError(
            "provide only one of dem_vertical_correction_m and "
            "cop30_vertical_correction_m"
        )
    vertical_correction_m = (
        dem_vertical_correction_m
        if dem_vertical_correction_m is not None
        else cop30_vertical_correction_m
    )
    if dem_cache_dir is not None and cop30_cache_dir is not None:
        raise ValueError("provide only one of dem_cache_dir and cop30_cache_dir")
    cache_dir = dem_cache_dir if dem_cache_dir is not None else cop30_cache_dir
    if incidence_source not in {"cop30_local", "product_ellipsoid"}:
        raise ValueError(
            "incidence_source must be 'cop30_local' or 'product_ellipsoid'"
        )
    if incidence_resampling not in {"linear", "nearest"}:
        raise ValueError("incidence_resampling must be 'linear' or 'nearest'")

    pol = polarization or _detect_pol_without_loading(path)
    phase_group = f"/science/LSAR/GUNW/grids/{frequency}/unwrappedInterferogram/{pol}"
    radar_group = RADAR_GRID_GROUP
    phase_ds = _open_group(path, phase_group, chunks=chunks)
    radar_ds = (
        _open_group(path, radar_group, chunks=chunks)
        if incidence_source == "product_ellipsoid"
        else None
    )
    try:
        if "unwrappedPhase" not in phase_ds:
            raise ValueError(
                f"GUNW phase layer is missing at {phase_group}/unwrappedPhase"
            )
        if incidence_source == "product_ellipsoid" and "incidenceAngle" not in radar_ds:
            raise ValueError(f"GUNW incidenceAngle is missing at {radar_group}")
        if "projection" not in phase_ds:
            raise ValueError("GUNW phase group is missing its projection metadata")

        raw_phase = _grid_data(
            phase_ds["unwrappedPhase"], phase_ds, name="unwrappedPhase"
        )
        raw_phase.attrs["units"] = raw_phase.attrs.get("units", "").lower()
        if raw_phase.attrs["units"] not in {"radians", "radian", "rad"}:
            raise ValueError("GUNW unwrappedPhase has missing or unknown angle units")

        if incidence_source == "product_ellipsoid":
            raw_incidence = _radar_grid_slice(
                radar_ds["incidenceAngle"],
                radar_ds,
                radar_cube_index=radar_cube_index,
            )
            source_incidence_units = raw_incidence.attrs.get("units")
            if source_incidence_units not in _KNOWN_SOURCE_ANGLE_UNITS:
                raise ValueError(
                    "GUNW incidenceAngle has missing or unknown source angle units; "
                    "expected degrees metadata"
                )
            incidence = raw_incidence * (math.pi / 180.0)
            incidence.attrs = _serializable_attrs(raw_incidence.attrs)
            incidence.attrs.update(
                {
                    "units": "rad",
                    "incidence_angle_reference": "ellipsoid",
                    "source_units": source_incidence_units,
                    "source_variable": "incidenceAngle",
                }
            )
            if np.array_equal(
                incidence.coords["x"].data, raw_phase.coords["x"].data
            ) and np.array_equal(
                incidence.coords["y"].data, raw_phase.coords["y"].data
            ):
                incidence = incidence.assign_coords(
                    x=raw_phase.coords["x"], y=raw_phase.coords["y"]
                )
            else:
                incidence = incidence.interp_like(
                    raw_phase, method=incidence_resampling
                )
            incidence_provenance = {
                "incidence_angle_source": "NISAR GUNW radarGrid ellipsoid incidenceAngle",
                "incidence_angle_resampling": incidence_resampling,
                "incidence_angle_radar_cube_index": radar_cube_index,
            }
        else:
            epsg_code = phase_ds["projection"].attrs.get("epsg_code")
            if epsg_code is None:
                raise ValueError("GUNW projection metadata is missing epsg_code")
            target_x = np.asarray(phase_ds["xCoordinates"].load().data, dtype=float)
            target_y = np.asarray(phase_ds["yCoordinates"].load().data, dtype=float)
            dem_inputs = {
                "nisar_cop30": nisar_cop30_dem,
                "cop30": cop30_dem,
                "tandem30": tandem30_dem,
                "srtm30": srtm30_dem,
            }
            selected_dem = dem_inputs[dem_source]
            if dem_source in {"nisar_cop30", "cop30"} and (
                selected_dem is None
                or (isinstance(selected_dem, str) and selected_dem == "auto")
            ):
                if dem_source == "nisar_cop30":
                    selected_dem = download_nisar_cop30_dem_for_gunw(
                        path,
                        cache_dir=cache_dir,
                        frequency=frequency,
                        polarization=pol,
                    )
                else:
                    selected_dem = download_cop30_dem_for_gunw(
                        path,
                        cache_dir=cache_dir,
                        frequency=frequency,
                        polarization=pol,
                    )
            elif selected_dem is None or (
                isinstance(selected_dem, str) and selected_dem == "auto"
            ):
                raise ValueError(
                    f"dem_source={dem_source!r} requires a local "
                    f"{dem_source}_dem path or DataArray; SnowIn does not "
                    "download that source automatically"
                )
            dem = _open_dem(
                selected_dem,
                x=target_x,
                y=target_y,
                epsg_code=int(epsg_code),
                dem_source=dem_source,
            )
            heights, x_radar, y_radar, los_x, los_y, los_z = _read_radar_los(path)
            incidence = compute_cop30_local_incidence(
                dem,
                los_x,
                los_y,
                los_z,
                heights,
                x_radar,
                y_radar,
                epsg_code=int(epsg_code),
                vertical_correction_m=vertical_correction_m,
                require_vertical_datum_match=require_vertical_datum_match,
                dem_source=dem_source,
            )
            source_metadata = _DEM_SOURCE_METADATA[dem_source]
            incidence_provenance = {
                "incidence_angle_source": (
                    f"{source_metadata['label']} plus NISAR GUNW radar-grid LOS"
                ),
                "incidence_angle_algorithm": "snowin.io.nisar.compute_cop30_local_incidence",
                "incidence_angle_reference": "local terrain surface",
                "gunw_height_reference": "WGS84 ellipsoid",
                "dem_source": dem_source,
                "dem_product": source_metadata["product"],
                "dem_vertical_datum": source_metadata["vertical_datum"],
                "dem_height_reference": source_metadata["height_reference"],
                "vertical_datum_transform": incidence.attrs.get(
                    "vertical_correction_definition", "not applied"
                ),
                "vertical_datum_status": incidence.attrs.get(
                    "vertical_datum_status", "unknown"
                ),
                "vertical_correction_source": incidence.attrs.get(
                    "vertical_correction_source", "none"
                ),
                "coordinate_orientation": "GUNW projected x/y phase-grid coordinates",
                "dem_input": str(selected_dem)
                if not isinstance(selected_dem, xr.DataArray)
                else "xarray.DataArray",
                "incidence_angle_resampling": (
                    f"{source_metadata['label']} bilinear reprojection to GUNW phase grid"
                ),
            }

        additional: dict[str, xr.DataArray] = {}
        for source_name, normalized_name in {
            "coherenceMagnitude": "coherence",
            "connectedComponents": "connected_component",
        }.items():
            if source_name in phase_ds:
                additional[normalized_name] = _grid_data(
                    phase_ds[source_name], phase_ds, name=normalized_name
                )

        spatial_ref = xr.DataArray(
            phase_ds["projection"].data,
            attrs=_serializable_attrs(phase_ds["projection"].attrs),
            name="spatial_ref",
        )
        granule_id = read_scalar_hdf5(path, f"{IDENTIFICATION_GROUP}/granuleId")
        source_provenance = {
            "source_dataset_paths": json.dumps(
                {
                    "phase": f"{phase_group}/unwrappedPhase",
                    "incidence_angle": f"{radar_group}/incidenceAngle",
                    "center_frequency": f"/science/LSAR/GUNW/grids/{frequency}/centerFrequency",
                },
                sort_keys=True,
            ),
            "source_reader": "snowin.io.nisar.open_gunw",
            "wavelength_source": (
                "explicit wavelength_m override"
                if wavelength_m is not None
                else "NISAR GUNW centerFrequency metadata via c/f"
            ),
        }
        source_provenance.update(incidence_provenance)
        result = normalize_gunw_pair(
            raw_phase,
            incidence,
            wavelength_m=(
                _positive_scalar("wavelength_m", wavelength_m)
                if wavelength_m is not None
                else read_gunw_wavelength_m(path, frequency=frequency)
            ),
            reference_time=_identification_time(path, "reference"),
            secondary_time=_identification_time(path, "secondary"),
            source_phase_difference_definition=NISAR_GUNW_SOURCE_PHASE_DEFINITION,
            spatial_ref=spatial_ref,
            source_granule_id=str(granule_id) if granule_id is not None else None,
            additional_variables=additional,
            provenance=source_provenance,
        )
    except Exception:
        phase_ds.close()
        if radar_ds is not None:
            radar_ds.close()
        raise

    def close() -> None:
        phase_ds.close()
        if radar_ds is not None:
            radar_ds.close()

    result.set_close(close)
    return result


__all__ = [
    "NISAR_GUNW_PHASE_TRANSFORM",
    "NISAR_GUNW_SOURCE_PHASE_DEFINITION",
    "SPEED_OF_LIGHT_M_S",
    "compute_cop30_local_incidence",
    "download_cop30_dem_for_gunw",
    "download_nisar_cop30_dem_for_gunw",
    "normalize_gunw_pair",
    "open_gunw",
    "read_gunw_wavelength_m",
]
