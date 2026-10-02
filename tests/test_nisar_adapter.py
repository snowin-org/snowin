"""Tests for reading NISAR GUNW data into SnowIn pair Datasets."""

from __future__ import annotations

import json
import math
import warnings

import numpy as np
import pytest
import xarray as xr

from snowin.io import (
    NISAR_GUNW_SOURCE_PHASE_DEFINITION,
    add_gunw_incidence,
    compute_gunw_incidence,
    normalize_gunw_pair,
    open_gunw,
    read_gunw_wavelength_m,
)
from snowin.io.phase_normalization import _build_phase_normalized_dataset


def _pair_inputs() -> tuple[xr.DataArray, xr.DataArray, xr.DataArray]:
    coords = {"y": [20.0, 10.0], "x": [100.0, 110.0, 120.0]}
    phase = xr.DataArray(
        [[1.0, np.nan, -2.0], [3.0, 4.0, 5.0]],
        dims=("y", "x"),
        coords=coords,
        name="unwrappedPhase",
        attrs={"units": "radians"},
    )
    incidence = xr.DataArray(
        np.full((2, 3), math.radians(35.0)),
        dims=("y", "x"),
        coords=coords,
        attrs={"units": "rad", "incidence_angle_reference": "ellipsoid"},
    )
    spatial_ref = xr.DataArray(
        0,
        name="spatial_ref",
        attrs={"epsg_code": 32611, "spatial_ref": "EPSG:32611"},
    )
    return phase, incidence, spatial_ref


def test_normalize_gunw_pair_applies_explicit_source_transform():
    phase, incidence, spatial_ref = _pair_inputs()
    result = normalize_gunw_pair(
        phase,
        incidence,
        wavelength_m=0.24,
        reference_time="2025-01-01T00:00:00Z",
        secondary_time="2025-01-13T00:00:00Z",
        source_phase_difference_definition="reference_minus_secondary",
        spatial_ref=spatial_ref,
        source_granule_id="test-granule",
    )

    assert result.sizes == {"y": 2, "x": 3}
    np.testing.assert_array_equal(result.coords["x"].values, phase.coords["x"].values)
    np.testing.assert_array_equal(result.coords["y"].values, phase.coords["y"].values)
    np.testing.assert_allclose(result.phase.values, -phase.values, equal_nan=True)
    assert result.attrs["phase_difference_definition"] == "secondary_minus_reference"
    assert result.attrs["source_phase_difference_definition"] == (
        "reference_minus_secondary"
    )
    assert result.attrs["phase_transform"] == "multiply_by_-1"
    assert result.attrs["snowin_schema_version"] == "0.1"
    assert result.attrs["source_granule_id"] == "test-granule"
    assert result.attrs["snowin_data_state"] == "retrieval_ready_pair"
    assert result.spatial_ref.attrs["epsg_code"] == 32611


def test_source_metadata_cannot_override_canonical_pair_attributes():
    phase, incidence, spatial_ref = _pair_inputs()
    result = normalize_gunw_pair(
        phase,
        incidence,
        wavelength_m=0.24,
        reference_time="2025-01-01T00:00:00Z",
        secondary_time="2025-01-13T00:00:00Z",
        source_phase_difference_definition="reference_minus_secondary",
        spatial_ref=spatial_ref,
        source_metadata={
            "phase_difference_definition": "reference_minus_secondary",
            "wavelength_m": 999,
            "temporal_edge": "secondary_to_reference",
            "source_note": "source metadata is retained",
        },
    )

    assert result.attrs["phase_difference_definition"] == "secondary_minus_reference"
    assert result.phase.attrs["phase_difference_definition"] == (
        "secondary_minus_reference"
    )
    assert result.attrs["wavelength_m"] == pytest.approx(0.24)
    assert result.attrs["temporal_edge"] == "reference_to_secondary"
    assert result.attrs["source_note"] == "source metadata is retained"
    assert json.loads(result.attrs["source_metadata_conflicts"]) == {
        "phase_difference_definition": "reference_minus_secondary",
        "temporal_edge": "secondary_to_reference",
        "wavelength_m": 999,
    }


