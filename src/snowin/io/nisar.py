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
) -> xr.DataArray:
    """Compute terrain-surface incidence from a COP30 DEM and GUNW LOS.

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
    if dem.dims != ("y", "x"):
        raise ValueError("COP30 DEM must use dimensions ('y', 'x')")
    elevation = np.asarray(dem.data, dtype=float)
    x = np.asarray(dem.coords["x"].data, dtype=float)
    y = np.asarray(dem.coords["y"].data, dtype=float)
    if elevation.shape != (y.size, x.size) or x.size < 2 or y.size < 2:
        raise ValueError(
            "COP30 DEM coordinates must match a 2-D grid with at least two cells"
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
            "COP30 DEM surface or target grid extends outside the GUNW LOS lookup cube"
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
        raise ValueError("COP30 DEM coordinates must have nonzero spacing")
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
            "long_name": "COP30 terrain-surface local incidence angle",
            "valid_min": 0.0,
            "valid_max": float(np.pi),
            "los_vector_direction": "target_to_sensor",
            "dem_vertical_datum": dem.attrs.get("vertical_datum", "unknown"),
            "los_height_reference": "WGS84 ellipsoid",
            "definition": (
                "angle between target-to-sensor GUNW LOS and COP30 DEM-derived "
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


def _open_cop30_dem(
    dem: str | Path | xr.DataArray,
    *,
    x: np.ndarray,
    y: np.ndarray,
    epsg_code: int,
) -> xr.DataArray:
    """Read/reproject a COP30 DEM onto the exact GUNW phase grid."""
    if isinstance(dem, xr.DataArray):
        if dem.dims != ("y", "x"):
            raise ValueError("COP30 DEM must use dimensions ('y', 'x')")
        dem_epsg = dem.attrs.get("epsg_code")
        if dem_epsg is None:
            raise ValueError("COP30 DEM DataArray must declare epsg_code")
        if (
            int(dem_epsg) == epsg_code
            and dem.coords["x"].equals(xr.DataArray(x))
            and dem.coords["y"].equals(xr.DataArray(y))
        ):
            return dem
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
                raise ValueError("COP30 DEM raster is missing its CRS")
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
        raise ValueError("COP30 DEM does not overlap the GUNW phase grid")
    return xr.DataArray(
        destination,
        dims=("y", "x"),
        coords={"y": y, "x": x},
        name="cop30_elevation",
        attrs={
            "units": "m",
            "epsg_code": epsg_code,
            "horizontal_datum": "WGS84",
            "vertical_datum": "EGM2008",
            "vertical_datum_epsg": 3855,
            "height_reference": "orthometric",
        },
    )


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
    cop30_dem: str | Path | xr.DataArray | Literal["auto"] | None = "auto",
    cop30_cache_dir: str | Path | None = None,
    wavelength_m: float | None = None,
    incidence_source: str = "cop30_local",
    polarization: str | None = None,
    frequency: str = "frequencyA",
    radar_cube_index: int = 0,
    incidence_resampling: str = "linear",
    chunks: dict[str, int] | str | None = "auto",
) -> xr.Dataset:
    """Open and normalize a NISAR GUNW as a lazy SnowIn Dataset.

    By default, the incidence field is generated from a downloaded or cached
    COP30 DEM and the GUNW radar-grid LOS vectors using
    :func:`compute_cop30_local_incidence`.  Pass a local DEM path or DataArray
    to avoid network access, or pass ``incidence_source='product_ellipsoid'``
    to explicitly select the native ellipsoid angle.
    This is the terrain-surface angle required by the snow retrieval.  The
    product's ellipsoid-normal ``incidenceAngle`` is available only through
    the explicit ``incidence_source='product_ellipsoid'`` compatibility path;
    it is not silently substituted for local incidence.

    ``chunks='auto'`` preserves lazy Dask-backed arrays.  Pass ``chunks=None``
    for an eager read when Dask is not installed.
    """
    path = Path(gunw_file).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"GUNW file not found: {path}")
    if polarization is not None and polarization not in {"HH", "VV"}:
        raise ValueError("polarization must be 'HH', 'VV', or None")
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
            if cop30_dem is None or (
                isinstance(cop30_dem, str) and cop30_dem == "auto"
            ):
                cop30_dem = download_cop30_dem_for_gunw(
                    path,
                    cache_dir=cop30_cache_dir,
                    frequency=frequency,
                    polarization=pol,
                )
            dem = _open_cop30_dem(
                cop30_dem,
                x=target_x,
                y=target_y,
                epsg_code=int(epsg_code),
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
            )
            incidence_provenance = {
                "incidence_angle_source": "COP30 DEM plus NISAR GUNW radar-grid LOS",
                "incidence_angle_algorithm": "snowin.io.nisar.compute_cop30_local_incidence",
                "incidence_angle_reference": "local terrain surface",
                "gunw_height_reference": "WGS84 ellipsoid",
                "cop30_vertical_datum": "EGM2008 orthometric",
                "vertical_datum_transform": "not applied",
                "coordinate_orientation": "GUNW projected x/y phase-grid coordinates",
                "cop30_dem": str(cop30_dem)
                if not isinstance(cop30_dem, xr.DataArray)
                else "xarray.DataArray",
                "incidence_angle_resampling": "COP30 DEM bilinear reprojection to GUNW phase grid",
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
    "normalize_gunw_pair",
    "open_gunw",
    "read_gunw_wavelength_m",
]
