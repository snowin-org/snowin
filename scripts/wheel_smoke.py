"""Exercise a minimal public SnowIn call from an installed wheel."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import xarray as xr

import snowin
from snowin.io import open_gunw


def main() -> None:
    installed_path = Path(snowin.__file__).resolve()
    environment_path = Path(sys.prefix).resolve()
    if environment_path not in installed_path.parents:
        raise RuntimeError(
            f"snowin imported outside the wheel environment: {installed_path}"
        )
    if not callable(open_gunw):
        raise AssertionError("optional NISAR adapter import is not callable")

    phase = xr.DataArray(
        [[0.5, -0.5]],
        dims=("y", "x"),
        coords={"y": [100.0], "x": [500000.0, 500010.0]},
        name="phase",
        attrs={
            "units": "rad",
            "phase_difference_definition": "secondary_minus_reference",
        },
    )
    incidence = xr.DataArray(
        np.full((1, 2), math.radians(35.0)),
        dims=phase.dims,
        coords=phase.coords,
        name="incidence_angle",
        attrs={"units": "rad", "incidence_angle_reference": "local"},
    )
    result = snowin.compute_leinss_dswe(phase, incidence, wavelength_m=0.24)
    expected = (
        np.asarray(phase) * 0.24 / (2.0 * math.pi * (1.59 + math.radians(35.0) ** 2.5))
    )

    np.testing.assert_allclose(result.values, expected, rtol=2e-13, atol=2e-15)
    if result.attrs.get("units") != "m" or result.dims != ("y", "x"):
        raise AssertionError("installed wheel returned an invalid dSWE result")
    print(f"wheel smoke passed: {installed_path}")


if __name__ == "__main__":
    main()