def test_pair_times_with_explicit_offsets_are_stored_as_utc():
    phase, incidence, spatial_ref = _pair_inputs()
    result = normalize_gunw_pair(
        phase,
        incidence,
        wavelength_m=0.24,
        reference_time="2025-01-01T04:00:00+04:00",
        secondary_time="2025-01-12T19:00:00-05:00",
        source_phase_difference_definition="reference_minus_secondary",
        spatial_ref=spatial_ref,
    )

    assert result.attrs["reference_time"] == "2025-01-01T00:00:00Z"
    assert result.attrs["secondary_time"] == "2025-01-13T00:00:00Z"


@pytest.mark.parametrize(
    ("reference_time", "message"),
    [(None, "reference_time is missing"), ("not-a-time", "reference_time is invalid")],
)
def test_pair_time_errors_distinguish_missing_from_invalid(reference_time, message):
    phase, incidence, spatial_ref = _pair_inputs()
    with pytest.raises(ValueError, match=message):
        normalize_gunw_pair(
            phase,
            incidence,
            wavelength_m=0.24,
            reference_time=reference_time,
            secondary_time="2025-01-13T00:00:00Z",
            source_phase_difference_definition="secondary_minus_reference",
            spatial_ref=spatial_ref,
        )


def test_normalize_gunw_pair_orders_subsecond_times_as_instants():
    phase, incidence, spatial_ref = _pair_inputs()
    result = normalize_gunw_pair(
        phase,
        incidence,
        wavelength_m=0.24,
        reference_time="2025-01-01T00:00:00Z",
        secondary_time="2025-01-01T00:00:00.000001Z",
        source_phase_difference_definition="secondary_minus_reference",
        spatial_ref=spatial_ref,
    )

    assert result.attrs["reference_time"] == "2025-01-01T00:00:00Z"
    assert result.attrs["secondary_time"] == "2025-01-01T00:00:00.000001Z"


@pytest.mark.parametrize(
    "reference_time, secondary_time",
    [
        ("2025-01-01T00:00:00", "2025-01-13T00:00:00Z"),
        ("2025-01-01T00:00:00Z", "2025-01-13T00:00:00"),
    ],
)
def test_normalize_gunw_pair_rejects_naive_timestamps(reference_time, secondary_time):
    phase, incidence, spatial_ref = _pair_inputs()
    with pytest.raises(ValueError, match="explicit UTC offset"):
        normalize_gunw_pair(
            phase,
            incidence,
            wavelength_m=0.24,
            reference_time=reference_time,
            secondary_time=secondary_time,
            source_phase_difference_definition="reference_minus_secondary",
            spatial_ref=spatial_ref,
        )


def test_normalize_gunw_pair_rejects_nonchronological_reference_secondary_times():
    phase, incidence, spatial_ref = _pair_inputs()
    with pytest.raises(ValueError, match="secondary_time must be later"):
        normalize_gunw_pair(
            phase,
            incidence,
            wavelength_m=0.24,
            reference_time="2025-01-13T00:00:00Z",
            secondary_time="2025-01-01T00:00:00Z",
            source_phase_difference_definition="reference_minus_secondary",
            spatial_ref=spatial_ref,
        )


def test_pair_builder_rejects_undeclared_native_grid_variable():
    phase, _, spatial_ref = _pair_inputs()
    native_layer = xr.DataArray(
        np.ones((2, 3)),
        dims=("radar_y", "radar_x"),
        coords={"radar_y": [0, 1], "radar_x": [0, 1, 2]},
    )

    with pytest.raises(ValueError, match="unsupported dimensions"):
        _build_phase_normalized_dataset(
            phase,
            spatial_ref,
            source_phase_difference_definition="reference_minus_secondary",
            reference_time="2025-01-01T00:00:00Z",
            secondary_time="2025-01-13T00:00:00Z",
            wavelength_m=0.24,
            additional_variables={"unexpected_layer": native_layer},
        )


