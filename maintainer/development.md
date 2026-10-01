# Development

SnowIn supports Python 3.12 and newer. The package uses a `src/` layout and
`pyproject.toml` is the authority for runtime dependencies, optional features,
development tools, and documentation tools.

## Install

Use pip 25.1 or newer for PEP 735 dependency groups:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[nisar,geometry,dask]" --group dev --group docs --group notebooks
```

For the base scientific package, install `-e .`. Add only the feature extras
needed in your workflow: `nisar` for GUNW reading, `geometry` for prepared-DEM
local incidence, and `dask` for chunked arrays. The notebook group contains
Jupyter and plotting tools; none are runtime dependencies.

## Quality checks

```bash
pytest -q
pytest --cov=snowin --cov-report=term-missing --cov-report=xml
ruff check .
ruff format --check .
python -m build
git diff --check
mkdocs build --strict
```

The standard test suite is synthetic, offline, and fast. Optional real-product
checks are marked `integration`; fixture provenance is documented in
`tests/fixtures/README.md`.
Follow the [scientific testing policy](testing.md) when changing scientific
behavior. Do not loosen numerical tolerances without a scientific rationale.

## Package and wheel checks

Build and inspect the wheel, then install it into a clean environment. The
smoke script verifies that imports resolve to the installed wheel and computes
a small synthetic dSWE value:

```bash
python -m build
python -m venv /tmp/snowin-wheel-smoke
/tmp/snowin-wheel-smoke/bin/python -m pip install dist/*.whl
/tmp/snowin-wheel-smoke/bin/python scripts/wheel_smoke.py
```

Base imports and retrievals must work without NISAR, geometry, or notebook
dependencies. Optional integrations should raise clear installation guidance
when their dependency is missing.

## CI

GitHub Actions tests Python 3.12–3.14, checks the minimum supported NumPy and
xarray versions on Python 3.12, runs Ruff, builds the package, and exercises a
clean wheel install. The documentation workflow builds with strict MkDocs
warnings. Package CI does not install the notebook environment or
use private data, credentials, or network access.
