"""Scientific grid and geometry contracts for vector region masks."""

from __future__ import annotations

import json

import numpy as np
import pytest
import xarray as xr
from shapely.geometry import box, mapping

from scripts.study_utils.spatial import rasterize_vector_mask


def _grid_target(x=(5.0, 15.0, 25.0, 35.0), y=(35.0, 25.0, 15.0, 5.0)):
    phase = xr.DataArray(
        np.zeros((len(y), len(x))),
        dims=("y", "x"),
        coords={"y": np.asarray(y), "x": np.asarray(x)},
        name="phase",
        attrs={"units": "rad"},
    )
    return xr.Dataset(
        {"phase": phase},
        coords={
            "spatial_ref": xr.DataArray(
                0,
                attrs={"spatial_ref": "EPSG:32613"},
            )
        },
    )


@pytest.mark.parametrize("reverse_x", [False, True])
@pytest.mark.parametrize("reverse_y", [False, True])
def test_mask_preserves_physical_pixels_and_exact_axis_order(reverse_x, reverse_y):
    x = np.array([5.0, 15.0, 25.0, 35.0])
    y = np.array([35.0, 25.0, 15.0, 5.0])
    if reverse_x:
        x = x[::-1]
    if reverse_y:
        y = y[::-1]
    target = _grid_target(x, y)

    mask = rasterize_vector_mask(
        [box(10.0, 10.0, 30.0, 30.0)],
        target=target,
        source_crs="EPSG:32613",
        progress=False,
    )

    expected = np.zeros((4, 4), dtype=bool)
    expected[1:3, 1:3] = True
    if reverse_y:
        expected = expected[::-1]
    if reverse_x:
        expected = expected[:, ::-1]
    np.testing.assert_array_equal(mask.values, expected)
    assert mask.dims == target.phase.dims
    assert mask.dtype == np.bool_
    np.testing.assert_array_equal(mask.coords["y"], target.coords["y"])
    np.testing.assert_array_equal(mask.coords["x"], target.coords["x"])
    assert mask.attrs["target_grid_crs"] == "EPSG:32613"
    assert mask.attrs["unknown_policy"] == "outside vector region is explicitly false"


@pytest.mark.parametrize(
    "geojson",
    [
        mapping(box(10.0, 10.0, 20.0, 20.0)),
        {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "geometry": mapping(box(10.0, 10.0, 20.0, 20.0))},
                {"type": "Feature", "geometry": None},
            ],
        },
    ],
)
def test_geojson_mapping_inputs_are_rasterized_with_declared_source_crs(geojson):
    mask = rasterize_vector_mask(
        geojson,
        target=_grid_target(),
        source_crs="EPSG:32613",
        progress=False,
    )

    assert mask.attrs["vector_feature_count"] == 1
    assert mask.attrs["vector_source_crs"] == "EPSG:32613"
    assert mask.attrs["vector_source"] == "in-memory geometry"
    assert mask.values[2, 1]


def test_dataarray_target_and_single_variable_dataset_keep_grid_coordinates():
    target = _grid_target()
    dataarray = target.phase.assign_coords(
        spatial_ref=xr.DataArray(0, attrs={"spatial_ref": "EPSG:32613"})
    )
    single_layer_dataset = xr.Dataset(
        {"elevation": dataarray.rename("elevation")},
    )
    geometry = box(10.0, 10.0, 20.0, 20.0)

    from_array = rasterize_vector_mask(
        geometry,
        target=dataarray,
        source_crs="EPSG:32613",
        progress=False,
    )
    from_dataset = rasterize_vector_mask(
        [geometry],
        target=single_layer_dataset,
        source_crs="EPSG:32613",
        progress=False,
    )

    np.testing.assert_array_equal(
        from_array.coords["x"].values, dataarray.coords["x"].values
    )
    np.testing.assert_array_equal(
        from_array.coords["y"].values, dataarray.coords["y"].values
    )
    np.testing.assert_array_equal(from_array, from_dataset)


