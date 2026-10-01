"""Offline tests for Notebook 03's acquisition handoff."""

from __future__ import annotations

import builtins
import json
import sys
from pathlib import Path
from types import ModuleType


def test_notebook_03_search_download_and_path_handoff_are_mocked(
    tmp_path, monkeypatch, capsys
):
    notebook_path = (
        Path(__file__).parents[1]
        / "notebooks"
        / ("03_nisar_pytools_search_and_snowin.ipynb")
    )
    notebook = json.loads(notebook_path.read_text())
    code_cells = [
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    ]
    setup_cell = next(source for source in code_cells if "from nisar_pytools" in source)
    search_cell = next(source for source in code_cells if "find_nisar(" in source)
    download_cell = next(source for source in code_cells if "download_urls(" in source)

    prompts = iter(
        [
            "-112.0,39.0,-111.0,40.0",
            "2025-01-01",
            "2025-02-01",
            "0",
        ]
    )
    monkeypatch.setattr(builtins, "input", lambda _prompt: next(prompts))
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))
    monkeypatch.delenv("SNOWIN_GUNW", raising=False)

    calls = {}
    product_url = "https://example.invalid/product/test_gunw.h5"

    def find_nisar(**kwargs):
        calls["search"] = kwargs
        return [product_url]

    def download_urls(urls, output_dir, *, max_workers, validate):
        calls["download"] = (urls, Path(output_dir), max_workers, validate)
        destination = Path(output_dir) / "test_gunw.h5"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"mock validated product")
        return [destination]

    mocked_nisar_pytools = ModuleType("nisar_pytools")
    mocked_nisar_pytools.find_nisar = find_nisar
    mocked_nisar_pytools.download_urls = download_urls
    monkeypatch.setitem(sys.modules, "nisar_pytools", mocked_nisar_pytools)

    namespace = {}
    exec(setup_cell, namespace)
    exec(search_cell, namespace)
    exec(download_cell, namespace)

    expected_path = tmp_path / ".cache" / "snowin" / "nisar-products" / "test_gunw.h5"
    assert calls["search"] == {
        "aoi": [-112.0, 39.0, -111.0, 40.0],
        "start_date": "2025-01-01",
        "end_date": "2025-02-01",
        "product_type": "GUNW",
        "max_results": 20,
    }
    assert calls["download"] == ([product_url], expected_path.parent, 1, True)
    assert expected_path.read_bytes() == b"mock validated product"
    assert namespace["os"].environ["SNOWIN_GUNW"] == str(expected_path)
    output = capsys.readouterr().out
    assert str(expected_path.parent) in output
    assert f'SNOWIN_GUNW="{expected_path}"' in output
    assert "matching NISAR-modified Copernicus DEM" in output