def test_pair_builder_checks_declared_native_grid_dimensions():
    phase, _, spatial_ref = _pair_inputs()
    malformed_layer = xr.DataArray(
        np.ones((2, 2, 3)),
        dims=("radar_height", "radar_y", "radar_x"),
        coords={"radar_y": [0, 1], "radar_x": [0, 1, 2]},
    )

    with pytest.raises(ValueError, match="coordinate for dimension 'radar_height'"):
        _build_phase_normalized_dataset(
            phase,
            spatial_ref,
            source_phase_difference_definition="reference_minus_secondary",
            reference_time="2025-01-01T00:00:00Z",
            secondary_time="2025-01-13T00:00:00Z",
            wavelength_m=0.24,
            additional_variables={"hydro_tropo": malformed_layer},
            native_grid_dimensions={
                "hydro_tropo": (("radar_height", "radar_y", "radar_x"),)
            },
        )


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (None, "is missing"),
        ("", "is missing"),
        ("unknown", "is unsupported"),
        ("reference_minus_secondaryx", "is unsupported"),
    ],
)
def test_normalize_gunw_pair_reports_missing_and_unsupported_phase_conventions(
    source, message
):
    phase, incidence, spatial_ref = _pair_inputs()
    with pytest.raises(ValueError, match=message):
        normalize_gunw_pair(
            phase,
            incidence,
            wavelength_m=0.24,
            reference_time="2025-01-01T00:00:00Z",
            secondary_time="2025-01-13T00:00:00Z",
            source_phase_difference_definition=source,
            spatial_ref=spatial_ref,
        )


@pytest.mark.parametrize(
    ("target", "units", "message"),
    [
        ("phase", None, "source phase units are missing"),
        ("phase", "degrees", "source phase units .* unsupported"),
        ("incidence", None, "incidence_angle units are missing"),
        ("incidence", "degrees", "incidence_angle units .* unsupported"),
    ],
)
def test_normalize_gunw_pair_reports_missing_and_unsupported_units(
    target, units, message
):
    phase, incidence, spatial_ref = _pair_inputs()
    variable = phase if target == "phase" else incidence
    if units is None:
        variable.attrs.pop("units")
    else:
        variable.attrs["units"] = units
    with pytest.raises(ValueError, match=message):
        normalize_gunw_pair(
            phase,
            incidence,
            wavelength_m=0.24,
            reference_time="2025-01-01T00:00:00Z",
            secondary_time="2025-01-13T00:00:00Z",
            source_phase_difference_definition=NISAR_GUNW_SOURCE_PHASE_DEFINITION,
            spatial_ref=spatial_ref,
        )


def test_nisar_wavelength_is_derived_from_center_frequency(tmp_path):
    h5netcdf = pytest.importorskip("h5netcdf")
    path = tmp_path / "frequency.h5"
    with h5netcdf.File(path, "w") as root:
        group = root.create_group("science/LSAR/GUNW/grids/frequencyA")
        variable = group.create_variable("centerFrequency", (), float)
        variable[()] = 1.0e9
        variable.attrs["units"] = "hertz"

    assert read_gunw_wavelength_m(path) == pytest.approx(0.299792458)


def test_nisar_adapter_converts_phase_and_preserves_laziness(tmp_path):
    pytest.importorskip("scipy")
    h5netcdf = pytest.importorskip("h5netcdf")
    path = tmp_path / "test_gunw.h5"
    _write_synthetic_gunw(h5netcdf, path)

    dem = _synthetic_dem()
    result = open_gunw(path, chunks=None, progress=False)
    try:
        assert "incidence_angle" not in result
        with pytest.warns(UserWarning, match='dem_source="nisar_cop30"'):
            returned = add_gunw_incidence(
                result, path, dem_source="cop30", dem=dem, progress=False
            )
        assert returned is result
        assert result.attrs["snowin_data_state"] == "retrieval_ready_pair"
        np.testing.assert_allclose(result.phase.values, [[-1.0, -2.0], [-3.0, -4.0]])
        assert result.phase.attrs["units"] == "rad"
        assert result.incidence_angle.attrs["units"] == "rad"
        assert result.incidence_angle.attrs["incidence_angle_reference"] == "local"
        assert result.incidence_angle.attrs["los_interpolation_method"] == "linear"
        assert result.incidence_angle.attrs["incidence_angle_origin"] == "terrain_local"
        assert "source_units" not in result.incidence_angle.attrs
        assert "incidence_angle_source_dataset_path" not in result.incidence_angle.attrs
        np.testing.assert_allclose(result.incidence_angle.values, np.deg2rad(30.0))
        assert result.geometry_valid.dtype == bool
        assert bool(result.geometry_valid.all())
        assert result.attrs["wavelength_m"] == pytest.approx(0.299792458)
        assert result.attrs["source_phase_difference_definition"] == (
            "reference_minus_secondary"
        )
        assert result.attrs["phase_transform"] == "multiply_by_-1"
        assert result.attrs["reference_time"] == "2025-01-01T00:00:00Z"
        assert result.attrs["secondary_time"] == "2025-01-13T00:00:00Z"
        assert result.attrs["source_acquisition_time_zone"] == (
            "UTC per NISAR L2 Product Format Document v1.2.1"
        )
        assert result.attrs["temporal_edge"] == "reference_to_secondary"
        assert result.spatial_ref.attrs["epsg_code"] == 32611
        np.testing.assert_allclose(result.ionosphere, [[0.1, 0.2], [0.3, 0.4]])
        assert result.ionosphere_unc.attrs["units"] == "radians"
        assert result.hydro_tropo.dims == ("radar_height", "radar_y", "radar_x")
        assert result.radar_height.attrs["units"] == "m"
        assert result.wet_tropo.attrs["correction_status"] == "available_not_applied"
        assert result.attrs["correction_layers_applied"] is False
        assert result.attrs["incidence_angle_source"].startswith("DEM elevation")
        assert "heightAboveEllipsoid" in result.attrs["incidence_angle_source"]
    finally:
        result.close()