def test_invert_and_all_touched_are_explicit_and_recorded():
    target = _grid_target()
    geometry = box(9.5, 29.5, 10.5, 30.5)
    center_rule = rasterize_vector_mask(
        [geometry], target=target, source_crs="EPSG:32613", progress=False
    )
    touched_rule = rasterize_vector_mask(
        [geometry],
        target=target,
        source_crs="EPSG:32613",
        all_touched=True,
        progress=False,
    )
    inverse = rasterize_vector_mask(
        [geometry],
        target=target,
        source_crs="EPSG:32613",
        invert=True,
        name="outside_region",
        progress=False,
    )

    assert not center_rule.values.any()
    assert touched_rule.values.any()
    assert np.all(~center_rule.values | touched_rule.values)
    np.testing.assert_array_equal(inverse.values, ~center_rule.values)
    assert touched_rule.attrs["rasterization_all_touched"] is True
    assert inverse.name == "outside_region"
    assert inverse.attrs["rasterization_invert"] is True


@pytest.mark.parametrize(
    "target, error, message",
    [
        (None, TypeError, "target must be an xarray"),
        (xr.DataArray(np.zeros(4), dims=("x",)), ValueError, "two-dimensional"),
        (
            xr.DataArray(np.zeros((2, 2)), dims=("row", "column")),
            ValueError,
            "coordinates",
        ),
        (
            xr.DataArray(
                np.zeros((2, 2)),
                dims=("y", "x"),
                coords={"y": [2.0, 0.0], "x": [0.0, 1.0]},
            ),
            ValueError,
            "spatial_ref",
        ),
    ],
)
def test_invalid_target_contracts_fail_loudly(target, error, message):
    with pytest.raises(error, match=message):
        rasterize_vector_mask(
            [box(0.0, 0.0, 1.0, 1.0)],
            target=target,
            source_crs="EPSG:32613",
            progress=False,
        )


@pytest.mark.parametrize(
    "x, y, error, message",
    [
        ((5.0,), (5.0, 15.0), ValueError, "at least two values"),
        ((5.0, 15.0, 35.0), (15.0, 5.0), ValueError, "regularly spaced"),
        ((0.0, 0.0, 0.0), (15.0, 5.0, -5.0), ValueError, "non-zero spacing"),
        (("west", "east"), (15.0, 5.0), TypeError, "numeric projected coordinates"),
    ],
)
def test_invalid_or_ambiguous_grid_axes_fail_loudly(x, y, error, message):
    values = np.zeros((len(y), len(x)))
    target = xr.Dataset(
        {
            "phase": xr.DataArray(
                values,
                dims=("y", "x"),
                coords={"y": np.asarray(y), "x": np.asarray(x)},
            )
        },
        coords={"spatial_ref": xr.DataArray(0, attrs={"spatial_ref": "EPSG:32613"})},
    )

    with pytest.raises(error, match=message):
        rasterize_vector_mask(
            [box(0.0, 0.0, 1.0, 1.0)], target=target, source_crs="EPSG:32613"
        )


def test_ambiguous_dataset_target_and_invalid_geometry_fail_loudly():
    target = _grid_target()
    two_layers = xr.Dataset(
        {"first": target.phase, "second": target.phase.copy()},
        coords=target.coords,
    )
    with pytest.raises(ValueError, match="exactly one 2-D data variable"):
        rasterize_vector_mask(
            [box(0.0, 0.0, 1.0, 1.0)],
            target=two_layers,
            source_crs="EPSG:32613",
            progress=False,
        )
    with pytest.raises(ValueError, match="no non-empty geometries"):
        rasterize_vector_mask(
            [], target=target, source_crs="EPSG:32613", progress=False
        )
    with pytest.raises(TypeError, match="Shapely geometries"):
        rasterize_vector_mask(
            [object()], target=target, source_crs="EPSG:32613", progress=False
        )


def test_missing_vector_path_and_invalid_output_name_fail_loudly(tmp_path):
    target = _grid_target()
    with pytest.raises(ValueError, match="name must be a non-empty string"):
        rasterize_vector_mask(
            [box(0.0, 0.0, 1.0, 1.0)],
            target=target,
            source_crs="EPSG:32613",
            name="",
            progress=False,
        )
    with pytest.raises(FileNotFoundError, match="vector file not found"):
        rasterize_vector_mask(
            tmp_path / "absent.geojson", target=target, progress=False
        )


def test_feature_collection_mapping_is_json_serializable_and_not_mutated():
    target = _grid_target()
    features = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": mapping(box(10.0, 10.0, 20.0, 20.0))}
        ],
    }
    original = json.dumps(features, sort_keys=True)
    mask = rasterize_vector_mask(
        features,
        target=target,
        source_crs="EPSG:32613",
        progress=False,
    )

    assert json.dumps(features, sort_keys=True) == original
    assert mask.attrs["vector_feature_count"] == 1
