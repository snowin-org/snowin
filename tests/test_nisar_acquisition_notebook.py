"""Offline checks for Notebook 03's guarded acquisition handoff."""

from __future__ import annotations

import builtins
import json
import sys
from pathlib import Path
from types import ModuleType


def _notebook_cells():
    notebook_path = (
        Path(__file__).parents[1]
        / "notebooks"
        / "03_nisar_pytools_search_and_snowin.ipynb"
    )
    notebook = json.loads(notebook_path.read_text())
    return {
        cell["id"]: "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    }


def _mock_nisar_pytools(monkeypatch, calls):
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
    return product_url


def test_notebook_03_run_all_does_not_search_or_download(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(Path, "cwd", classmethod(lambda _cls: tmp_path))
    monkeypatch.setattr(
        builtins,
        "input",
        lambda _prompt: (_ for _ in ()).throw(AssertionError("unexpected prompt")),
    )
    calls = {}
    _mock_nisar_pytools(monkeypatch, calls)
    cells = _notebook_cells()
    namespace = {}

    for cell_id in ("handoff-search-params", "handoff-search", "handoff-download"):
        exec(cells[cell_id], namespace)

    assert namespace["RUN_REMOTE_SEARCH"] is False
    assert namespace["DOWNLOAD_PRODUCT_INDEX"] is None
    assert calls == {}
    assert not (tmp_path / "data" / "external" / "nisar" / "gunw").exists()
    output = capsys.readouterr().out
    assert "Remote search is disabled" in output
    assert "Product download is disabled" in output


def test_notebook_03_download_runs_only_after_explicit_configuration(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(Path, "cwd", classmethod(lambda _cls: tmp_path))
    prompts = iter(["-112.0,39.0,-111.0,40.0", "2025-08-01", "2025-09-01"])
    monkeypatch.setattr(builtins, "input", lambda _prompt: next(prompts))
    calls = {}
    product_url = _mock_nisar_pytools(monkeypatch, calls)
    cells = _notebook_cells()
    setup_cell = (
        cells["handoff-search-params"]
        .replace("RUN_REMOTE_SEARCH = False", "RUN_REMOTE_SEARCH = True")
        .replace("DOWNLOAD_PRODUCT_INDEX = None", "DOWNLOAD_PRODUCT_INDEX = 0")
    )
    namespace = {}

    exec(setup_cell, namespace)
    exec(cells["handoff-search"], namespace)
    exec(cells["handoff-download"], namespace)

    expected_dir = tmp_path / "data" / "external" / "nisar" / "gunw"
    expected_path = expected_dir / "test_gunw.h5"
    assert calls["search"] == {
        "aoi": [-112.0, 39.0, -111.0, 40.0],
        "start_date": "2025-08-01",
        "end_date": "2025-09-01",
        "product_type": "GUNW",
        "max_results": 20,
    }
    assert calls["download"] == ([product_url], expected_dir, 1, True)
    assert expected_path.read_bytes() == b"mock validated product"
    assert str(expected_path) in capsys.readouterr().out
