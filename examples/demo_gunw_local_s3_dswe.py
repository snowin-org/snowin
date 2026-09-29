#!/usr/bin/env python3
"""Compose NISAR GUNW reading, caller-owned S3 staging, and dSWE retrieval.

This example stages a remote input locally, opens the normalized GUNW pair,
adds either prepared-DEM local incidence or the product ellipsoid angle, and
uses xarray plotting for the resulting dSWE. It is a workflow example rather
than a SnowIn convenience API.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path
from urllib.parse import urlsplit

import fsspec
import matplotlib.pyplot as plt

from snowin import compute_dswe
from snowin.io import add_gunw_incidence, open_gunw


def _stage_input(uri: str, cache_dir: Path) -> Path:
    """Return a local input path, staging S3 data in this example's cache."""
    parsed = urlsplit(uri)
    if parsed.scheme != "s3":
        path = Path(uri).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        return path

    name = Path(parsed.path).name or "gunw.h5"
    key = hashlib.sha256(uri.encode("utf-8")).hexdigest()[:12]
    destination = cache_dir / f"{key}_{name}"
    if destination.is_file():
        return destination

    cache_dir.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    try:
        with fsspec.open(uri, "rb") as source, partial.open("wb") as target:
            shutil.copyfileobj(source, target)
        partial.replace(destination)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    return destination


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gunw", required=True, help="Local path or s3:// GUNW URI.")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--cache-dir", type=Path, default=Path("~/.cache/snowin/gunw"))
    parser.add_argument(
        "--incidence-source",
        choices=("cop30_local", "product_ellipsoid"),
        default="cop30_local",
    )
    parser.add_argument(
        "--dem", type=Path, help="Prepared local DEM for local incidence."
    )
    parser.add_argument(
        "--dem-source",
        choices=("nisar_cop30", "cop30", "tandem30", "srtm30"),
        default="nisar_cop30",
        help="Prepared DEM product and vertical-datum contract.",
    )
    parser.add_argument("--show", action="store_true", help="Display the dSWE plot.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.out_dir = args.out_dir.expanduser().resolve()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    gunw_path = _stage_input(args.gunw, args.cache_dir.expanduser().resolve())

    if args.incidence_source == "cop30_local" and args.dem is None:
        raise ValueError("--dem is required when --incidence-source is cop30_local")

    pair = open_gunw(gunw_path, chunks=None)
    try:
        incidence_kwargs = {"incidence_source": args.incidence_source}
        if args.incidence_source == "cop30_local":
            incidence_kwargs.update(
                dem=args.dem.expanduser().resolve(), dem_source=args.dem_source
            )
        add_gunw_incidence(pair, gunw_path, **incidence_kwargs)
        dswe = compute_dswe(
            pair["phase"],
            pair["incidence_angle"].where(pair["geometry_valid"]),
            wavelength_m=float(pair.attrs["wavelength_m"]),
        )
        dswe_path = args.out_dir / f"{gunw_path.stem}_dswe.nc"
        dswe.to_netcdf(dswe_path)
        axes = dswe.plot.imshow(
            cmap="RdBu_r",
            robust=True,
            figsize=(9, 6),
            cbar_kwargs={"label": "dSWE (m w.e.)"},
        )
        axes.set_title(f"Pairwise dSWE: {gunw_path.name}")
        figure = axes.figure
        figure.tight_layout()
        figure.savefig(args.out_dir / f"{gunw_path.stem}_dswe.png", dpi=150)
        if args.show:
            plt.show()
        else:
            plt.close(figure)
        print(f"dSWE data: {dswe_path}")
        print(f"dSWE plot: {args.out_dir / f'{gunw_path.stem}_dswe.png'}")
    finally:
        pair.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