def test_nisar_adapter_converts_times_and_rejects_reversed_pairs(tmp_path):
    h5netcdf = pytest.importorskip("h5netcdf")
    offset_path = tmp_path / "test_gunw_time_offsets.h5"
    _write_synthetic_gunw(
        h5netcdf,
        offset_path,
        reference_time="2025-01-01T04:00:00+04:00",
        secondary_time="2025-01-12T19:00:00-05:00",
    )
    result = open_gunw(offset_path, chunks=None, progress=False)
    try:
        assert result.attrs["reference_time"] == "2025-01-01T00:00:00Z"
        assert result.attrs["secondary_time"] == "2025-01-13T00:00:00Z"
    finally:
        result.close()

    reversed_path = tmp_path / "test_gunw_reversed_times.h5"
    _write_synthetic_gunw(
        h5netcdf,
        reversed_path,
        reference_time="2025-01-13T00:00:00Z",
        secondary_time="2025-01-01T00:00:00Z",
    )
    with pytest.raises(ValueError, match="secondary_time must be later"):
        open_gunw(reversed_path, chunks=None, progress=False)


def test_nisar_adapter_supports_alternate_polarization_and_optional_layers(tmp_path):
    h5netcdf = pytest.importorskip("h5netcdf")
    path = tmp_path / "test_gunw_vv.h5"
    _write_synthetic_gunw(
        h5netcdf, path, polarization="VV", include_optional_layers=False
    )

    result = open_gunw(path, chunks=None, progress=False)
    try:
        assert result.phase.attrs["source_variable"] == "unwrappedPhase"
        assert "coherence" not in result
        assert result.attrs["source_granule_id"] == "synthetic-gunw-VV"
    finally:
        result.close()


def test_nisar_adapter_reads_nondefault_frequency_and_grid_orientation(tmp_path):
    h5netcdf = pytest.importorskip("h5netcdf")
    path = tmp_path / "variant_frequencyB_vv.nc"
    _write_synthetic_gunw(
        h5netcdf,
        path,
        frequency="frequencyB",
        polarization="VV",
        x_coordinates=(110.0, 100.0),
        y_coordinates=(10.0, 20.0),
        center_frequency_hz=1.25e9,
        include_connected_components=True,
    )

    result = open_gunw(
        path, frequency="frequencyB", polarization="VV", chunks=None, progress=False
    )
    try:
        assert result.sizes["y"] == result.sizes["x"] == 2
        assert result.sizes["radar_height"] == 2
        np.testing.assert_array_equal(result.x, [110.0, 100.0])
        np.testing.assert_array_equal(result.y, [10.0, 20.0])
        np.testing.assert_array_equal(result.phase, [[-1.0, -2.0], [-3.0, -4.0]])
        np.testing.assert_array_equal(result.connected_component, [[4, 4], [8, 8]])
        assert result.attrs["wavelength_m"] == pytest.approx(299792458.0 / 1.25e9)
        assert result.phase.attrs["grid_mapping"] == "spatial_ref"
        assert "/frequencyB/" in result.attrs["source_dataset_paths"]
        assert result.attrs["source_granule_id"] == "synthetic-gunw-VV"
    finally:
        result.close()


