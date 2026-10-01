"""Geometry invariants and optional real-product regression coverage."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from snowin.io._nisar_hdf5 import _read_radar_los
from snowin.io.geometry import (
    _open_cop30_dem,
    compute_cop30_local_incidence,
)


def _constant_los(angle_rad: float, shape: tuple[int, int, int]):
    height, y, x = shape
    return (
        np.full(shape, np.sin(angle_rad)),
        np.zeros((height, y, x)),
        np.full(shape, np.cos(angle_rad)),
    )


def _dem(values: np.ndarray, *, x=None, y=None, attrs=None) -> xr.DataArray:
    y = np.arange(values.shape[0], dtype=float) if y is None else y
    x = np.arange(values.shape[1], dtype=float) if x is None else x
    return xr.DataArray(
        values,
        dims=("y", "x"),
        coords={"y": y, "x": x},
        attrs={"units": "m", "epsg_code": 32613, **(attrs or {})},
    )


def test_flat_dem_returns_known_incidence_angle():
    incidence = compute_cop30_local_incidence(
        _dem(np.full((3, 3), 100.0)),
        *_constant_los(np.deg2rad(30.0), (2, 3, 3)),
        heights=np.array([0.0, 200.0]),
        x_radar=np.array([0.0, 1.0, 2.0]),
        y_radar=np.array([0.0, 1.0, 2.0]),
    )
    np.testing.assert_allclose(incidence, np.deg2rad(30.0), atol=1e-6)
    assert incidence.attrs["units"] == "rad"
    assert incidence.attrs["incidence_angle_reference"] == "local"


def test_sloped_dem_returns_known_incidence_angle():
    x = np.arange(3, dtype=float)
    dem = _dem(np.broadcast_to(0.1 * x, (3, 3)), x=x)
    incidence = compute_cop30_local_incidence(
        dem,
        *_constant_los(0.0, (2, 3, 3)),
        heights=np.array([-1.0, 1.0]),
        x_radar=x,
        y_radar=np.arange(3, dtype=float),
    )
    np.testing.assert_allclose(incidence, np.arctan(0.1), atol=1e-6)


def test_back_facing_terrain_has_missing_incidence_support():
    x = np.arange(3, dtype=float)
    dem = _dem(np.broadcast_to(10.0 * x, (3, 3)), x=x)
    incidence = compute_cop30_local_incidence(
        dem,
        *_constant_los(np.deg2rad(40.0), (2, 3, 3)),
        heights=np.array([-1.0, 21.0]),
        x_radar=x,
        y_radar=np.arange(3, dtype=float),
    )
    assert np.isnan(incidence.values).all()
    assert incidence.attrs["valid_max_exclusive"] is True


def test_larger_grid_geometry_is_finite_and_shape_preserving():
    y = np.arange(16, dtype=float)
    x = np.arange(20, dtype=float)
    dem = _dem(np.broadcast_to(0.02 * x[None, :], (y.size, x.size)), x=x, y=y)
    incidence = compute_cop30_local_incidence(
        dem,
        *_constant_los(np.deg2rad(35.0), (3, y.size, x.size)),
        heights=np.array([-1.0, 100.0, 201.0]),
        x_radar=x,
        y_radar=y,
    )
    assert incidence.shape == (16, 20)
    assert np.isfinite(incidence.values).all()
    expected = np.arccos(
        (np.sin(np.deg2rad(35.0)) * -0.02 + np.cos(np.deg2rad(35.0)))
        / np.sqrt(1.0 + 0.02**2)
    )
    np.testing.assert_allclose(incidence.values, expected, atol=1e-6)


def test_vertical_correction_is_explicit_and_additive():
    dem = _dem(
        np.full((3, 3), 100.0),
        attrs={"vertical_datum": "EGM2008", "height_reference": "orthometric"},
    )
    correction = xr.DataArray(
        np.full((3, 3), 10.0),
        dims=("y", "x"),
        coords=dem.coords,
        attrs={"units": "m"},
    )
    incidence = compute_cop30_local_incidence(
        dem,
        *_constant_los(np.deg2rad(30.0), (2, 3, 3)),
        heights=np.array([105.0, 115.0]),
        x_radar=np.array([0.0, 1.0, 2.0]),
        y_radar=np.array([0.0, 1.0, 2.0]),
        vertical_correction_m=correction,
        require_vertical_datum_match=True,
    )
    np.testing.assert_allclose(incidence, np.deg2rad(30.0), atol=1e-6)
    assert incidence.attrs["vertical_datum_status"] == (
        "corrected_with_supplied_geoid_undulation"
    )


def test_vertical_datum_match_can_be_required():
    dem = _dem(
        np.full((3, 3), 100.0),
        attrs={"vertical_datum": "EGM2008", "height_reference": "orthometric"},
    )
    with pytest.raises(ValueError, match="vertical_correction_m"):
        compute_cop30_local_incidence(
            dem,
            *_constant_los(np.deg2rad(30.0), (2, 3, 3)),
            heights=np.array([0.0, 200.0]),
            x_radar=np.array([0.0, 1.0, 2.0]),
            y_radar=np.array([0.0, 1.0, 2.0]),
            require_vertical_datum_match=True,
        )


def test_vertical_correction_requires_metre_units():
    dem = _dem(
        np.full((3, 3), 100.0),
        attrs={"vertical_datum": "EGM2008", "height_reference": "orthometric"},
    )
    correction = xr.DataArray(
        np.zeros((3, 3)),
        dims=("y", "x"),
        coords=dem.coords,
        attrs={"units": "feet"},
    )
    with pytest.raises(ValueError, match="units of metres"):
        compute_cop30_local_incidence(
            dem,
            *_constant_los(np.deg2rad(30.0), (2, 3, 3)),
            heights=np.array([0.0, 200.0]),
            x_radar=np.array([0.0, 1.0, 2.0]),
            y_radar=np.array([0.0, 1.0, 2.0]),
            vertical_correction_m=correction,
        )


def test_vertical_correction_raster_is_reprojected(tmp_path):
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin

    correction_path = tmp_path / "egm2008_geoid_undulation.tif"
    with rasterio.open(
        correction_path,
        "w",
        driver="GTiff",
        height=3,
        width=3,
        count=1,
        dtype="float32",
        crs="EPSG:32613",
        transform=from_origin(-0.5, 2.5, 1.0, 1.0),
        nodata=-9999.0,
    ) as dst:
        dst.write(np.full((3, 3), 10.0, dtype="float32"), 1)

    dem = _dem(
        np.full((3, 3), 100.0),
        attrs={"vertical_datum": "EGM2008", "height_reference": "orthometric"},
    )
    incidence = compute_cop30_local_incidence(
        dem,
        *_constant_los(np.deg2rad(30.0), (2, 3, 3)),
        heights=np.array([105.0, 115.0]),
        x_radar=np.array([0.0, 1.0, 2.0]),
        y_radar=np.array([0.0, 1.0, 2.0]),
        vertical_correction_m=correction_path,
        require_vertical_datum_match=True,
    )
    np.testing.assert_allclose(incidence, np.deg2rad(30.0), atol=1e-6)
    assert incidence.attrs["vertical_datum_status"] == (
        "corrected_with_supplied_geoid_undulation"
    )
    assert incidence.attrs["vertical_correction_source"] == str(correction_path)


def test_non_monotonic_los_coordinates_fail():
    with pytest.raises(ValueError, match="strictly monotonic"):
        compute_cop30_local_incidence(
            _dem(np.ones((3, 3))),
            *_constant_los(0.0, (2, 3, 3)),
            heights=np.array([0.0, 1.0]),
            x_radar=np.array([0.0, 2.0, 1.0]),
            y_radar=np.arange(3, dtype=float),
        )


def test_out_of_range_los_interpolation_fails():
    with pytest.raises(ValueError, match="outside the GUNW LOS lookup cube"):
        compute_cop30_local_incidence(
            _dem(np.full((3, 3), 100.0)),
            *_constant_los(0.0, (2, 3, 3)),
            heights=np.array([0.0, 1.0]),
            x_radar=np.arange(3, dtype=float),
            y_radar=np.arange(3, dtype=float),
        )


def test_dem_without_crs_fails(tmp_path):
    dem = _dem(np.ones((3, 3)), attrs={"epsg_code": None})
    dem.attrs.pop("epsg_code")
    with pytest.raises(ValueError, match="declare epsg_code"):
        _open_cop30_dem(dem, x=np.arange(3.0), y=np.arange(3.0), epsg_code=32613)


def test_non_overlapping_dem_fails():
    dem = _dem(
        np.ones((3, 3)),
        x=np.array([1000.0, 1001.0, 1002.0]),
        y=np.array([1000.0, 1001.0, 1002.0]),
    )
    with pytest.raises(ValueError, match="does not overlap"):
        _open_cop30_dem(dem, x=np.arange(3.0), y=np.arange(3.0), epsg_code=32613)


def test_missing_los_z_is_derived_from_xy(tmp_path):
    h5netcdf = pytest.importorskip("h5netcdf")

    path = tmp_path / "missing_z.h5"
    with h5netcdf.File(path, "w") as root:
        group = root.create_group("science/LSAR/GUNW/metadata/radarGrid")
        group.dimensions = {"height": 2, "y": 2, "x": 2}
        group.create_variable("heightAboveEllipsoid", ("height",), float)[:] = [
            0.0,
            1.0,
        ]
        group.create_variable("xCoordinates", ("x",), float)[:] = [0.0, 1.0]
        group.create_variable("yCoordinates", ("y",), float)[:] = [1.0, 0.0]
        group.create_variable("losUnitVectorX", ("height", "y", "x"), float)[:] = 0.6
        group.create_variable("losUnitVectorY", ("height", "y", "x"), float)[:] = 0.0

    _, _, _, los_x, los_y, los_z = _read_radar_los(path)
    np.testing.assert_allclose(los_x, 0.6)
    np.testing.assert_allclose(los_y, 0.0)
    np.testing.assert_allclose(los_z, 0.8)


def test_missing_xy_cannot_derive_los_z(tmp_path):
    h5netcdf = pytest.importorskip("h5netcdf")
    path = tmp_path / "missing_xy.h5"
    with h5netcdf.File(path, "w") as root:
        group = root.create_group("science/LSAR/GUNW/metadata/radarGrid")
        group.dimensions = {"height": 2, "y": 2, "x": 2}
        group.create_variable("heightAboveEllipsoid", ("height",), float)[:] = [
            0.0,
            1.0,
        ]
        group.create_variable("xCoordinates", ("x",), float)[:] = [0.0, 1.0]
        group.create_variable("yCoordinates", ("y",), float)[:] = [1.0, 0.0]
        group.create_variable("losUnitVectorX", ("height", "y", "x"), float)[:] = 0.6

    with pytest.raises(ValueError, match="missing LOS datasets"):
        _read_radar_los(path)


@pytest.mark.integration
def test_real_product_geometry_regression():
    manifest_path = Path(__file__).parent / "fixtures" / "real_product_geometry.json"
    manifest = json.loads(manifest_path.read_text())
    gunw = os.environ.get("SNOWIN_GEOMETRY_GUNW")
    dem_path = os.environ.get("SNOWIN_GEOMETRY_COP30_DEM")
    if not gunw or not dem_path:
        pytest.skip("set SNOWIN_GEOMETRY_GUNW and SNOWIN_GEOMETRY_COP30_DEM")

    gunw_path = Path(gunw)
    assert gunw_path.name == manifest["gunw_filename"]
    x = np.linspace(
        manifest["target_grid"]["x_start"],
        manifest["target_grid"]["x_stop"],
        manifest["target_grid"]["width"],
    )
    y = np.linspace(
        manifest["target_grid"]["y_start"],
        manifest["target_grid"]["y_stop"],
        manifest["target_grid"]["height"],
    )
    dem = _open_cop30_dem(
        dem_path,
        x=x,
        y=y,
        epsg_code=manifest["epsg_code"],
    )
    heights, x_radar, y_radar, los_x, los_y, los_z = _read_radar_los(gunw_path)
    incidence = compute_cop30_local_incidence(
        dem,
        los_x,
        los_y,
        los_z,
        heights,
        x_radar,
        y_radar,
        epsg_code=manifest["epsg_code"],
    )
    values = incidence.values
    expected = manifest["expected_incidence_rad"]
    assert float(np.isfinite(values).mean()) == pytest.approx(
        expected["valid_fraction"], abs=1e-12
    )
    for statistic in ("min", "max", "mean", "std", "p50"):
        actual = {
            "min": np.nanmin(values),
            "max": np.nanmax(values),
            "mean": np.nanmean(values),
            "std": np.nanstd(values),
            "p50": np.nanpercentile(values, 50),
        }[statistic]
        assert float(actual) == pytest.approx(
            expected[statistic], abs=manifest["tolerance_rad"]
        )
