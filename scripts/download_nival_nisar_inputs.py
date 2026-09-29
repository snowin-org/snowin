"""Download the exact NIVAL lidar and NISAR GUNW inputs for notebook 05.

NIVAL files are selected from the public NSIDC ``NIVAL_MCS_Lidar`` collection.
The script downloads only the two Snow Depth GeoTIFF assets, not the larger
multi-layer lidar granules. The GUNW is selected by its full granule name from
ASF's ``NISAR_L2_GUNW_PROVISIONAL_V1`` collection. The ``dem`` input stages
one public Copernicus GLO-30 tile covering the Mores Creek AOI.

This repository workflow uses ``earthaccess`` and ``requests`` from the
internal ``notebooks`` dependency group (pip 25.1 or newer), plus a free NASA
Earthdata Login for the lidar and GUNW. The public DEM tile download requires
no login. If a stale ``.netrc`` entry is configured, pass
``--interactive-login`` to enter a current Earthdata username/password without
changing that file.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import urlparse

import earthaccess
import requests

GUNW_COLLECTION = "NISAR_L2_GUNW_PROVISIONAL_V1"
GUNW_NAME = (
    "NISAR_L2_PR_GUNW_012_077_A_024_013_4000_SH_"
    "20260207T124619_20260207T124654_20260219T124619_20260219T124654_"
    "P05023_N_F_J_001.h5"
)
LIDAR_COLLECTION = "NIVAL_MCS_Lidar"
LIDAR_FILES = {
    "20260207": "NIVAL_MCS_Lidar_20260207_SD_v01.tif",
    "20260222": "NIVAL_MCS_Lidar_20260222_SD_v01.tif",
}
COP30_TILE = "Copernicus_DSM_COG_10_N43_00_W116_00_DEM.tif"
COP30_TILE_URL = (
    "https://copernicus-dem-30m.s3.amazonaws.com/"
    "Copernicus_DSM_COG_10_N43_00_W116_00_DEM/"
    "Copernicus_DSM_COG_10_N43_00_W116_00_DEM.tif"
)


def _basename(url: str) -> str:
    return urlparse(url).path.rsplit("/", 1)[-1]


def _unique_asset(urls: list[str], *, label: str, expected_name: str) -> str:
    matches = [url for url in dict.fromkeys(urls) if _basename(url) == expected_name]
    if len(matches) != 1:
        available = sorted({_basename(url) for url in urls})
        raise RuntimeError(
            f"Expected one {label} asset named {expected_name!r}, found "
            f"{len(matches)}. Candidate assets: {available}"
        )
    return matches[0]


def _download(session, url: str, destination: Path) -> Path:
    if destination.is_file() and destination.stat().st_size > 0:
        print(f"skip existing: {destination} ({destination.stat().st_size:,} bytes)")
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    name = destination.name
    print(f"downloading {name}", flush=True)
    written = 0
    try:
        with session.get(url, stream=True) as response:
            response.raise_for_status()
            expected_size = int(response.headers.get("content-length", 0))
            with partial.open("wb") as output:
                for chunk in response.iter_content(1024 * 1024):
                    if chunk:
                        output.write(chunk)
                        written += len(chunk)
        if expected_size and written != expected_size:
            raise OSError(
                f"Incomplete download for {name}: received {written:,} of "
                f"{expected_size:,} bytes"
            )
        partial.replace(destination)
    except Exception:
        partial.unlink(missing_ok=True)
        raise

    print(f"saved {destination} ({written:,} bytes)", flush=True)
    return destination


def _find_lidar_urls() -> dict[str, str]:
    granules = earthaccess.search_data(
        short_name=LIDAR_COLLECTION,
        count=-1,
    )
    urls = [url for granule in granules for url in granule.data_links()]
    return {
        day: _unique_asset(urls, label=f"NIVAL {day} snow depth", expected_name=name)
        for day, name in LIDAR_FILES.items()
    }


def _find_gunw_url() -> str:
    granules = earthaccess.search_data(
        short_name=GUNW_COLLECTION,
        granule_name=f"{Path(GUNW_NAME).stem}*",
        count=10,
    )
    urls = [url for granule in granules for url in granule.data_links()]
    return _unique_asset(urls, label="NISAR GUNW", expected_name=GUNW_NAME)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inputs",
        choices=("all", "lidar", "gunw", "dem"),
        default="all",
        help="download the GUNW, lidar, and local Copernicus tile, or select one type",
    )
    parser.add_argument(
        "--destination",
        type=Path,
        default=Path.home() / ".cache" / "snowin" / "nival_nisar",
        help="directory for the downloaded source files",
    )
    parser.add_argument(
        "--interactive-login",
        action="store_true",
        help="prompt for Earthdata credentials instead of reading environment/.netrc first",
    )
    args = parser.parse_args()

    if args.inputs == "dem":
        session = requests.Session()
        _download(session, COP30_TILE_URL, args.destination / "dem" / COP30_TILE)
        return

    strategy = "interactive" if args.interactive_login else "all"
    earthaccess.login(strategy=strategy)
    session = earthaccess.get_requests_https_session()

    if args.inputs in {"all", "lidar"}:
        lidar_urls = _find_lidar_urls()
        lidar_dir = args.destination / "lidar"
        for day, filename in LIDAR_FILES.items():
            _download(session, lidar_urls[day], lidar_dir / filename)

    if args.inputs in {"all", "gunw"}:
        gunw_url = _find_gunw_url()
        _download(session, gunw_url, args.destination / "gunw" / GUNW_NAME)

    if args.inputs == "all":
        _download(session, COP30_TILE_URL, args.destination / "dem" / COP30_TILE)


if __name__ == "__main__":
    main()
