"""Tests for the NISAR GUNW to normalized SnowIn Dataset boundary."""

from __future__ import annotations

import math

import numpy as np
import pytest
import xarray as xr

from snowin.io import (
    NISAR_GUNW_SOURCE_PHASE_DEFINITION,
    add_gunw_incidence,
    normalize_gunw_pair,
    open_gunw,
    read_gunw_wavelength_m,
)
from snowin.io.nisar import _nisar_dem_tile_url


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
    assert result.attrs["source_granule_id"] == "test-granule"
    assert result.spatial_ref.attrs["epsg_code"] == 32611


@pytest.mark.parametrize("source", [None, "unknown", "reference_minus_secondaryx"])
def test_normalize_gunw_pair_rejects_missing_or_unknown_source_convention(source):
    phase, incidence, spatial_ref = _pair_inputs()
    with pytest.raises(ValueError, match="missing or unknown"):
        normalize_gunw_pair(
            phase,
            incidence,
            wavelength_m=0.24,
            reference_time="2025-01-01T00:00:00Z",
            secondary_time="2025-01-13T00:00:00Z",
            source_phase_difference_definition=source,
            spatial_ref=spatial_ref,
        )


def test_normalize_gunw_pair_requires_explicit_radian_metadata():
    phase, incidence, spatial_ref = _pair_inputs()
    phase.attrs = {}
    with pytest.raises(ValueError, match="radians"):
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


def test_nisar_dem_tile_url_uses_documented_band_directories():
    assert _nisar_dem_tile_url(36, -109).endswith(
        "/EPSG4326/N30/N30_W120/DEM_N36_00_W109_00_C01.tif"
    )


def test_nisar_adapter_opens_lazy_normalized_gunw(tmp_path):
    pytest.importorskip("scipy")
    h5netcdf = pytest.importorskip("h5netcdf")
    path = tmp_path / "test_gunw.h5"
    _write_synthetic_gunw(h5netcdf, path)

    dem = _synthetic_dem()
    result = open_gunw(path, chunks=None, progress=False)
    try:
        assert "incidence_angle" not in result
        add_gunw_incidence(
            result, path, dem_source="cop30", cop30_dem=dem, progress=False
        )
        np.testing.assert_allclose(result.phase.values, [[-1.0, -2.0], [-3.0, -4.0]])
        assert result.phase.attrs["units"] == "rad"
        assert result.incidence_angle.attrs["units"] == "rad"
        assert result.incidence_angle.attrs["incidence_angle_reference"] == "local"
        np.testing.assert_allclose(result.incidence_angle.values, np.deg2rad(30.0))
        assert result.attrs["wavelength_m"] == pytest.approx(0.299792458)
        assert result.attrs["source_phase_difference_definition"] == (
            "reference_minus_secondary"
        )
        assert result.attrs["phase_transform"] == "multiply_by_-1"
        assert result.attrs["temporal_edge"] == "reference_to_secondary"
        assert result.attrs["incidence_angle_source"].startswith("COP30 DEM")
    finally:
        result.close()


def test_product_ellipsoid_incidence_requires_explicit_opt_in(tmp_path):
    h5netcdf = pytest.importorskip("h5netcdf")
    path = tmp_path / "test_gunw_ellipsoid.h5"
    _write_synthetic_gunw(h5netcdf, path)

    result = open_gunw(path, chunks=None, progress=False)
    try:
        add_gunw_incidence(
            result, path, incidence_source="product_ellipsoid", progress=False
        )
        assert result.incidence_angle.attrs["incidence_angle_reference"] == "ellipsoid"
        np.testing.assert_allclose(result.incidence_angle.values, np.deg2rad(30.0))
    finally:
        result.close()


def test_nisar_cop30_local_incidence_downloads_dem_by_default(tmp_path, monkeypatch):
    h5netcdf = pytest.importorskip("h5netcdf")
    path = tmp_path / "test_gunw_default.h5"
    _write_synthetic_gunw(h5netcdf, path)

    calls = []

    def fake_download(*args, **kwargs):
        calls.append((args, kwargs))
        return _synthetic_dem()

    monkeypatch.setattr(
        "snowin.io.nisar.download_nisar_cop30_dem_for_gunw", fake_download
    )
    result = open_gunw(path, chunks=None, progress=False)
    try:
        add_gunw_incidence(result, path, progress=False)
        assert len(calls) == 1
        assert result.attrs["incidence_angle_reference"] == "local terrain surface"
        assert result.attrs["dem_source"] == "nisar_cop30"
        assert result.attrs["wavelength_m"] == pytest.approx(0.299792458)
    finally:
        result.close()


