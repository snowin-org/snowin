"""Synthetic tests for GUNW plotting data and output contracts."""

from __future__ import annotations

import builtins
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pytest
import xarray as xr
from shapely.geometry import Polygon, box, mapping

from snowin.io.gunw import GunwLayers
from snowin.plotting.gunw import (
    GeoJsonCropper,
    _apply_crop,
    basename_no_suffix,
    build_summary_rows,
    dataarray_to_array,
    discrete_cmap_and_norm,
    maybe_downsample,
    metadata_text,
    percentile_limits,
    plot_continuous,
    plot_discrete,
    plot_gunw,
    safe_name_token,
    write_metadata_json,
    write_summary_csv,
)


def _grid(values: np.ndarray, *, name: str = "layer") -> xr.DataArray:
    return xr.DataArray(
        values,
        dims=("y", "x"),
        coords={
            "y": [30.0 - 10.0 * i for i in range(values.shape[0])],
            "x": [10.0 * i for i in range(values.shape[1])],
        },
        name=name,
    )


def test_dataarray_to_array_handles_complex_and_structured_samples():
    complex_layer = _grid(
        np.tile([3 + 4j, 1 + 1j, np.nan + 0j, 1e21 + 0j], (3, 1)),
        name="complex",
    )
    magnitude, x, y = dataarray_to_array(complex_layer, magnitude=True)
    np.testing.assert_allclose(magnitude[0, :2], [5.0, np.sqrt(2.0)])
    assert np.isnan(magnitude[0, 2:]).all()
    np.testing.assert_array_equal(x, [0.0, 10.0, 20.0, 30.0])
    np.testing.assert_array_equal(y, [30.0, 20.0, 10.0])

    structured = np.array(
        [[(3.0, 4.0), (1.0, 1.0)]],
        dtype=[("r", "float64"), ("i", "float64")],
    )
    structured_layer = xr.DataArray(
        structured,
        dims=("y", "x"),
        coords={"y": [10.0], "x": [2.0, 3.0]},
    )
    structured_magnitude, _, _ = dataarray_to_array(structured_layer, magnitude=True)
    np.testing.assert_allclose(structured_magnitude, [[5.0, np.sqrt(2.0)]])
    assert dataarray_to_array(None) == (None, None, None)


def test_plotting_numeric_limits_and_stride_downsampling():
    assert percentile_limits(np.array([np.nan, 2.0, 2.0])) == (2.0, 2.000001)
    assert percentile_limits(np.array([np.nan])) == (0.0, 1.0)

    values = np.arange(9 * 12).reshape(9, 12)
    x = np.arange(12)
    y = np.arange(9)
    sampled, sampled_x, sampled_y = maybe_downsample(values, x, y, max_dim=4)
    np.testing.assert_array_equal(sampled, values[::3, ::3])
    np.testing.assert_array_equal(sampled_x, x[::3])
    np.testing.assert_array_equal(sampled_y, y[::3])
    assert maybe_downsample(None, None, None) == (None, None, None)


@pytest.mark.parametrize(
    "values, expected_labels",
    [
        (np.array([np.nan]), []),
        (np.array([4.0, 4.0]), ["4"]),
        (np.array([1.0, 4.0, np.nan]), ["1", "4"]),
    ],
)
def test_discrete_color_scale_labels_only_finite_classes(values, expected_labels):
    _cmap, norm, classes, labels = discrete_cmap_and_norm(values)

    assert labels == (expected_labels if expected_labels else None)
    np.testing.assert_array_equal(classes, np.unique(values[np.isfinite(values)]))
    if expected_labels:
        assert norm is not None


