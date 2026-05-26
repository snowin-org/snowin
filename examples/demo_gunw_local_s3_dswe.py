#!/usr/bin/env python3
"""Demo: local/S3 GUNW quicklook and explicit raw phase-to-dSWE scaffold.

This script demonstrates package plumbing, not a validated SWE retrieval.
Corrections, reference choice, masking thresholds, and provenance are explicit.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from snowin import plot_gunw
from snowin.io import is_s3_uri, stage_remote_file
from snowin.workflows import gunw_to_dswe


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Demo SnowIn local/S3 GUNW reading, quicklook, and dSWE scaffold."
    )
    parser.add_argument("--gunw", required=True, help="Local path or s3:// URI to a GUNW .nc product.")
    parser.add_argument("--out-dir", required=True, help="Output directory.")
    parser.add_argument("--cache-dir", default=None, help="Local cache directory for s3:// input.")
    parser.add_argument("--crop-geojson", default=None, help="Optional AOI GeoJSON for quicklook crop/mask.")
    parser.add_argument("--coherence-min", type=float, default=0.30, help="Minimum coherence for demo mask.")
    parser.add_argument("--show", action="store_true", help="Display quicklook inline in notebooks.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if is_s3_uri(args.gunw):
        if args.cache_dir is None:
            raise ValueError("--cache-dir is required for s3:// inputs.")
        gunw_path = stage_remote_file(args.gunw, args.cache_dir)
    else:
        gunw_path = stage_remote_file(args.gunw, out_dir / "cache")

    quicklook = plot_gunw(
        gunw_path,
        out_dir=out_dir / "quicklook",
        crop_geojson=args.crop_geojson,
        show=args.show,
        verbose=True,
    )

    # The workflow does not crop yet; it preserves the full GUNW array and makes
    # all science-sensitive choices explicit in JSON/CSV diagnostics.
    dswe = gunw_to_dswe(
        gunw_path,
        out_dir=out_dir / "dswe_demo",
        quality_config={"coherence_min": args.coherence_min},
        correction_config={},
        reference_config={"strategy": "none"},
        dswe_config={
            "method": "oveisgharan",
            "sensor": "nisar",
            "band": "L",
            "incidence_angle_unit": "auto",
            "output_unit": "cm",
            # Demo-only fallback: current NISAR GUNW products may expose incidence
            # angle on a coarser radar-grid metadata cube than the geocoded phase.
            # This expands the median incidence angle to the phase grid and records
            # that approximation in diagnostics. Do not use this as a science
            # retrieval substitute for proper incidence-angle interpolation.
            "incidence_shape_policy": "median",
        },
        write_outputs=True,
    )

    print("quicklook_outputs:")
    quicklook.print_paths()
    print("dswe_outputs:")
    for key, value in dswe.output_paths.items():
        print(f"{key}: {value}")
    print("WARNING: dSWE output is a scaffold demonstration, not a validated retrieval.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
