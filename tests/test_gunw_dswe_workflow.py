import numpy as np
import xarray as xr

from snowin.workflows import gunw_to_dswe


class DummyGunw:
    def __init__(self, layers):
        self.gunw_file = "dummy.nc"
        self.polarization = "HH"
        self.layers = layers
        self.metadata = {"granuleId": "dummy", "trackNumber": 42}


def test_gunw_to_dswe_synthetic_minimal(monkeypatch, tmp_path):
    layers = {
        "unwrapped_phase": xr.DataArray(np.array([[-1.0, -1.0], [-1.0, -1.0]])),
        "incidence_angle": xr.DataArray(np.deg2rad(np.full((2, 2), 35.0))),
        "coherence_unw": xr.DataArray(np.full((2, 2), 0.8)),
        "connected_components": xr.DataArray(np.ones((2, 2))),
        "mask": xr.DataArray(np.zeros((2, 2))),
        "ionosphere": None,
        "wet_tropo": None,
        "hydro_tropo": None,
    }
    monkeypatch.setattr(
        "snowin.workflows.gunw_dswe.read_gunw_layers", lambda *a, **k: DummyGunw(layers)
    )
    out = gunw_to_dswe("dummy.nc", out_dir=tmp_path, write_outputs=True)
    assert out.dswe.shape == (2, 2)
    assert np.isfinite(out.dswe).all()
    assert "diagnostics_json" in out.output_paths
    assert out.metadata["validated_science_product"] is False
