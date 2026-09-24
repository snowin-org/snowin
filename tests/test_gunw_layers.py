import numpy as np
import pytest

from snowin.io.gunw import (
    RADAR_GRID_GROUP,
    STANDARD_GUNW_LAYER_NAMES,
    UNWRAPPED_GROUP_TEMPLATE,
    decode_hdf5_scalar,
    detect_grid_epsg,
    detect_pol,
    open_group_dataset,
    parse_epsg_value,
    read_2d,
    read_attrs_hdf5,
    read_gunw_layers,
    read_radar_grid_slice,
    read_scalar_hdf5,
    try_read,
)


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


def test_hdf5_readers_preserve_gunw_grids_and_select_radar_slice(tmp_path):
    h5netcdf = pytest.importorskip("h5netcdf")
    path = tmp_path / (
        "NISAR_L2_PR_GUNW_005_042_D_069_006_4000_SH_"
        "20251113T025606_20251113T025641_"
        "20251125T025606_20251125T025641_X05010_N_F_J_001.h5"
    )
    _write_gunw_groups(h5netcdf, path)

    group = UNWRAPPED_GROUP_TEMPLATE.format(pol="VV")
    opened = open_group_dataset(path, group, "unwrappedPhase")
    assert opened.name == "unwrappedPhase"
    assert opened.dims == ("y", "x")
    phase = read_2d(path, group, "unwrappedPhase")
    np.testing.assert_array_equal(phase.coords["x"], [100.0, 110.0, 120.0])
    np.testing.assert_array_equal(phase.coords["y"], [20.0, 10.0])
    np.testing.assert_array_equal(phase, [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])

    incidence = read_radar_grid_slice(
        path,
        RADAR_GRID_GROUP,
        "incidenceAngle",
        radar_cube_index=1,
    )
    np.testing.assert_array_equal(incidence, np.full((2, 3), 40.0))
    assert detect_pol(path) == "VV"
    assert detect_grid_epsg(path) == 32613
    assert try_read(path, group, "absentLayer") is None

    selected = read_gunw_layers(path, layers=["unwrapped_phase", "incidence_angle"])
    assert selected.polarization == "VV"
    assert selected.layers["unwrapped_phase"].shape == (2, 3)
    assert selected.layers["incidence_angle"].shape == (2, 3)
    assert selected.metadata["days_between"] == pytest.approx(12.0)


@pytest.mark.parametrize(
    "value, expected",
    [(32611, 32611), (32612.0, 32612), ("EPSG:32613", 32613), (b"EPSG:32614", 32614)],
)
def test_epsg_parser_accepts_supported_hdf_scalar_encodings(value, expected):
    assert parse_epsg_value(value) == expected


def test_hdf5_scalar_and_attribute_decoding(tmp_path):
    h5py = pytest.importorskip("h5py")
    path = tmp_path / "metadata.h5"
    with h5py.File(path, "w") as h5:
        variable = h5.create_dataset("track", data=np.int32(42))
        variable.attrs["label"] = np.bytes_(b"track-number")
        h5.create_dataset("name", data=np.bytes_(b"synthetic-granule"))

    assert decode_hdf5_scalar(np.asarray(b"snow")) == "snow"
    assert decode_hdf5_scalar(np.array([b"a", b"b"])) == ["a", "b"]
    assert decode_hdf5_scalar(np.float32(2.5)) == pytest.approx(2.5)
    assert read_scalar_hdf5(path, "name") == "synthetic-granule"
    assert read_scalar_hdf5(path, "missing") is None
    assert read_attrs_hdf5(path, "track") == {"label": "track-number"}
    assert read_attrs_hdf5(path, "missing") == {}


def _write_gunw_groups(h5netcdf, path):
    with h5netcdf.File(path, "w") as root:
        base = root.create_group("science/LSAR/GUNW")
        grids = base.create_group("grids/frequencyA")
        projection = grids.create_variable("projection", (), "u4")
        projection[()] = 0
        projection.attrs["epsg_code"] = 32613

        unwrapped = grids.create_group("unwrappedInterferogram")
        unwrapped.dimensions = {"y": 2, "x": 3}
        for pol in ("VV",):
            group = unwrapped.create_group(pol)
            group.dimensions = {"y": 2, "x": 3}
            group.create_variable("xCoordinates", ("x",), float)[:] = [
                100.0,
                110.0,
                120.0,
            ]
            group.create_variable("yCoordinates", ("y",), float)[:] = [20.0, 10.0]
            phase = group.create_variable("unwrappedPhase", ("y", "x"), float)
            phase[:] = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
            phase.attrs["units"] = "radians"
            coherence = group.create_variable("coherenceMagnitude", ("y", "x"), float)
            coherence[:] = 0.8

        mask = unwrapped.create_variable("mask", ("y", "x"), "u1")
        mask[:] = 0
        wrapped = grids.create_group("wrappedInterferogram")
        wrapped.dimensions = {"y": 2, "x": 3}
        wrapped_vv = wrapped.create_group("VV")
        wrapped_vv.dimensions = {"y": 2, "x": 3}
        wrapped_vv.create_variable("xCoordinates", ("x",), float)[:] = [
            100.0,
            110.0,
            120.0,
        ]
        wrapped_vv.create_variable("yCoordinates", ("y",), float)[:] = [20.0, 10.0]
        ifg = wrapped_vv.create_variable("wrappedInterferogram", ("y", "x"), "c8")
        ifg[:] = 1 + 1j

        radar = base.create_group("metadata/radarGrid")
        radar.dimensions = {"height": 2, "y": 2, "x": 3}
        radar.create_variable("xCoordinates", ("x",), float)[:] = [
            100.0,
            110.0,
            120.0,
        ]
        radar.create_variable("yCoordinates", ("y",), float)[:] = [20.0, 10.0]
        incidence = radar.create_variable("incidenceAngle", ("height", "y", "x"), float)
        incidence[:] = np.stack([np.full((2, 3), 30.0), np.full((2, 3), 40.0)])
