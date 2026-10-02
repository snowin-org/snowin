"""Offline checks for the opt-in NISAR GUNW downloader."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

from scripts.download_nisar_gunw import main


def _mock_nisar_pytools(monkeypatch):
    calls = {}
    product_url = "https://example.invalid/product/test_gunw.h5"

    def find_nisar(**kwargs):
        calls["search"] = kwargs
        return [product_url]

    def download_urls(urls, output_dir, *, max_workers, validate):
        calls["download"] = (urls, Path(output_dir), max_workers, validate)
        destination = Path(output_dir) / "test_gunw.h5"
        destination.write_bytes(b"mock validated product")
        return [destination]

    mocked_nisar_pytools = ModuleType("nisar_pytools")
    mocked_nisar_pytools.find_nisar = find_nisar
    mocked_nisar_pytools.download_urls = download_urls
    monkeypatch.setitem(sys.modules, "nisar_pytools", mocked_nisar_pytools)
    return calls, product_url


def _search_args(output_dir: Path) -> list[str]:
    return [
        "--aoi",
        "-112",
        "39",
        "-111",
        "40",
        "--start-date",
        "2025-08-01",
        "--end-date",
        "2025-09-01",
        "--output-dir",
        str(output_dir),
    ]


def test_dry_run_searches_but_does_not_create_directory_or_download(
    tmp_path, monkeypatch, capsys
):
    output_dir = tmp_path / "external" / "nisar" / "gunw"
    calls, _product_url = _mock_nisar_pytools(monkeypatch)

    assert main([*_search_args(output_dir), "--dry-run"]) == 0

    assert calls["search"] == {
        "aoi": [-112.0, 39.0, -111.0, 40.0],
        "start_date": "2025-08-01",
        "end_date": "2025-09-01",
        "product_type": "GUNW",
        "max_results": 20,
    }
    assert "download" not in calls
    assert not output_dir.exists()
    assert "Search-only dry run: no product was downloaded." in capsys.readouterr().out


def test_download_requires_index_and_writes_validated_product(
    tmp_path, monkeypatch, capsys
):
    output_dir = tmp_path / "external" / "nisar" / "gunw"
    calls, product_url = _mock_nisar_pytools(monkeypatch)

    assert main([*_search_args(output_dir), "--download-index", "0"]) == 0

    destination = output_dir / "test_gunw.h5"
    assert calls["download"] == ([product_url], output_dir, 1, True)
    assert destination.read_bytes() == b"mock validated product"
    assert str(destination) in capsys.readouterr().out