def test_gunw_wavelength_can_be_explicitly_overridden(tmp_path):
    h5netcdf = pytest.importorskip("h5netcdf")
    path = tmp_path / "test_gunw_wavelength_override.h5"
    _write_synthetic_gunw(h5netcdf, path)

    result = open_gunw(path, wavelength_m=0.123, chunks=None, progress=False)
    try:
        add_gunw_incidence(
            result,
            path,
            dem_source="cop30",
            cop30_dem=_synthetic_dem(),
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
        add_gunw_incidence(
            result,
            path,
            dem_source="tandem30",
            tandem30_dem=_synthetic_dem(),
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

    with pytest.raises(ValueError, match="SRTM 30 m DEM heights"):
        result = open_gunw(path, chunks=None, progress=False)
        add_gunw_incidence(
            result,
            path,
            dem_source="srtm30",
            srtm30_dem=_synthetic_dem(),
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
        add_gunw_incidence(
            result,
            path,
            dem_source="cop30",
            cop30_dem=_synthetic_dem(),
            progress=False,
        )
        assert hasattr(result.phase.data, "chunks")
        np.testing.assert_allclose(
            result.phase.compute().values,
            [[-1.0, -2.0], [-3.0, -4.0]],
        )
    finally:
        result.close()


def _write_synthetic_gunw(h5netcdf, path):
    import h5py

    with h5netcdf.File(path, "w") as root:
        base = root.create_group("science/LSAR/GUNW")
        grids = base.create_group("grids/frequencyA")
        center = grids.create_variable("centerFrequency", (), float)
        center[()] = 1.0e9
        center.attrs["units"] = "hertz"

        phase_group = grids.create_group("unwrappedInterferogram/HH")
        phase_group.dimensions = {"y": 2, "x": 2}
        phase_group.create_variable("xCoordinates", ("x",), float)[:] = [100.0, 110.0]
        phase_group.create_variable("yCoordinates", ("y",), float)[:] = [20.0, 10.0]
        phase = phase_group.create_variable("unwrappedPhase", ("y", "x"), float)
        phase[:] = [[1.0, 2.0], [3.0, 4.0]]
        phase.attrs["units"] = "radians"
        coherence = phase_group.create_variable("coherenceMagnitude", ("y", "x"), float)
        coherence[:] = 0.8
        coherence.attrs["units"] = "1"
        projection = phase_group.create_variable("projection", (), "u4")
        projection[()] = 0
        projection.attrs["epsg_code"] = 32611
        projection.attrs["spatial_ref"] = "EPSG:32611"

        radar = base.create_group("metadata/radarGrid")
        radar.dimensions = {"height": 2, "y": 2, "x": 2}
        radar.create_variable("xCoordinates", ("x",), float)[:] = [100.0, 110.0]
        radar.create_variable("yCoordinates", ("y",), float)[:] = [20.0, 10.0]
        radar.create_variable("heightAboveEllipsoid", ("height",), float)[:] = [
            -1.0,
            1.0,
        ]
        incidence = radar.create_variable("incidenceAngle", ("height", "y", "x"), float)
        incidence[:] = 30.0
        incidence.attrs["units"] = "degrees"
        los_x = radar.create_variable("losUnitVectorX", ("height", "y", "x"), float)
        los_x[:] = math.sin(math.radians(30.0))
        los_y = radar.create_variable("losUnitVectorY", ("height", "y", "x"), float)
        los_y[:] = 0.0

        ident = root.create_group("science/LSAR/identification")
        for name, value in {
            "productType": "GUNW",
            "granuleId": "synthetic-gunw",
            "referenceZeroDopplerStartTime": "2025-01-01T00:00:00.000000000",
            "secondaryZeroDopplerStartTime": "2025-01-13T00:00:00.000000000",
        }.items():
            variable = ident.create_variable(
                name, (), h5py.string_dtype(encoding="utf-8")
            )
            variable[()] = value


def _synthetic_dem() -> xr.DataArray:
    return xr.DataArray(
        np.zeros((2, 2), dtype=float),
        dims=("y", "x"),
        coords={"y": [20.0, 10.0], "x": [100.0, 110.0]},
        attrs={"units": "m", "epsg_code": 32611},
        name="cop30_elevation",
    )