def test_geojson_crop_preserves_grid_order_and_masks_outside_polygon(tmp_path):
    geojson = tmp_path / "region.geojson"
    geojson.write_text(
        json.dumps({"type": "Feature", "geometry": mapping(box(5, 5, 25, 25))}),
        encoding="utf-8",
    )
    cropper = GeoJsonCropper.from_geojson(
        geojson,
        target_epsg=32613,
        source_epsg=32613,
        padding=5.0,
    )
    values = np.arange(12, dtype=float).reshape(3, 4)
    cropped, x, y = cropper.crop_to_bbox(
        values,
        np.array([0.0, 10.0, 20.0, 30.0]),
        np.array([30.0, 20.0, 10.0]),
    )
    assert cropped.shape == (3, 4)
    np.testing.assert_array_equal(x, [0.0, 10.0, 20.0, 30.0])
    np.testing.assert_array_equal(y, [30.0, 20.0, 10.0])
    masked = cropper.mask_array(cropped, x, y)
    assert np.isnan(masked[0, 0])
    assert np.isfinite(masked[1, 1])

    no_mask = GeoJsonCropper(box(0, 0, 2, 2), mask_outside=False)
    np.testing.assert_array_equal(no_mask.mask_array(cropped, x, y), cropped)
    empty, empty_x, empty_y = _apply_crop(
        values,
        np.arange(4, dtype=float),
        np.arange(3, dtype=float),
        GeoJsonCropper(box(100, 100, 101, 101)),
    )
    assert empty.shape == (0, 0)
    assert empty_x.size == empty_y.size == 0


def test_polygon_hole_masks_pixels_without_mutating_input():
    polygon = Polygon(
        [(0, 0), (4, 0), (4, 4), (0, 4)],
        holes=[[(1, 1), (3, 1), (3, 3), (1, 3)]],
    )
    cropper = GeoJsonCropper(polygon)
    original = np.arange(16, dtype=float).reshape(4, 4)
    values = original.copy()
    x = np.array([0.5, 1.5, 2.5, 3.5])
    y = x[::-1]

    masked = cropper.mask_array(values, x, y)

    assert np.isnan(masked[1:3, 1:3]).all()
    assert np.isfinite(masked[0, 0])
    np.testing.assert_array_equal(values, original)


def test_polygon_mask_uses_rasterio_fallback_without_shapely_accelerators(
    monkeypatch,
):
    shapely = pytest.importorskip("shapely")
    pytest.importorskip("rasterio")
    monkeypatch.setattr(shapely, "contains_xy", None, raising=False)
    original_import = builtins.__import__

    def import_without_vectorized(
        name, globals=None, locals=None, fromlist=(), level=0
    ):
        if name == "shapely" and "vectorized" in fromlist:
            raise ImportError("exercise Rasterio mask fallback")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", import_without_vectorized)
    cropper = GeoJsonCropper(box(0, 0, 4, 4))
    values = np.arange(16, dtype=float).reshape(4, 4)

    masked = cropper.mask_array(
        values,
        np.array([0.5, 1.5, 2.5, 3.5]),
        np.array([3.5, 2.5, 1.5, 0.5]),
    )

    np.testing.assert_array_equal(masked, values)


def test_geojson_feature_collection_reprojects_union_and_rejects_empty(tmp_path):
    from pyproj import Transformer
    from shapely.ops import transform, unary_union

    path = tmp_path / "regions.geojson"
    features = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": mapping(box(-111.1, 40, -111.0, 40.1))},
            {"type": "Feature", "geometry": mapping(box(-110.9, 40, -110.8, 40.1))},
        ],
    }
    path.write_text(json.dumps(features), encoding="utf-8")
    cropper = GeoJsonCropper.from_geojson(
        path, target_epsg=32612, source_epsg=4326, padding=125.0
    )
    transformer = Transformer.from_crs(4326, 32612, always_xy=True)
    expected_geometry = transform(
        transformer.transform,
        unary_union([box(-111.1, 40, -111.0, 40.1), box(-110.9, 40, -110.8, 40.1)]),
    )
    xmin, ymin, xmax, ymax = expected_geometry.bounds
    np.testing.assert_allclose(
        cropper.bounds,
        [xmin - 125.0, ymin - 125.0, xmax + 125.0, ymax + 125.0],
        rtol=0,
        atol=1e-8,
    )

    empty_path = tmp_path / "empty.geojson"
    empty_path.write_text(
        '{"type":"FeatureCollection","features":[]}', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="no geometry"):
        GeoJsonCropper.from_geojson(empty_path, target_epsg=32612)