def test_nisar_adapter_rejects_missing_required_projection(tmp_path):
    h5netcdf = pytest.importorskip("h5netcdf")
    path = tmp_path / "test_gunw_missing_projection.h5"
    _write_synthetic_gunw(h5netcdf, path, include_projection=False)

    with pytest.raises(ValueError, match="missing its projection"):
        open_gunw(path, chunks=None, progress=False)


def test_open_gunw_defers_geometry_and_incidence_requires_explicit_gunw(tmp_path):
    h5netcdf = pytest.importorskip("h5netcdf")
    path = tmp_path / "test_gunw_deferred_geometry.h5"
    _write_synthetic_gunw(h5netcdf, path)

    result = open_gunw(path, chunks=None, progress=False)
    try:
        assert "incidence_angle" not in result
        assert result.attrs["incidence_angle_status"] == "not_computed"
        assert result.attrs["snowin_data_state"] == "phase_normalized_product"
        with pytest.raises(FileNotFoundError, match="GUNW file not found"):
            compute_gunw_incidence(tmp_path / "different_product.h5", result)
    finally:
        result.close()


def test_gunw_incidence_rejects_source_granule_mismatch(tmp_path):
    h5netcdf = pytest.importorskip("h5netcdf")
    target_path = tmp_path / "target_gunw.h5"
    other_path = tmp_path / "other_gunw.h5"
    _write_synthetic_gunw(h5netcdf, target_path, granule_id="target-granule")
    _write_synthetic_gunw(h5netcdf, other_path, granule_id="other-granule")

    target = open_gunw(target_path, chunks=None, progress=False)
    try:
        with pytest.raises(ValueError, match="does not match target source_granule_id"):
            compute_gunw_incidence(
                other_path,
                target,
                dem_source="cop30",
                dem=_synthetic_dem(),
                progress=False,
            )
    finally:
        target.close()


def test_product_ellipsoid_incidence_ignores_unrelated_mixed_dimension_layers(
    tmp_path,
):
    h5netcdf = pytest.importorskip("h5netcdf")
    h5py = pytest.importorskip("h5py")
    path = tmp_path / "test_gunw_ellipsoid.h5"
    _write_synthetic_gunw(h5netcdf, path)
    with h5py.File(path, "a") as source:
        radar = source["science/LSAR/GUNW/metadata/radarGrid"]
        baseline = radar.create_dataset(
            "parallelBaseline", data=np.zeros((2, 2, 2), dtype="float32")
        )
        baseline.dims[1].attach_scale(radar["yCoordinates"])
        baseline.dims[2].attach_scale(radar["xCoordinates"])

    result = open_gunw(path, chunks=None, progress=False)
    try:
        add_gunw_incidence(
            result, path, incidence_source="product_ellipsoid", progress=False
        )
        assert result.incidence_angle.attrs["incidence_angle_reference"] == "ellipsoid"
        assert result.incidence_angle.attrs["units"] == "rad"
        assert result.incidence_angle.sizes == result.phase.sizes
        np.testing.assert_array_equal(
            result.incidence_angle.coords["x"], result.phase.coords["x"]
        )
        np.testing.assert_array_equal(
            result.incidence_angle.coords["y"], result.phase.coords["y"]
        )
        np.testing.assert_allclose(result.incidence_angle.values, np.deg2rad(30.0))
        assert result.incidence_angle.attrs["source_units"] == "degrees"
        assert result.incidence_angle.attrs["incidence_angle_origin"] == (
            "product_ellipsoid"
        )
        assert result.incidence_angle.attrs["incidence_angle_resampling"] == "none"
        assert result.incidence_angle.attrs[
            "incidence_angle_source_dataset_path"
        ].endswith("/incidenceAngle")
    finally:
        result.close()


def test_local_incidence_requires_a_prepared_dem(tmp_path):
    h5netcdf = pytest.importorskip("h5netcdf")
    path = tmp_path / "test_gunw_default.h5"
    _write_synthetic_gunw(h5netcdf, path)

    result = open_gunw(path, chunks=None, progress=False)
    try:
        with pytest.raises(ValueError, match="caller-supplied prepared DEM"):
            add_gunw_incidence(result, path, progress=False)
    finally:
        result.close()


