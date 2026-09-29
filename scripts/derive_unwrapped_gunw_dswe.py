"""Convert an independently unwrapped GUNW GeoTIFF to SnowIn dSWE.

This is the SnowIn handoff after ``unwrap_gunw_20m_isce3.py``. ISCE3's ICU
output keeps the source GUNW orientation; this script normalizes it to SnowIn's
secondary-minus-reference convention, computes local incidence with the
product LOS and Copernicus GLO-30, and applies SnowIn's Leinss dSWE kernel.
It writes both canonical SnowIn dSWE and a sign-adjusted field matching the
reference analysis' source-phase polarity.

    conda run -n nisar_snotel python scripts/derive_unwrapped_gunw_dswe.py \
      --gunw /path/to/operational_gunw.h5 \
      --phase /path/to/nival_20m_isce3_icu.tif \
      --output /path/to/nival_20m_snowin_dswe.nc

The output is relative dSWE after removing the median unwrapped phase. It does
not apply the lidar SWE anchor; that is a separate comparison reference.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import rioxarray
import xarray as xr

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from snowin import compute_dswe  # noqa: E402
from snowin.io import add_gunw_incidence, read_gunw_wavelength_m  # noqa: E402


def derive_dswe(
    gunw: Path,
    phase_path: Path,
    output: Path,
    *,
    dem: Path,
) -> Path:
    raster = rioxarray.open_rasterio(phase_path, masked=True).squeeze()
    if raster.ndim != 2 or raster.dims != ("y", "x"):
        raise ValueError(
            f"Expected a 2-D phase raster with y/x dimensions, got {raster.dims}"
        )
    epsg = raster.rio.crs.to_epsg()
    if epsg is None:
        raise ValueError("Phase GeoTIFF must have an EPSG CRS")

    raw_phase = xr.DataArray(
        raster.values.astype(np.float32),
        dims=("y", "x"),
        coords={"y": raster.y.values, "x": raster.x.values},
        name="source_unwrapped_phase",
        attrs={
            "units": "rad",
            "phase_difference_definition": "reference_minus_secondary",
            "source": "ISCE3 ICU unwrap of the delivered GUNW wrappedInterferogram",
        },
    )
    canonical_phase = (-raw_phase).rename("phase")
    canonical_phase.attrs = {
        "units": "rad",
        "phase_difference_definition": "secondary_minus_reference",
        "source_phase_difference_definition": "reference_minus_secondary",
        "phase_transform": "multiply_by_-1",
    }
    target = xr.Dataset({"phase": canonical_phase})
    wkt = raster.rio.crs.to_wkt()
    target["spatial_ref"] = xr.DataArray(
        np.uint32(epsg),
        attrs={"epsg_code": int(epsg), "spatial_ref": wkt},
    )
    target.attrs.update(
        {
            "source_product": gunw.name,
            "source_reader": "ISCE3 ICU GeoTIFF handoff",
            "phase_difference_definition": "secondary_minus_reference",
        }
    )

    target = add_gunw_incidence(
        target,
        gunw,
        dem_source="cop30",
        dem=dem,
        progress=True,
    )
    phase_median = float(canonical_phase.median(skipna=True).values)
    phase_referenced = (canonical_phase - phase_median).rename("phase_referenced")
    phase_referenced.attrs = dict(canonical_phase.attrs)
    phase_referenced.attrs.update(
        {
            "phase_reference_method": "scene_median",
            "phase_reference_offset_rad": phase_median,
        }
    )
    dswe_snowin_canonical = compute_dswe(
        phase_referenced,
        target["incidence_angle"],
        wavelength_m=read_gunw_wavelength_m(gunw),
    )
    # Zach's retrieval divides the source-orientation phase (reference minus
    # secondary) by a positive Leinss factor. SnowIn normalizes to
    # secondary-minus-reference, so invert the kernel result for a like-for-like
    # comparison while retaining the canonical SnowIn result alongside it.
    dswe = (-dswe_snowin_canonical).rename("dswe")
    dswe.attrs = dict(dswe_snowin_canonical.attrs)
    dswe.attrs.update(
        {
            "phase_difference_definition": "reference_minus_secondary",
            "comparison_sign_adjustment": (
                "negative of SnowIn secondary_minus_reference dSWE to match "
                "the reference analysis source-phase orientation"
            ),
        }
    )
    dswe.attrs["phase_reference_offset_rad"] = phase_median

    result = xr.Dataset(
        {
            "dswe": dswe,
            "dswe_snowin_canonical": dswe_snowin_canonical,
            "phase_referenced": phase_referenced,
            "incidence_angle": target["incidence_angle"],
        },
        attrs={
            "crs_epsg": int(epsg),
            "posting_m": float(abs(raster.x.values[1] - raster.x.values[0])),
            "unwrap_algorithm": "ISCE3 ICU",
            "wavelength_m": float(read_gunw_wavelength_m(gunw)),
            "incidence_angle_reference": "local",
            "swe_absolute_anchor": "not applied",
        },
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_netcdf(output)
    print(f"SnowIn 20 m dSWE product: {output}")
    print(f"grid: {result.sizes['y']} rows x {result.sizes['x']} cols")
    print(f"finite dSWE pixels: {int(np.isfinite(dswe.values).sum()):,}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gunw", type=Path, required=True)
    parser.add_argument(
        "--phase", type=Path, required=True, help="ISCE3 ICU phase GeoTIFF"
    )
    parser.add_argument("--output", type=Path, required=True, help="SnowIn dSWE NetCDF")
    parser.add_argument(
        "--cop30-dem",
        type=Path,
        required=True,
        help="prepared local Copernicus GLO-30 raster covering the phase crop",
    )
    args = parser.parse_args()
    if not args.gunw.is_file():
        raise FileNotFoundError(args.gunw)
    if not args.phase.is_file():
        raise FileNotFoundError(args.phase)
    if not args.cop30_dem.is_file():
        raise FileNotFoundError(args.cop30_dem)
    derive_dswe(args.gunw, args.phase, args.output, dem=args.cop30_dem)


if __name__ == "__main__":
    main()
