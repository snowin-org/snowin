"""Smoke test the data-free README quick-start example."""

from __future__ import annotations

import re
from pathlib import Path

import pytest


def test_readme_quickstart_code_block_runs_and_matches_equation():
    readme = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")
    matches = re.findall(
        r"```python snowin-quickstart\s*\n(.*?)\n```", readme, flags=re.DOTALL
    )
    assert len(matches) == 1, "README must have exactly one tagged quick-start block"

    namespace: dict[str, object] = {}
    exec(compile(matches[0], "README.md:quick-start", "exec"), namespace)

    import math

    theta = math.radians(35.0)
    expected = 1.2 * 0.2384 / (2 * math.pi * (1.59 + theta**2.5))
    dswe = namespace["dswe"]
    assert dswe.item() == pytest.approx(expected, rel=1e-12, abs=0.0)