def test_recommended_nisar_dem_and_product_incidence_emit_no_warning(tmp_path):
    h5netcdf = pytest.importorskip("h5netcdf")
    path = tmp_path / "test_gunw_nisar_dem_recommendation.h5"
    _write_synthetic_gunw(h5netcdf, path)

    local = open_gunw(path, chunks=None, progress=False)
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            add_gunw_incidence(
                local,
                path,
                dem_source="nisar_cop30",
                dem=_synthetic_dem(),
                progress=False,
            )
        assert not caught
        assert local.incidence_angle.attrs["dem_grid_alignment"] == "already_aligned"
        assert local.incidence_angle.attrs["dem_resampling_method"] == "none"
    finally:
        local.close()

    product = open_gunw(path, chunks=None, progress=False)
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            add_gunw_incidence(
                product,
                path,
                incidence_source="product_ellipsoid",
                progress=False,
            )
        assert not caught
    finally:
        product.close()


def test_gunw_wavelength_can_be_explicitly_overridden(tmp_path):
    h5netcdf = pytest.importorskip("h5netcdf")
    path = tmp_path / "test_gunw_wavelength_override.h5"
    _write_synthetic_gunw(h5netcdf, path)

    result = open_gunw(path, wavelength_m=0.123, chunks=None, progress=False)
    try:
        with pytest.warns(UserWarning, match='dem_source="nisar_cop30"'):
            add_gunw_incidence(
                result,
                path,
                dem_source="cop30",
                dem=_synthetic_dem(),
                progress=False,
            )
        assert result.attrs["wavelength_m"] == pytest.approx(0.123)
        assert result.attrs["wavelength_source"] == "explicit wavelength_m override"
    finally:
        result.close()


def test_tandem30_dem_source_uses_local_ellipsoidal_input(tmp_path):
    pytest.importorskip("scipy")
    h5netcdf = pytest.importorskip("h5netcdf")
    path = tmp_path / "test_gunw_tandem30.h5"
    _write_synthetic_gunw(h5netcdf, path)

    result = open_gunw(path, chunks=None, progress=False)
    try:
        with pytest.warns(UserWarning, match='dem_source="nisar_cop30"'):
            add_gunw_incidence(
                result,
                path,
                dem_source="tandem30",
                dem=_synthetic_dem(),
                require_vertical_datum_match=True,
                progress=False,
            )
        assert result.attrs["dem_source"] == "tandem30"
        assert result.attrs["dem_product"] == "TanDEM-X 30 m DEM"
        assert result.attrs["dem_height_reference"] == "ellipsoidal"
        assert result.attrs["vertical_datum_status"] == "matched"
    finally:
        result.close()


def test_srtm30_requires_vertical_correction_for_strict_matching(tmp_path):
    pytest.importorskip("scipy")
    h5netcdf = pytest.importorskip("h5netcdf")
    path = tmp_path / "test_gunw_srtm30.h5"
    _write_synthetic_gunw(h5netcdf, path)

    with (
        pytest.warns(UserWarning, match='dem_source="nisar_cop30"'),
        pytest.raises(ValueError, match="SRTM 30 m DEM heights"),
    ):
        result = open_gunw(path, chunks=None, progress=False)
        add_gunw_incidence(
            result,
            path,
            dem_source="srtm30",
            dem=_synthetic_dem(),
            require_vertical_datum_match=True,
            progress=False,
        )


def test_nisar_adapter_preserves_dask_backing_when_available(tmp_path):
    pytest.importorskip("scipy")
    pytest.importorskip("dask.array")
    h5netcdf = pytest.importorskip("h5netcdf")
    path = tmp_path / "test_gunw_dask.h5"
    _write_synthetic_gunw(h5netcdf, path)

    result = open_gunw(path, chunks="auto", progress=False)
    try:
        with pytest.warns(UserWarning, match='dem_source="nisar_cop30"'):
            add_gunw_incidence(
                result,
                path,
                dem_source="cop30",
                dem=_synthetic_dem(),
                progress=False,
            )
        assert hasattr(result.phase.data, "chunks")
        np.testing.assert_allclose(
            result.phase.compute().values,
            [[-1.0, -2.0], [-3.0, -4.0]],
        )
    finally:
        result.close()


