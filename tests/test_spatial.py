"""Tests for vector-defined analysis-region masks."""

from __future__ import annotations

import numpy as np
import pytest
import xarray as xr
from shapely.geometry import box

from scripts.study_utils.spatial import rasterize_vector_mask


def _target() -> xr.Dataset:
    y = np.array([400005.0, 399995.0, 399985.0, 399975.0])
    x = np.array([500005.0, 500015.0, 500025.0, 500035.0])
    return xr.Dataset(
        {
            "phase": xr.DataArray(
                np.zeros((y.size, x.size)),
                dims=("y", "x"),
                coords={"y": y, "x": x},
            )
        },
        coords={
            "spatial_ref": xr.DataArray(
                0,
                attrs={"spatial_ref": "EPSG:32613"},
            )
        },
    )


def test_in_memory_vector_mask_is_aligned_and_preserves_region_semantics():
    target = _target()
    result = rasterize_vector_mask(
        [box(500000.0, 399980.0, 500020.0, 400010.0)],
        target=target,
        source_crs="EPSG:32613",
        progress=False,
    )

    np.testing.assert_array_equal(
        result.values,
        [
            [True, True, False, False],
            [True, True, False, False],
            [True, True, False, False],
            [False, False, False, False],
        ],
    )
    assert result.dims == target.phase.dims
    assert result.dtype == bool
    assert result.attrs["mask_type"] == "analysis_region"
    assert result.attrs["target_grid_crs"] == "EPSG:32613"
    assert result.attrs["rasterization_all_touched"] is False


def test_geopackage_layer_is_read_and_reprojected(tmp_path):
    geopandas = pytest.importorskip("geopandas")
    pytest.importorskip("rasterio")
    pytest.importorskip("pyproj")

    from pyproj import Transformer
    from shapely.ops import transform

    target = _target()
    transformer = Transformer.from_crs("EPSG:32613", "EPSG:4326", always_xy=True)
    geographic_geometry = transform(
        transformer.transform,
        box(500000.0, 399980.0, 500020.0, 400010.0),
    )
    frame = geopandas.GeoDataFrame(
        {"name": ["East River"]},
        geometry=[geographic_geometry],
        crs="EPSG:4326",
    )
    path = tmp_path / "regions.gpkg"
    frame.to_file(path, layer="erb", driver="GPKG")

    result = rasterize_vector_mask(
        path,
        target=target,
        layer="erb",
        progress=False,
    )

    assert result.attrs["vector_layer"] == "erb"
    assert result.attrs["vector_feature_count"] == 1
    np.testing.assert_array_equal(result.values[:3, :2], True)
    np.testing.assert_array_equal(result.values[:, 2:], False)


def test_vector_mask_requires_crs_for_bare_geometries():
    with pytest.raises(ValueError, match="source CRS is missing"):
        rasterize_vector_mask(
            [box(0.0, 0.0, 1.0, 1.0)], target=_target(), progress=False
        )


def test_vector_mask_requires_target_crs():
    target = _target().drop_vars("spatial_ref")
    with pytest.raises(ValueError, match="spatial_ref"):
        rasterize_vector_mask(
            [box(500000.0, 399980.0, 500020.0, 400010.0)],
            target=target,
            source_crs="EPSG:32613",
            progress=False,
        )
