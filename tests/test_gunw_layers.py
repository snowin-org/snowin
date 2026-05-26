import pytest

from snowin.io.gunw import STANDARD_GUNW_LAYER_NAMES, read_gunw_layers


def test_read_gunw_layers_polarization_override_and_metadata(monkeypatch, tmp_path):
    f = tmp_path / (
        "NISAR_L2_PR_GUNW_005_042_D_069_006_4000_SH_"
        "20251113T025606_20251113T025641_"
        "20251125T025606_20251125T025641_X05010_N_F_J_001.nc"
    )
    f.write_text("dummy")

    def fake_build_layers(path, pol, radar_cube_index=0):
        return (
            {name: None for name in STANDARD_GUNW_LAYER_NAMES},
            {name: f"/{name}" for name in STANDARD_GUNW_LAYER_NAMES},
        )

    monkeypatch.setattr("snowin.io.gunw.build_layers", fake_build_layers)
    monkeypatch.setattr(
        "snowin.io.gunw.read_identification_metadata", lambda path: {"trackNumber": 42}
    )

    out = read_gunw_layers(f, pol="VV")
    assert out.polarization == "VV"
    assert out.metadata["trackNumber"] == 42
    assert out.metadata["days_between"] == pytest.approx(12.0)
    assert tuple(out.layers) == STANDARD_GUNW_LAYER_NAMES


def test_read_gunw_layers_subset_and_missing_layers(monkeypatch, tmp_path):
    f = tmp_path / "x.nc"
    f.write_text("dummy")

    def fake_build_layers(path, pol, radar_cube_index=0):
        return (
            {"unwrapped_phase": None, "coherence_unw": object()},
            {"unwrapped_phase": "/a", "coherence_unw": "/b"},
        )

    monkeypatch.setattr("snowin.io.gunw.detect_pol", lambda path: "HH")
    monkeypatch.setattr("snowin.io.gunw.build_layers", fake_build_layers)
    monkeypatch.setattr("snowin.io.gunw.read_identification_metadata", lambda path: {})

    out = read_gunw_layers(f, layers=["unwrapped_phase", "coherence_unw"])
    assert out.polarization == "HH"
    assert out.layers["unwrapped_phase"] is None
    assert out.layers["coherence_unw"] is not None


def test_read_gunw_layers_unknown_layer_raises(monkeypatch, tmp_path):
    f = tmp_path / "x.nc"
    f.write_text("dummy")
    monkeypatch.setattr("snowin.io.gunw.detect_pol", lambda path: "HH")
    monkeypatch.setattr("snowin.io.gunw.build_layers", lambda *a, **k: ({}, {}))
    with pytest.raises(ValueError, match="Unknown GUNW layer"):
        read_gunw_layers(f, layers=["not_a_layer"])