def test_plot_boundary_includes_polygon_exterior_and_hole():
    polygon = Polygon(
        [(0, 0), (4, 0), (4, 4), (0, 4)],
        holes=[[(1, 1), (3, 1), (3, 3), (1, 3)]],
    )
    figure, axis = plt.subplots()
    try:
        GeoJsonCropper(polygon).plot_boundary(axis, color="black")
        assert len(axis.lines) == 2
        np.testing.assert_array_equal(axis.lines[0].get_xdata(), [0, 4, 4, 0, 0])
        np.testing.assert_array_equal(axis.lines[1].get_xdata(), [1, 3, 3, 1, 1])
    finally:
        plt.close(figure)


def test_plot_orientation_and_discrete_colorbar_tick_cap():
    ascending_y = _grid(np.arange(12, dtype=float).reshape(3, 4)).assign_coords(
        y=[10.0, 20.0, 30.0]
    )
    figure, axis = plt.subplots()
    try:
        plot_continuous(axis, ascending_y, "ascending", "viridis")
        image = axis.images[0]
        assert image.origin == "lower"
        assert image.get_extent() == [0.0, 30.0, 10.0, 30.0]
    finally:
        plt.close(figure)

    many_classes = _grid(np.arange(20, dtype=float).reshape(4, 5))
    figure, axis = plt.subplots()
    try:
        plot_discrete(axis, many_classes, "class labels")
        assert len(figure.axes) == 2
        colorbar_axis = figure.axes[1]
        assert len(colorbar_axis.get_xticks()) == 12
        assert len(colorbar_axis.get_xticklabels()) == 12
    finally:
        plt.close(figure)


def test_plot_helpers_report_missing_empty_and_rendered_data():
    figure, axes = plt.subplots(1, 4)
    try:
        plot_continuous(axes[0], None, "missing", "viridis")
        plot_discrete(axes[1], None, "missing")
        invalid = _grid(np.full((3, 4), np.nan))
        plot_continuous(axes[2], invalid, "empty", "viridis")
        valid = _grid(np.arange(12, dtype=float).reshape(3, 4))
        plot_continuous(axes[3], valid, "phase", "viridis")
        assert "not found" in axes[0].get_title()
        assert "not found" in axes[1].get_title()
        assert "no valid" in axes[2].get_title()
        assert "p1=" in axes[3].get_title()
    finally:
        plt.close(figure)

    figure, axis = plt.subplots()
    try:
        plot_discrete(
            axis,
            _grid(np.tile([1, 1, 2, 2], (3, 1))),
            "components",
        )
        assert axis.get_title() == "components"
    finally:
        plt.close(figure)


def test_summary_exports_keep_layer_presence_and_metadata(tmp_path):
    layers = {
        "unwrapped_phase": _grid(np.array([[1.0, 2.0, np.nan, 4.0]])),
        "wrapped_ifg": _grid(np.array([[1 + 1j, 2 + 0j, 0j, 4 + 0j]])),
        "connected_components": _grid(np.array([[1, 1, 2, 2]])),
        "mask": _grid(np.array([[0, 1, 255, 0]])),
    }
    rows = build_summary_rows(layers, {}, "unused.h5")
    by_name = {row["layer"]: row for row in rows}
    assert len(rows) == 19
    assert by_name["unwrapped_phase"]["valid_n"] == 3
    assert by_name["wrapped_ifg_amplitude"]["mean"] == pytest.approx(
        (np.sqrt(2) + 2 + 0 + 4) / 4
    )
    assert by_name["incidence_angle"]["present"] is False
    assert by_name["connected_components"]["cc_n_unique"] == 2
    assert by_name["mask"]["mask_fill_255_fraction"] == pytest.approx(0.25)

    csv_path = write_summary_csv(rows, tmp_path / "nested" / "summary.csv")
    with csv_path.open(newline="", encoding="utf-8") as stream:
        saved_rows = list(csv.DictReader(stream))
    assert len(saved_rows) == 19
    assert saved_rows[0]["layer"] == "unwrapped_phase"

    metadata = {"phase_convention": "secondary_minus_reference"}
    json_path = write_metadata_json(metadata, tmp_path / "nested" / "meta.json")
    assert json.loads(json_path.read_text(encoding="utf-8")) == metadata
    header = metadata_text(
        {"granuleId": "synthetic", "crop_geojson": "/tmp/aoi.geojson"}
    )
    assert "Granule: synthetic" in header
    assert "Crop: aoi.geojson" in header


