"""Prepared-DEM geometry for SnowIn local-incidence calculations."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Literal

import numpy as np
import xarray as xr

from ._geometry_dask import _dask_incidence_array, _normalize_geometry_chunks

DEMSource = Literal["nisar_cop30", "cop30", "tandem30", "srtm30"]
"""Named prepared DEM inputs supported by SnowIn geometry."""


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


def _require_rasterio():
    try:
        return import_module("rasterio")
    except ImportError as exc:
        raise ImportError(
            "Raster-based DEM and CRS operations require SnowIn's optional "
            "'geometry' extra (rasterio)"
        ) from exc


def _progress(message: str, enabled: bool) -> None:
    """Emit a small user-facing progress message for slow I/O/geometry work."""
    if enabled:
        print(f"[snowin] {message}", flush=True)


def _validate_dem_source(source: str) -> DEMSource:
    if source not in _DEM_SOURCE_METADATA:
        supported = ", ".join(_DEM_SOURCE_METADATA)
        raise ValueError(f"dem_source must be one of: {supported}")
    return source


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
    geometry_chunks: int | tuple[int, int] | None = None,
    progress: bool = True,
) -> xr.DataArray:
    """Compute terrain-surface incidence from a named DEM and GUNW LOS.

    The calculation is an independent xarray-facing reimplementation of the
    verified Colorado method: a projected-metre DEM supplies a local surface
    normal, and the GUNW target-to-sensor LOS vectors are interpolated through
    their height/y/x lookup cube at each DEM surface elevation.  The returned
    angle is in SnowIn's required radians and is explicitly local.

    By default the DEM and LOS lookup are materialized and the result is eager,
    because SciPy's regular-grid interpolation is the numerical primitive. If
    ``geometry_chunks`` is supplied, SnowIn builds a prototype Dask graph that
    interpolates one output chunk at a time and returns a Dask-backed angle.
    The DEM, LOS lookup cube, and terrain normals are still loaded eagerly in
    that prototype; this option is intended for benchmarking and validation,
    not yet as a distributed geometry implementation.
    """
    dem_source = _validate_dem_source(dem_source)
    _progress("computing terrain-surface incidence from DEM and GUNW LOS", progress)
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

    sorted_height, _ = _sorted_axis(heights, arrays[0], 0)
    sorted_y, _ = _sorted_axis(y_radar, arrays[0], 1)
    sorted_x, _ = _sorted_axis(x_radar, arrays[0], 2)
    lookup_axes = (sorted_height, sorted_y, sorted_x)
    point_axes = (elevation, y, x)
    if any(
        np.nanmin(point_axis) < lookup_axis[0]
        or np.nanmax(point_axis) > lookup_axis[-1]
        for point_axis, lookup_axis in zip(point_axes, lookup_axes)
    ):
        raise ValueError(
            f"{source_label} surface or target grid extends outside the GUNW LOS lookup cube"
        )

    _progress("interpolating GUNW LOS vectors onto the DEM surface", progress)
    sorted_arrays = []
    for values in arrays:
        _, values = _sorted_axis(heights, values, 0)
        _, values = _sorted_axis(y_radar, values, 1)
        _, values = _sorted_axis(x_radar, values, 2)
        sorted_arrays.append(values)

    _progress("deriving terrain normals and incidence angles", progress)
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
    if geometry_chunks is None:
        try:
            from scipy.interpolate import RegularGridInterpolator
        except ImportError as exc:
            raise ImportError(
                "Local-incidence geometry requires SnowIn's optional "
                "'geometry' extra (scipy)"
            ) from exc

        yy, xx = np.meshgrid(y, x, indexing="ij")
        points = np.column_stack((elevation.ravel(), yy.ravel(), xx.ravel()))
        interpolated = []
        for values in sorted_arrays:
            interpolator = RegularGridInterpolator(
                (sorted_height, sorted_y, sorted_x),
                values,
                bounds_error=False,
                fill_value=np.nan,
            )
            interpolated.append(interpolator(points).reshape(elevation.shape))
        with np.errstate(invalid="ignore", divide="ignore"):
            dot = np.clip(
                interpolated[0] * normal_x
                + interpolated[1] * normal_y
                + interpolated[2] * normal_z,
                -1.0,
                1.0,
            )
            angle = np.where(dot > 0.0, np.arccos(dot), np.nan)
        geometry_execution = "eager"
        geometry_chunk_metadata = "none"
    else:
        chunk_shape = _normalize_geometry_chunks(
            geometry_chunks, (elevation.shape[0], elevation.shape[1])
        )
        _progress(
            f"building Dask-chunked incidence graph with chunks={chunk_shape}",
            progress,
        )
        angle = _dask_incidence_array(
            elevation,
            normal_x,
            normal_y,
            normal_z,
            x,
            y,
            chunk_shape=chunk_shape,
            sorted_height=sorted_height,
            sorted_y=sorted_y,
            sorted_x=sorted_x,
            arrays=tuple(sorted_arrays),  # type: ignore[arg-type]
        )
        geometry_execution = "dask_chunked_prototype"
        geometry_chunk_metadata = f"{chunk_shape[0]},{chunk_shape[1]}"

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
            "valid_max": float(np.pi / 2.0),
            "valid_max_exclusive": True,
            "invalid_geometry_policy": (
                "NaN where the target-to-sensor LOS has no positive projection "
                "onto the local terrain normal"
            ),
            "los_vector_direction": "target_to_sensor",
            "los_interpolation_method": "linear",
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
            "geometry_execution": geometry_execution,
            "geometry_chunks": geometry_chunk_metadata,
        },
    )
    if epsg_code is not None:
        result.attrs["epsg_code"] = int(epsg_code)
    return result


def _coordinate_transform(x: np.ndarray, y: np.ndarray):
    _require_rasterio()
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
        _require_rasterio()
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
    _require_rasterio()
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
        _require_rasterio()
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

    _require_rasterio()
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


__all__ = ["DEMSource", "compute_cop30_local_incidence"]
