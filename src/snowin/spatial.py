"""Spatial region masks aligned to SnowIn xarray grids."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr


def _progress(message: str, enabled: bool) -> None:
    if enabled:
        print(f"SnowIn: {message}", flush=True)


def _optional_spatial_dependencies():
    try:
        import geopandas as gpd
        import rasterio
        from pyproj import CRS, Transformer
        from rasterio.features import rasterize
        from rasterio.transform import from_bounds
        from shapely.geometry import base
        from shapely.ops import transform, unary_union
    except ImportError as exc:  # pragma: no cover - exercised by install tests
        raise ImportError(
            "vector region masks require the optional 'vectors' dependencies; "
            "install snowin[vectors] or snowin[dev]"
        ) from exc
    return (
        gpd,
        rasterio,
        CRS,
        Transformer,
        rasterize,
        from_bounds,
        base,
        transform,
        unary_union,
    )


def _target_grid(target: xr.Dataset | xr.DataArray) -> tuple[xr.DataArray, str, str]:
    if isinstance(target, xr.Dataset):
        if "phase" in target:
            template = target["phase"]
        else:
            candidates = [
                variable for variable in target.data_vars.values() if variable.ndim == 2
            ]
            if len(candidates) != 1:
                raise ValueError(
                    "target Dataset must contain a 2-D 'phase' variable or exactly one 2-D data variable"
                )
            template = candidates[0]
    elif isinstance(target, xr.DataArray):
        template = target
    else:
        raise TypeError("target must be an xarray.Dataset or xarray.DataArray")

    if template.ndim != 2:
        raise ValueError("target grid must be two-dimensional")
    y_dim, x_dim = template.dims
    if y_dim not in template.coords or x_dim not in template.coords:
        raise ValueError("target grid must provide one-dimensional x and y coordinates")
    y = np.asarray(template.coords[y_dim].values)
    x = np.asarray(template.coords[x_dim].values)
    if y.ndim != 1 or x.ndim != 1 or y.size < 2 or x.size < 2:
        raise ValueError(
            "target x and y coordinates must be one-dimensional with at least two values"
        )
    if not (np.issubdtype(x.dtype, np.number) and np.issubdtype(y.dtype, np.number)):
        raise TypeError(
            "target x and y coordinates must be numeric projected coordinates"
        )
    dx = np.diff(x)
    dy = np.diff(y)
    if not np.allclose(dx, dx[0]) or not np.allclose(dy, dy[0]):
        raise ValueError("target x and y coordinates must be regularly spaced")
    if dx[0] == 0 or dy[0] == 0:
        raise ValueError("target x and y coordinates must have non-zero spacing")
    return template, y_dim, x_dim


def _target_crs(target: xr.Dataset | xr.DataArray, CRS: Any):
    dataset = (
        target
        if isinstance(target, xr.Dataset)
        else target.to_dataset(name=target.name or "target")
    )
    if "spatial_ref" not in dataset:
        raise ValueError(
            "target grid must provide a 'spatial_ref' coordinate for CRS-aware masking"
        )
    attrs = dict(dataset["spatial_ref"].attrs)
    for key in ("spatial_ref", "crs_wkt", "crs", "epsg_code"):
        value = attrs.get(key)
        if value is not None:
            try:
                return CRS.from_user_input(value)
            except (TypeError, ValueError):
                continue
    raise ValueError("target spatial_ref does not declare a usable CRS")


def _read_vector_source(
    vector: str | Path | Any,
    *,
    layer: str | None,
    source_crs: Any,
    gpd: Any,
    base: Any,
):
    feature_count: int | None = None
    source_name = str(vector) if isinstance(vector, (str, Path)) else None
    if isinstance(vector, (str, Path)):
        path = Path(vector).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"vector file not found: {path}")
        frame = gpd.read_file(path, layer=layer)
        geometries = [
            geometry
            for geometry in frame.geometry
            if geometry is not None and not geometry.is_empty
        ]
        vector_crs = frame.crs
        feature_count = len(geometries)
    elif hasattr(vector, "geometry"):
        geometries = [
            geometry
            for geometry in vector.geometry
            if geometry is not None and not geometry.is_empty
        ]
        vector_crs = getattr(vector, "crs", None)
        feature_count = len(geometries)
    elif isinstance(vector, Mapping) or hasattr(vector, "__geo_interface__"):
        # The public API accepts GeoJSON mappings as well as objects exposing
        # the GeoJSON protocol; a mapping itself should not fall through as an
        # iterable of coordinate keys.
        interface = vector if isinstance(vector, Mapping) else vector.__geo_interface__
        if interface.get("type") == "FeatureCollection":
            geometries = [
                feature["geometry"]
                for feature in interface.get("features", [])
                if feature.get("geometry") is not None
            ]
        else:
            geometries = [interface]
        vector_crs = None
        feature_count = len(geometries)
    else:
        try:
            geometries = list(vector)
        except TypeError as exc:
            raise TypeError(
                "vector must be a path, GeoDataFrame, geometry, or iterable of geometries"
            ) from exc
        vector_crs = None
        feature_count = len(geometries)

    if not geometries:
        raise ValueError("vector source contains no non-empty geometries")
    if vector_crs is None:
        vector_crs = source_crs
    if vector_crs is None:
        raise ValueError("vector source CRS is missing; provide source_crs explicitly")
    normalized = []
    for geometry in geometries:
        if isinstance(geometry, Mapping):
            from shapely.geometry import shape

            geometry = shape(geometry)
        if not isinstance(geometry, base.BaseGeometry):
            raise TypeError(
                "vector geometries must be Shapely geometries or GeoJSON mappings"
            )
        if not geometry.is_empty:
            normalized.append(geometry)
    if not normalized:
        raise ValueError("vector source contains no usable geometries")
    return normalized, vector_crs, feature_count, source_name


def rasterize_vector_mask(
    vector: str | Path | Any,
    *,
    target: xr.Dataset | xr.DataArray,
    layer: str | None = None,
    source_crs: Any | None = None,
    all_touched: bool = False,
    dissolve: bool = True,
    invert: bool = False,
    name: str = "analysis_region",
    progress: bool = True,
) -> xr.DataArray:
    """Rasterize vector geometries onto an aligned SnowIn grid.

    Parameters
    ----------
    vector
        A GeoPackage, Shapefile, GeoJSON path, GeoDataFrame, Shapely geometry,
        GeoJSON mapping, or iterable of geometries.
    target
        SnowIn Dataset or 2-D DataArray providing projected x/y coordinates
        and a ``spatial_ref`` CRS coordinate.
    layer
        Optional vector layer name, used for multi-layer GeoPackages.
    source_crs
        CRS for bare geometries or geometry iterables without CRS metadata.
    all_touched
        If true, include every pixel touched by a geometry. The default uses
        pixel-center inclusion for a conservative, reproducible boundary.
    dissolve
        Union all input geometries before rasterization. This avoids overlaps
        changing the result and is appropriate for one analysis region.
    invert
        Return the complement of the rasterized region.
    name
        Name of the boolean analysis-region DataArray.
    progress
        Emit short progress messages for vector reading and rasterization.

    Returns
    -------
    xarray.DataArray
        Boolean mask aligned exactly to the target grid. The original phase,
        geometry, and quality layers are not modified.
    """
    if not isinstance(name, str) or not name:
        raise ValueError("name must be a non-empty string")
    (
        gpd,
        _rasterio,
        CRS,
        Transformer,
        rasterize,
        from_bounds,
        _base,
        transform,
        unary_union,
    ) = _optional_spatial_dependencies()
    template, y_dim, x_dim = _target_grid(target)
    target_crs = _target_crs(target, CRS)
    _progress("reading vector analysis region", progress)
    geometries, vector_crs, feature_count, source_name = _read_vector_source(
        vector,
        layer=layer,
        source_crs=source_crs,
        gpd=gpd,
        base=_base,
    )
    source_crs_obj = CRS.from_user_input(vector_crs)
    if source_crs_obj != target_crs:
        transformer = Transformer.from_crs(source_crs_obj, target_crs, always_xy=True)
        geometries = [
            transform(transformer.transform, geometry) for geometry in geometries
        ]
    if dissolve:
        geometries = [unary_union(geometries)]

    y = np.asarray(template.coords[y_dim].values, dtype=float)
    x = np.asarray(template.coords[x_dim].values, dtype=float)
    x_step = abs(float(np.diff(x)[0]))
    y_step = abs(float(np.diff(y)[0]))
    west = float(x.min() - x_step / 2.0)
    east = float(x.max() + x_step / 2.0)
    south = float(y.min() - y_step / 2.0)
    north = float(y.max() + y_step / 2.0)
    transform_affine = from_bounds(west, south, east, north, len(x), len(y))
    _progress("rasterizing vector analysis region onto target grid", progress)
    mask = rasterize(
        [(geometry, 1) for geometry in geometries],
        out_shape=(len(y), len(x)),
        transform=transform_affine,
        fill=0,
        default_value=1,
        all_touched=all_touched,
        dtype="uint8",
    ).astype(bool)
    if y[0] < y[-1]:
        mask = mask[::-1, :]
    if x[0] > x[-1]:
        mask = mask[:, ::-1]
    if invert:
        mask = ~mask

    result = xr.DataArray(
        mask,
        dims=template.dims,
        coords={dimension: template.coords[dimension] for dimension in template.dims},
        name=name,
        attrs={
            "meaning": "explicit vector-defined analysis region",
            "mask_type": "analysis_region",
            "vector_source": source_name or "in-memory geometry",
            "vector_layer": layer or "",
            "vector_feature_count": int(feature_count or 0),
            "vector_source_crs": source_crs_obj.to_string(),
            "target_grid_crs": target_crs.to_string(),
            "rasterization_all_touched": bool(all_touched),
            "rasterization_dissolve": bool(dissolve),
            "rasterization_invert": bool(invert),
            "unknown_policy": "outside vector region is explicitly false",
        },
    )
    return result


__all__ = ["rasterize_vector_mask"]
