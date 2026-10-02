#!/usr/bin/env python3
"""Search ASF for NISAR GUNW products and download one only when requested."""

from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import urlparse

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPOSITORY_ROOT / "data" / "external" / "nisar" / "gunw"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Search ASF for NISAR GUNW products. Searches are read-only; "
            "downloading requires an explicit --download-index."
        )
    )
    parser.add_argument(
        "--aoi",
        nargs=4,
        type=float,
        required=True,
        metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        help="AOI bounds in longitude/latitude degrees",
    )
    parser.add_argument("--start-date", required=True, help="start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="end date (YYYY-MM-DD)")
    parser.add_argument("--max-results", type=int, default=20)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="search and list products without downloading (the default)",
    )
    mode.add_argument(
        "--download-index",
        type=int,
        help="download the product at this index from the search results",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"download directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        from nisar_pytools import download_urls, find_nisar
    except ImportError:
        parser.error("nisar-pytools is required; install SnowIn with the 'nisar' extra")

    urls = list(
        find_nisar(
            aoi=args.aoi,
            start_date=args.start_date,
            end_date=args.end_date,
            product_type="GUNW",
            max_results=args.max_results,
        )
        or []
    )
    print(f"Found {len(urls)} GUNW products")
    for index, url in enumerate(urls):
        product_name = Path(urlparse(str(url)).path).name or str(url)
        print(f"{index}: {product_name}")

    if args.download_index is None:
        print("Search-only dry run: no product was downloaded.")
        if urls:
            print("Review the list, then pass --download-index N to download one.")
        return 0

    if args.download_index not in range(len(urls)):
        parser.error("--download-index must match one of the listed product indices")

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    files = download_urls(
        [urls[args.download_index]], output_dir, max_workers=1, validate=True
    )
    if not files:
        raise RuntimeError("No product was downloaded and validated.")

    downloaded_paths = [Path(file).expanduser().resolve() for file in files]
    for path in downloaded_paths:
        if not path.is_file():
            raise FileNotFoundError(path)
        print("Validated local GUNW:", path)
    print("Download directory:", output_dir)
    print("Set SNOWIN_GUNW to the selected file if the directory has multiple GUNWs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
