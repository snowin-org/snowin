"""Opt-in checks against external NISAR GUNW/COP30 evidence files."""

from __future__ import annotations

import os
from pathlib import Path

import h5py
import numpy as np
import pytest

from snowin.io.nisar import open_gunw


def test_real_gunw_phase_lineage_is_explicit():
    """Verify the raw product is preserved and normalized by the declared transform."""
    gunw = os.environ.get("SNOWIN_REAL_GUNW")
    if not gunw:
        pytest.skip("set SNOWIN_REAL_GUNW for the external GUNW lineage check")

    path = Path(gunw)
    phase_path = (
        "science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH/unwrappedPhase"
    )
    with h5py.File(path, "r") as source:
        raw = np.asarray(source[phase_path][...], dtype=float)
        units = source[phase_path].attrs["units"]
        height_attrs = dict(
            source["science/LSAR/GUNW/metadata/radarGrid/heightAboveEllipsoid"].attrs
        )

    assert str(units).lower().replace("b'", "").replace("'", "") in {
        "rad",
        "radians",
    }
    assert "WGS84" in str(height_attrs["description"])

    # The real-product geometry input is deliberately omitted here. This keeps
    # the phase-lineage check independent of DEM availability and expensive
    # incidence computation.
    import xarray as xr

    from snowin.io.nisar import normalize_gunw_pair

    phase = xr.DataArray(raw, dims=("y", "x"), attrs={"units": "radians"})
    incidence = xr.DataArray(
        np.full(raw.shape, np.deg2rad(35.0)),
        dims=("y", "x"),
        attrs={"units": "rad", "incidence_angle_reference": "local"},
    )
    result = normalize_gunw_pair(
        phase,
        incidence,
        wavelength_m=0.238403545,
        reference_time="2025-01-01T00:00:00Z",
        secondary_time="2025-01-13T00:00:00Z",
        source_phase_difference_definition="reference_minus_secondary",
        spatial_ref=xr.DataArray(0, attrs={"epsg_code": 32613}),
    )
    np.testing.assert_allclose(result["phase"].values, -raw, equal_nan=True)
    assert result.attrs["phase_transform"] == "multiply_by_-1"


def test_real_gunw_geometry_requires_declared_datum_inputs():
    gunw = os.environ.get("SNOWIN_REAL_GUNW")
    dem = os.environ.get("SNOWIN_REAL_COP30_DEM")
    if not gunw or not dem:
        pytest.skip("set SNOWIN_REAL_GUNW and SNOWIN_REAL_COP30_DEM")

    with pytest.raises(ValueError, match="vertical_correction_m"):
        result = open_gunw(
            gunw,
            cop30_dem=dem,
            chunks=None,
            require_vertical_datum_match=True,
        )
        result.close()
