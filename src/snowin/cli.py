"""Command-line entry points for SnowIn."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from snowin.plotting import plot_gunw


def plot_gunw_cli(argv: Sequence[str] | None = None) -> int:
    """CLI wrapper for ``snowin.plotting.plot_gunw``."""
    parser = argparse.ArgumentParser(description="Create NISAR GUNW quick-look plots and diagnostic CSVs.")
    parser.add_argument("gunw_file", type=Path, help="Path to NISAR GUNW .nc file")
    parser.add_argument("--out-dir", type=Path, required=True, help="Output directory")
    parser.add_argument("--crop-geojson", type=Path, default=None, help="Optional GeoJSON polygon for crop/mask")
    parser.add_argument("--grid-epsg", type=int, default=None, help="EPSG code of GUNW x/y grid")
    parser.add_argument("--geojson-epsg", type=int, default=4326, help="EPSG code of input GeoJSON")
    parser.add_argument("--crop-padding", type=float, default=0.0, help="Crop padding in grid units")
    parser.add_argument("--no-mask-outside-geojson", action="store_true", help="Crop bbox but do not mask outside polygon")
    parser.add_argument("--pol", choices=["HH", "VV"], default=None, help="Force polarization")
    parser.add_argument("--radar-cube-index", type=int, default=0, help="Height index for radarGrid 3-D cube variables")
    parser.add_argument("--dpi", type=int, default=220, help="PNG DPI")
    parser.add_argument("--max-plot-dim", type=int, default=2200, help="Maximum plotted dimension after downsampling")
    parser.add_argument("--no-metadata", action="store_true", help="Do not write metadata JSON")
    parser.add_argument("--open", action="store_true", help="Open generated figure")
    args = parser.parse_args(argv)

    result = plot_gunw(
        args.gunw_file,
        out_dir=args.out_dir,
        crop_geojson=args.crop_geojson,
        grid_epsg=args.grid_epsg,
        geojson_epsg=args.geojson_epsg,
        crop_padding=args.crop_padding,
        mask_outside_geojson=not args.no_mask_outside_geojson,
        pol=args.pol,
        radar_cube_index=args.radar_cube_index,
        dpi=args.dpi,
        max_plot_dim=args.max_plot_dim,
        write_metadata=not args.no_metadata,
        open_plot=args.open,
    )
    for path in result.figure_paths:
        print(f"figure: {path}")
    print(f"summary_csv: {result.summary_csv_path}")
    if result.metadata_json_path is not None:
        print(f"metadata_json: {result.metadata_json_path}")
    return 0
