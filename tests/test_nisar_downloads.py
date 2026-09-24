"""Mocked-download tests for public GUNW DEM staging workflows."""

from __future__ import annotations

import io
import netrc
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from snowin.io import nisar_product
from snowin.io.nisar_product import (
    _download_nisar_dem_tile,
    _open_nisar_dem_url,
    download_cop30_dem_for_gunw,
    download_nisar_cop30_dem_for_gunw,
)


def _geotiff_bytes(path):
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=80,
        width=80,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(-107.0, 42.0, 0.05, 0.05),
        tiled=True,
        blockxsize=16,
        blockysize=16,
    ) as dataset:
        dataset.write(np.arange(6400, dtype="float32").reshape(80, 80), 1)
    return path.read_bytes()


def _fixed_bounds(*args, **kwargs):
    return -106.5, 39.0, -104.5, 41.1


def test_public_cop30_download_mosaics_mocked_tiles_and_uses_cache(
    monkeypatch, tmp_path
):
    rasterio = pytest.importorskip("rasterio")

    tile_source = tmp_path / "source.tif"
    tile_bytes = _geotiff_bytes(tile_source)
    urls = []

    def fake_urlopen(url, timeout):
        urls.append((url, timeout))
        return io.BytesIO(tile_bytes)

    monkeypatch.setattr(nisar_product, "_gunw_geographic_bounds", _fixed_bounds)
    monkeypatch.setattr(nisar_product.urllib.request, "urlopen", fake_urlopen)
    output = tmp_path / "public" / "mosaic.tif"
    result = download_cop30_dem_for_gunw(
        "synthetic.h5",
        cache_dir=tmp_path / "cache",
        output_path=output,
        polarization="HH",
        progress=False,
    )

    assert result == output
    assert result.is_file()
    assert len(urls) == 9
    assert all(
        url.startswith("https://copernicus-dem-30m.s3.amazonaws.com/")
        for url, _ in urls
    )
    with rasterio.open(result) as dataset:
        assert dataset.crs.to_epsg() == 4326
        assert dataset.tags()["source_product"] == "Copernicus DEM GLO-30 Public"
        assert dataset.read(1).size > 0

    cached = download_cop30_dem_for_gunw(
        "synthetic.h5",
        cache_dir=tmp_path / "cache",
        output_path=output,
        polarization="HH",
        progress=False,
    )
    assert cached == output
    assert len(urls) == 9


def test_nisar_dem_download_mosaics_tiles_from_downloader_boundary(
    monkeypatch, tmp_path
):
    rasterio = pytest.importorskip("rasterio")
    source = tmp_path / "source.tif"
    _geotiff_bytes(source)
    downloaded = []

    def fake_download(url, destination):
        downloaded.append(url)
        destination.write_bytes(source.read_bytes())

    monkeypatch.setattr(nisar_product, "_gunw_geographic_bounds", _fixed_bounds)
    monkeypatch.setattr(nisar_product, "_download_nisar_dem_tile", fake_download)
    output = tmp_path / "nisar" / "mosaic.tif"
    result = download_nisar_cop30_dem_for_gunw(
        "synthetic.h5",
        cache_dir=tmp_path / "nisar-cache",
        output_path=output,
        polarization="VV",
        progress=False,
    )

    assert result == output
    assert output.is_file()
    assert len(downloaded) == 9
    assert all("/EPSG4326/" in url and "/DEM_" in url for url in downloaded)
    with rasterio.open(output) as dataset:
        assert dataset.crs.to_epsg() == 4326
        assert dataset.tags()["height_reference"] == "ellipsoidal"


def test_public_dem_download_failure_removes_partial_tile(monkeypatch, tmp_path):
    pytest.importorskip("rasterio")
    monkeypatch.setattr(nisar_product, "_gunw_geographic_bounds", _fixed_bounds)

    def fail_download(url, timeout):
        raise OSError("offline synthetic test")

    monkeypatch.setattr(nisar_product.urllib.request, "urlopen", fail_download)
    cache = tmp_path / "cache"
    with pytest.raises(RuntimeError, match="could not download public COP30 tile"):
        download_cop30_dem_for_gunw(
            "synthetic.h5",
            cache_dir=cache,
            output_path=tmp_path / "mosaic.tif",
            polarization="HH",
            progress=False,
        )
    assert not list(cache.rglob("*.part"))


def test_nisar_tile_download_uses_earthaccess_or_urllib_fallback(monkeypatch, tmp_path):
    destination = tmp_path / "tile.tif"
    earthaccess_file = tmp_path / "remote.tif"
    earthaccess_file.write_bytes(b"authenticated-data")
    calls = []
    fake_earthaccess = SimpleNamespace(
        login=lambda **kwargs: calls.append(("login", kwargs)),
        download=lambda url, **kwargs: (
            calls.append((url, kwargs)) or [earthaccess_file]
        ),
    )
    monkeypatch.setitem(sys.modules, "earthaccess", fake_earthaccess)
    _download_nisar_dem_tile("https://example.test/tile.tif", destination)
    assert destination.read_bytes() == b"authenticated-data"
    assert calls[0] == ("login", {"strategy": "netrc", "persist": False})

    fallback = tmp_path / "fallback.tif"
    monkeypatch.setitem(sys.modules, "earthaccess", None)
    monkeypatch.setattr(
        nisar_product,
        "_open_nisar_dem_url",
        lambda _url: io.BytesIO(b"fallback-data"),
    )
    _download_nisar_dem_tile("https://example.test/tile.tif", fallback)
    assert fallback.read_bytes() == b"fallback-data"
    assert not fallback.with_suffix(".part").exists()


def test_nisar_url_open_uses_unauthenticated_and_netrc_paths(monkeypatch):
    class NoCredentials:
        def authenticators(self, host):
            return None

    monkeypatch.setattr(netrc, "netrc", lambda: NoCredentials())
    calls = []
    monkeypatch.setattr(
        nisar_product.urllib.request,
        "urlopen",
        lambda url, timeout: calls.append((url, timeout)) or "response",
    )
    assert _open_nisar_dem_url("https://example.test/dem.tif", timeout=12) == "response"
    assert calls == [("https://example.test/dem.tif", 12)]

    class EarthdataCredentials:
        def authenticators(self, host):
            return ("user", "ignored", "password") if host == "example.test" else None

    class FakeOpener:
        def open(self, url, timeout):
            return (url, timeout)

    monkeypatch.setattr(netrc, "netrc", lambda: EarthdataCredentials())
    monkeypatch.setattr(
        nisar_product.urllib.request,
        "build_opener",
        lambda handler: FakeOpener(),
    )
    assert _open_nisar_dem_url("https://example.test/dem.tif", timeout=5) == (
        "https://example.test/dem.tif",
        5,
    )


def test_nisar_url_and_tile_helpers_reject_invalid_inputs():
    with pytest.raises(ValueError, match="invalid DEM URL"):
        _open_nisar_dem_url("not-a-url")

    assert nisar_product._cop30_tile_name(-1, 5) == (
        "Copernicus_DSM_COG_10_S01_00_E005_00_DEM"
    )
    assert nisar_product._nisar_dem_tile_name(-1, -5) == "DEM_S01_00_W005_00_C01.tif"
    assert "/S10/S10_W180/" in nisar_product._nisar_dem_tile_url(-1, -179)
