"""Small cloud I/O helpers for SnowIn examples and workflows."""

from __future__ import annotations

import shutil
from pathlib import Path
from urllib.parse import urlparse


def is_s3_uri(path: str | Path) -> bool:
    """Return ``True`` when ``path`` is an ``s3://`` URI."""
    return str(path).startswith("s3://")


def stage_remote_file(
    uri: str | Path,
    cache_dir: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Stage a local file or S3 object to a local path.

    Local paths are returned unchanged after existence checks. S3 paths are
    copied into ``cache_dir`` using optional ``fsspec``/``s3fs`` dependencies.
    SnowIn intentionally stages GUNW products locally for now because robust
    direct HDF5/netCDF access over object storage needs separate tests.
    """
    uri_str = str(uri)
    if not is_s3_uri(uri_str):
        path = Path(uri_str).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return path

    cache_path = Path(cache_dir).expanduser().resolve()
    cache_path.mkdir(parents=True, exist_ok=True)
    parsed = urlparse(uri_str)
    filename = Path(parsed.path).name
    if not filename:
        raise ValueError(f"S3 URI does not include an object filename: {uri_str}")
    out_path = cache_path / filename

    if out_path.exists() and out_path.stat().st_size > 0 and not overwrite:
        return out_path

    try:
        import fsspec
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise ImportError(
            "S3 staging requires optional dependencies. Install with: "
            "python -m pip install 'snowin[cloud]'"
        ) from exc

    with fsspec.open(uri_str, "rb") as src, out_path.open("wb") as dst:
        shutil.copyfileobj(src, dst, length=16 * 1024 * 1024)
    return out_path