def test_nisar_adapter_chunked_geometry_is_lazy_and_matches_eager(tmp_path):
    pytest.importorskip("scipy")
    pytest.importorskip("dask.array")
    h5netcdf = pytest.importorskip("h5netcdf")
    path = tmp_path / "test_gunw_chunked_geometry.h5"
    _write_synthetic_gunw(h5netcdf, path)

    eager = open_gunw(path, chunks=None, progress=False)
    chunked = open_gunw(path, chunks=None, progress=False)
    try:
        with pytest.warns(UserWarning, match='dem_source="nisar_cop30"'):
            add_gunw_incidence(
                eager,
                path,
                dem_source="cop30",
                dem=_synthetic_dem(),
                progress=False,
            )
        with pytest.warns(UserWarning, match='dem_source="nisar_cop30"'):
            add_gunw_incidence(
                chunked,
                path,
                dem_source="cop30",
                dem=_synthetic_dem(),
                geometry_chunks=(1, 1),
                progress=False,
            )
        assert chunked.incidence_angle.attrs["geometry_execution"] == (
            "dask_chunked_prototype"
        )
        assert chunked.incidence_angle.attrs["geometry_chunks"] == "1,1"
        assert hasattr(chunked.incidence_angle.data, "chunks")
        np.testing.assert_allclose(
            chunked.incidence_angle.compute().values,
            eager.incidence_angle.values,
        )
    finally:
        eager.close()
        chunked.close()


