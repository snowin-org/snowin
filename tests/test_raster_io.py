import numpy as np
import pytest

from snowin.io.raster import infer_affine_from_xy, write_geotiff


def test_infer_affine_from_xy_descending_y():
    transform = infer_affine_from_xy(np.array([10.0, 20.0]), np.array([100.0, 90.0]))
    assert transform.a == pytest.approx(10.0)
    assert transform.e == pytest.approx(-10.0)
    assert transform.c == pytest.approx(5.0)
    assert transform.f == pytest.approx(105.0)


def test_write_geotiff_roundtrip(tmp_path):
    rasterio = pytest.importorskip("rasterio")
    arr = np.array([[1.0, 2.0], [3.0, 4.0]])
    out = write_geotiff(
        tmp_path / "a.tif", arr, np.array([10.0, 20.0]), np.array([100.0, 90.0]), 32611
    )
    with rasterio.open(out) as src:
        assert src.crs.to_epsg() == 32611
        assert src.read(1).shape == (2, 2)


def test_write_geotiff_shape_mismatch(tmp_path):
    with pytest.raises(ValueError):
        write_geotiff(
            tmp_path / "a.tif",
            np.ones((2, 3)),
            np.array([1, 2]),
            np.array([3, 4]),
            32611,
        )
