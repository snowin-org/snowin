"""CLI argument-to-public-workflow contract tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from snowin.cli import plot_gunw_cli


def test_plot_cli_passes_flags_to_workflow_and_reports_outputs(monkeypatch, capsys):
    calls = []

    def fake_plot_gunw(path, **kwargs):
        calls.append((path, kwargs))
        return SimpleNamespace(
            figure_paths=(Path("quickview.png"),),
            summary_csv_path=Path("summary.csv"),
            metadata_json_path=None,
        )

    monkeypatch.setattr("snowin.cli.plot_gunw", fake_plot_gunw)
    exit_code = plot_gunw_cli(
        [
            "pair.nc",
            "--out-dir",
            "results",
            "--crop-geojson",
            "region.geojson",
            "--grid-epsg",
            "32613",
            "--geojson-epsg",
            "4326",
            "--crop-padding",
            "12.5",
            "--no-mask-outside-geojson",
            "--pol",
            "VV",
            "--radar-cube-index",
            "1",
            "--dpi",
            "100",
            "--max-plot-dim",
            "1024",
            "--no-metadata",
            "--open",
        ]
    )

    assert exit_code == 0
    path, kwargs = calls[0]
    assert path == Path("pair.nc")
    assert kwargs["out_dir"] == Path("results")
    assert kwargs["crop_geojson"] == Path("region.geojson")
    assert kwargs["grid_epsg"] == 32613
    assert kwargs["geojson_epsg"] == 4326
    assert kwargs["crop_padding"] == 12.5
    assert kwargs["mask_outside_geojson"] is False
    assert kwargs["pol"] == "VV"
    assert kwargs["radar_cube_index"] == 1
    assert kwargs["dpi"] == 100
    assert kwargs["max_plot_dim"] == 1024
    assert kwargs["write_metadata"] is False
    assert kwargs["open_plot"] is True
    assert capsys.readouterr().out.splitlines() == [
        "figure: quickview.png",
        "summary_csv: summary.csv",
    ]
