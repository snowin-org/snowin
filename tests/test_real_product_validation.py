"""Opt-in checks against external NISAR GUNW/COP30 evidence files."""

from __future__ import annotations

import os
from pathlib import Path

import h5py
import numpy as np
import pytest

from snowin.io import add_gunw_incidence, open_gunw


@pytest.mark.integration
def test_real_gunw_phase_lineage_is_explicit():
    """Verify raw product phase uses the explicitly declared conversion."""
    gunw = os.environ.get("SNOWIN_REAL_GUNW")
    if not gunw:
        pytest.skip("set SNOWIN_REAL_GUNW for the external GUNW lineage check")

    path = Path(gunw)
    phase_path = (
        "science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH/unwrappedPhase"
    )
    with h5py.File(path, "r") as source:
        raw = np.asarray(source[phase_path][...])
        units = source[phase_path].attrs["units"]
        height_attrs = dict(
            source["science/LSAR/GUNW/metadata/radarGrid/heightAboveEllipsoid"].attrs
        )

    assert str(units).lower().replace("b'", "").replace("'", "") in {
        "rad",
        "radians",
    }
    assert "WGS84" in str(height_attrs["description"])

    # Check the public reader directly, without geometry or corrections.
    with open_gunw(path, chunks=None, progress=False) as result:
        phase = result.phase.values
        support = np.isfinite(raw) & np.isfinite(phase)
        assert support.any(), "real product has no shared valid phase support"
        np.testing.assert_allclose(phase[support], raw[support], rtol=0, atol=0)
        assert result.attrs["phase_transform"] == "identity"
        assert (
            result.attrs["phase_difference_definition"] == "reference_minus_secondary"
        )
        assert result.attrs["correction_layers_applied"] is False


@pytest.mark.integration
def test_real_gunw_geometry_requires_declared_datum_inputs():
    gunw = os.environ.get("SNOWIN_REAL_GUNW")
    dem = os.environ.get("SNOWIN_REAL_COP30_DEM")
    if not gunw or not dem:
        pytest.skip("set SNOWIN_REAL_GUNW and SNOWIN_REAL_COP30_DEM")

    with pytest.raises(ValueError, match="vertical_correction_m"):
        result = open_gunw(gunw, chunks=None, progress=False)
        try:
            add_gunw_incidence(
                result,
                gunw,
                dem=dem,
                require_vertical_datum_match=True,
                progress=False,
            )
        finally:
            result.close()
