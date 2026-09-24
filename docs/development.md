# SnowIn development workflow

## Supported Python

SnowIn targets Python 3.12 and newer. The requirement is declared in
`pyproject.toml`, Ruff targets Python 3.12 syntax, and continuous integration
tests Python 3.12, 3.13, and 3.14. Local development may use a newer supported
interpreter.

SnowIn uses a `src/` layout. Install the package before importing it from a
checkout:

```bash
python -m pip install -e ".[dev]"
```

The editable installation makes changes under `src/snowin/` visible while
keeping the repository root itself out of the import namespace. Do not add
`sys.path` manipulation to tests, examples, or package code.

## Conda environments

The Conda files separate SnowIn's scientific runtime from tools used to author
notebooks and maintain the project:

| File | Contents | Apply with |
| --- | --- | --- |
| `environment.yml` | Complete scientific runtime: core arrays, Dask, GUNW/geospatial, cloud, and vector dependencies | `conda env create -f environment.yml` |
| `environment-notebooks.yml` | JupyterLab and ipykernel, layered onto the runtime | `conda env update -n snowin -f environment-notebooks.yml` |
| `environment-dev.yml` | pytest, Hypothesis, pytest-cov, Ruff, build tools, and documentation tools, layered onto the runtime | `conda env update -n snowin -f environment-dev.yml` |

After creating the base environment, activate it and install the checkout in
editable mode with `python -m pip install -e .`. The full runtime list is also
the dependency target for a future conda-forge package. Jupyter and contributor
tools belong in the environment overlays, not the installed library's runtime
requirements. Setuptools discovers the installable package under `src/snowin`;
repository notebooks and research scripts remain checkout examples. In
particular, the Zach/NIVAL notebook and its ISCE3/SNAPHU processing are not
SnowIn package modules, runtime dependencies, or bundled study data.

The eventual conda-forge recipe will be submitted separately to
`conda-forge/staged-recipes/recipes/snowin/recipe.yaml` after a versioned source
release is available. Its runtime dependencies should match `environment.yml`;
its package test should import SnowIn and exercise a small synthetic public
scientific operation.

## API policy

The stable, recommended facade is the small set of generic scientific
functions exported from `snowin`. Product and domain-specific operations are
public through named submodules such as `snowin.io`, `snowin.reference`, and
`snowin.corrections`. Underscore-prefixed names are internal. Legacy submodule
APIs remain for compatibility but are not recommended for new work. Only the
root-level facade receives long-term stability guarantees. See the full
[API policy](api_policy.md).

## Quality checks

The intentionally small required check set is:

```bash
pytest -q
pytest --cov=snowin --cov-report=term-missing --cov-report=xml
ruff check .
ruff format --check .
python -m build
git diff --check
```

The test suite is data-free and should run in continuous integration. The
canonical [scientific testing policy](testing.md) covers independent equation
checks, invariants and property tests, input failures, xarray contracts,
missing-data behavior, eager/Dask equivalence, regression cases, and a
synthetic integration path. Optional real-product checks remain separate and
require explicitly supplied inputs.

The minimum-dependency job runs on Python 3.12 with NumPy 1.26.4 and xarray
2024.1. This is the oldest NumPy release that supports Python 3.12; NumPy 1.24,
which remains the declared lower bound, supports Python 3.8–3.11. The package's
Python floor and dependency floor therefore do not form a testable
NumPy-1.24/Python-3.12 combination. See [testing policy](testing.md) for the
official NumPy release references and the tested compatibility boundary.

Mypy is not part of the required check set yet. The current scientific code is
not mature enough for a strict type-checking gate, and adding a gate without a
reviewed typing boundary would create noise rather than confidence.

## Optional dependencies

The stable scientific API depends on NumPy and xarray. Dask remains optional at
runtime and is installed by the development extra for lazy-array regression
tests. GUNW, plotting, geospatial, and cloud functionality is available
through optional extras. Runtime code should not import examples, tests,
scripts, or repository-specific study code.

## CI

`.github/workflows/ci.yml` runs tests on Python 3.12–3.14, checks the minimum
scientific dependencies on Python 3.12, and runs lint, format, build, and
wheel-install smoke checks. It does not require NISAR products, cloud
credentials, or private study data. The CI coverage report is diagnostic; see
the threshold and scope in `pyproject.toml` and [testing policy](testing.md).

## Repository hygiene

Python caches, test/tool caches, packaging metadata, `.DS_Store`, and future
`outputs/` or `plots/` directories are ignored. Existing generated files that
were already tracked in the local working tree are not deleted automatically;
their removal or archival requires a separate review because they may be
scientific evidence for the downstream study.

## Known Stage 0 boundaries

The first-pass GUNW reader and plotting modules currently import their
optional dependencies eagerly when those subpackages are imported. This is a
known optional-dependency boundary to review as the I/O API is redesigned. The
current angle helper also retains an explicit `auto` compatibility path, and
the GUNW timestamp parser returns naive datetimes. These are documented debt,
not silently changed during package stabilization.

## Geometry execution decision

For the first public release, NISAR-modified Copernicus DEM reprojection and
LOS interpolation remain eager by default. The phase and normalized product
layers remain Dask-compatible and lazy. An opt-in ``geometry_chunks`` prototype
now builds a Dask-backed incidence result by evaluating the SciPy interpolation
one output chunk at a time. It still eagerly loads the DEM, LOS lookup cube,
and terrain normals, so it is a benchmark path rather than a distributed
geometry implementation. The real Colorado product produced a numerically
identical angle field with 512 x 512 chunks and reduced the observed peak from
about 6.7 GiB to about 5.7 GiB in the current environment, while adding graph
construction overhead. Keep the eager default until a larger benchmark and
collaborator review establish an acceptable memory/performance tradeoff.

## Release checks

The release candidate must pass the normal quality checks plus an isolated wheel
installation and CLI help smoke test:

```bash
python -m build
python -m venv /tmp/snowin-wheel-smoke
/tmp/snowin-wheel-smoke/bin/python -m pip install dist/*.whl
/tmp/snowin-wheel-smoke/bin/python scripts/wheel_smoke.py
```

The smoke script verifies that the built artifact, rather than the checkout,
is imported and that its public dSWE API returns the expected scientific
result. CI checks the console entry point in the development environment, where
the optional plotting dependencies are installed.