def _write_synthetic_gunw(
    h5netcdf,
    path,
    *,
    frequency="frequencyA",
    polarization="HH",
    include_optional_layers=True,
    include_projection=True,
    include_connected_components=False,
    include_correction_layers=True,
    granule_id=None,
    x_coordinates=(100.0, 110.0),
    y_coordinates=(20.0, 10.0),
    center_frequency_hz=1.0e9,
    reference_time="2025-01-01T00:00:00.000000000",
    secondary_time="2025-01-13T00:00:00.000000000",
):
    import h5py

    with h5netcdf.File(path, "w") as root:
        base = root.create_group("science/LSAR/GUNW")
        grids = base.create_group(f"grids/{frequency}")
        center = grids.create_variable("centerFrequency", (), float)
        center[()] = center_frequency_hz
        center.attrs["units"] = "hertz"

        phase_group = grids.create_group(f"unwrappedInterferogram/{polarization}")
        phase_group.dimensions = {"y": 2, "x": 2}
        phase_group.create_variable("xCoordinates", ("x",), float)[:] = x_coordinates
        phase_group.create_variable("yCoordinates", ("y",), float)[:] = y_coordinates
        phase = phase_group.create_variable("unwrappedPhase", ("y", "x"), float)
        phase[:] = [[1.0, 2.0], [3.0, 4.0]]
        phase.attrs["units"] = "radians"
        if include_optional_layers:
            coherence = phase_group.create_variable(
                "coherenceMagnitude", ("y", "x"), float
            )
            coherence[:] = 0.8
            coherence.attrs["units"] = "1"
        if include_connected_components:
            components = phase_group.create_variable(
                "connectedComponents", ("y", "x"), "i4"
            )
            components[:] = [[4, 4], [8, 8]]
        if include_correction_layers:
            ionosphere = phase_group.create_variable(
                "ionospherePhaseScreen", ("y", "x"), float
            )
            ionosphere[:] = [[0.1, 0.2], [0.3, 0.4]]
            ionosphere.attrs["units"] = "radians"
            ionosphere_uncertainty = phase_group.create_variable(
                "ionospherePhaseScreenUncertainty", ("y", "x"), float
            )
            ionosphere_uncertainty[:] = 0.01
            ionosphere_uncertainty.attrs["units"] = "radians"
        if include_projection:
            projection = phase_group.create_variable("projection", (), "u4")
            projection[()] = 32611
            projection.attrs["epsg_code"] = 32611
            projection.attrs["spatial_ref"] = "EPSG:32611"

        radar = base.create_group("metadata/radarGrid")
        radar.dimensions = {"height": 2, "y": 2, "x": 2}
        radar.create_variable("xCoordinates", ("x",), float)[:] = x_coordinates
        radar.create_variable("yCoordinates", ("y",), float)[:] = y_coordinates
        radar.create_variable("heightAboveEllipsoid", ("height",), float)[:] = [
            -1.0,
            1.0,
        ]
        incidence = radar.create_variable("incidenceAngle", ("height", "y", "x"), float)
        incidence[:] = 30.0
        incidence.attrs["units"] = "degrees"
        hydro_tropo = radar.create_variable(
            "hydrostaticTroposphericPhaseScreen", ("height", "y", "x"), float
        )
        hydro_tropo[:] = 0.02
        hydro_tropo.attrs["units"] = "radians"
        wet_tropo = radar.create_variable(
            "wetTroposphericPhaseScreen", ("height", "y", "x"), float
        )
        wet_tropo[:] = 0.03
        wet_tropo.attrs["units"] = "radians"
        los_x = radar.create_variable("losUnitVectorX", ("height", "y", "x"), float)
        los_x[:] = math.sin(math.radians(30.0))
        los_y = radar.create_variable("losUnitVectorY", ("height", "y", "x"), float)
        los_y[:] = 0.0

        ident = root.create_group("science/LSAR/identification")
        for name, value in {
            "productType": "GUNW",
            "granuleId": (
                granule_id
                if granule_id is not None
                else f"synthetic-gunw-{polarization}"
            ),
            "referenceZeroDopplerStartTime": reference_time,
            "secondaryZeroDopplerStartTime": secondary_time,
        }.items():
            variable = ident.create_variable(
                name, (), h5py.string_dtype(encoding="utf-8")
            )
            variable[()] = value

    with h5py.File(path, "r+") as root:
        if include_projection:
            # Match the scalar EPSG attribute representation in NISAR GUNW files.
            projection_attrs = root[
                f"science/LSAR/GUNW/grids/{frequency}/"
                f"unwrappedInterferogram/{polarization}/projection"
            ].attrs
            del projection_attrs["epsg_code"]
            projection_attrs["epsg_code"] = np.int64(32611)

        # Match NISAR's HDF5 dimension scales so nisar_pytools can retain the
        # source x/y grid on each layer.
        scale_specs = (
            (
                f"/science/LSAR/GUNW/grids/{frequency}/unwrappedInterferogram/{polarization}",
                {"y": "yCoordinates", "x": "xCoordinates"},
                {
                    name: ("y", "x")
                    for name in (
                        "unwrappedPhase",
                        "coherenceMagnitude",
                        "connectedComponents",
                        "ionospherePhaseScreen",
                        "ionospherePhaseScreenUncertainty",
                    )
                    if name
                    in root[
                        f"science/LSAR/GUNW/grids/{frequency}/"
                        f"unwrappedInterferogram/{polarization}"
                    ]
                },
            ),
            (
                "/science/LSAR/GUNW/metadata/radarGrid",
                {
                    "height": "heightAboveEllipsoid",
                    "y": "yCoordinates",
                    "x": "xCoordinates",
                },
                {
                    name: ("height", "y", "x")
                    for name in (
                        "incidenceAngle",
                        "losUnitVectorX",
                        "losUnitVectorY",
                        "hydrostaticTroposphericPhaseScreen",
                        "wetTroposphericPhaseScreen",
                    )
                    if name in root["/science/LSAR/GUNW/metadata/radarGrid"]
                },
            ),
        )
        for group_path, coordinate_names, variable_dimensions in scale_specs:
            group = root[group_path]
            scales = {
                dim: group[coordinate_name]
                for dim, coordinate_name in coordinate_names.items()
            }
            for dim, scale in scales.items():
                if not scale.is_scale:
                    for old_scale in list(scale.dims[0].values()):
                        scale.dims[0].detach_scale(old_scale)
                    scale.make_scale(dim)
            for name, dimensions in variable_dimensions.items():
                variable = group[name]
                for axis, dim in enumerate(dimensions):
                    for old_scale in list(variable.dims[axis].values()):
                        variable.dims[axis].detach_scale(old_scale)
                    variable.dims[axis].label = dim
                    variable.dims[axis].attach_scale(scales[dim])


def _synthetic_dem() -> xr.DataArray:
    return xr.DataArray(
        np.zeros((2, 2), dtype=float),
        dims=("y", "x"),
        coords={"y": [20.0, 10.0], "x": [100.0, 110.0]},
        attrs={"units": "m", "epsg_code": 32611},
        name="cop30_elevation",
    )