def test_plot_gunw_writes_quickview_summary_and_metadata(monkeypatch, tmp_path):
    from snowin.plotting import gunw as plotting

    gunw_file = tmp_path / "synthetic_gunw.nc"
    gunw_file.write_bytes(b"synthetic")
    layers = dict.fromkeys(
        (
            "unwrapped_phase",
            "wrapped_ifg",
            "coherence_unw",
            "connected_components",
            "mask",
            "ionosphere",
            "ionosphere_unc",
            "corr_peak",
            "wet_tropo",
        )
    )
    layers.update(
        {
            "unwrapped_phase": _grid(np.arange(12, dtype=float).reshape(3, 4)),
            "wrapped_ifg": _grid(np.ones((3, 4), dtype=complex)),
            "coherence_unw": _grid(np.full((3, 4), 0.8)),
            "connected_components": _grid(np.ones((3, 4))),
            "mask": _grid(np.zeros((3, 4))),
        }
    )
    gunw_layers = GunwLayers(
        gunw_file=gunw_file,
        polarization="HH",
        layers=layers,
        metadata={"granuleId": "synthetic"},
        dataset_attr_paths={},
    )
    monkeypatch.setattr(plotting, "detect_pol", lambda _path: "HH")
    monkeypatch.setattr(
        plotting, "read_gunw_layers", lambda *args, **kwargs: gunw_layers
    )
    monkeypatch.setattr(
        plotting,
        "build_metadata",
        lambda *args, **kwargs: {"granuleId": "synthetic", "polarization": "HH"},
    )

    result = plot_gunw(
        gunw_file,
        out_dir=tmp_path / "outputs",
        dpi=30,
        max_plot_dim=4,
        verbose=True,
    )

    assert result.polarization == "HH"
    assert result.figure_paths[0].is_file()
    assert result.summary_csv_path.is_file()
    assert result.metadata_json_path is not None
    assert result.metadata_json_path.is_file()
    assert len(result.summary_rows) == 19
    assert result.figure_paths[0].name == "synthetic_gunw_HH_quickview.png"

    opened = []
    shown = []
    monkeypatch.setattr(plotting, "_open_file", lambda path: opened.append(path))
    monkeypatch.setattr(
        plotting.GunwPlotResult,
        "show",
        lambda self: shown.append(self.figure_paths),
    )
    without_metadata = plot_gunw(
        gunw_file,
        out_dir=tmp_path / "outputs_without_metadata",
        dpi=30,
        max_plot_dim=4,
        write_metadata=False,
        open_plot=True,
        show=True,
    )
    assert without_metadata.metadata_json_path is None
    assert opened == list(without_metadata.figure_paths)
    assert shown == [without_metadata.figure_paths]


def test_name_helpers_handle_empty_and_nisar_paths():
    assert safe_name_token("  East River / Site  ") == "East_River_Site"
    assert safe_name_token("///") == "crop"
    assert basename_no_suffix(Path("granule.nc")) == "granule"
    assert basename_no_suffix(Path("granule.tif")) == "granule"
