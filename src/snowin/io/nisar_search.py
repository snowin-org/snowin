"""ASF discovery and download helpers backed by :mod:`nisar_pytools`.

SnowIn keeps the search results as ordinary URLs and downloaded products as
ordinary paths. The optional dependency is imported only when a helper runs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def find_nisar(*args: Any, **kwargs: Any) -> list[str]:
    """Return NISAR product URLs matching the ``nisar_pytools`` search API.

    See :func:`nisar_pytools.find_nisar` for AOI, date, product, orbit, and
    maturity filters. Install ``snowin[gunw]`` to use this helper.
    """
    try:
        from nisar_pytools import find_nisar as _find_nisar
    except ImportError as exc:
        raise ImportError(
            "NISAR search requires nisar_pytools; install SnowIn with the 'gunw' extra"
        ) from exc
    return _find_nisar(*args, **kwargs)


def download_urls(*args: Any, **kwargs: Any) -> list[Path]:
    """Download and validate NISAR product URLs with ``nisar_pytools``.

    This is a pass-through to the upstream downloader; see its documentation
    for supported options. Install ``snowin[gunw]`` to use this helper.
    """
    try:
        from nisar_pytools import download_urls as _download_urls
    except ImportError as exc:
        raise ImportError(
            "NISAR downloads require nisar_pytools; install SnowIn with "
            "the 'gunw' extra"
        ) from exc
    return _download_urls(*args, **kwargs)
