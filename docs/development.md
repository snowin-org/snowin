# SnowIn development workflow

## Supported Python

SnowIn targets Python 3.12 and newer. The requirement is declared in
`pyproject.toml`, Ruff targets Python 3.12 syntax, and continuous integration
tests Python 3.12, 3.13, and 3.14. Local development may use a newer supported
interpreter.

SnowIn uses a `src/` layout. Install the editable package and full test
dependencies before importing it from a checkout. PEP 735 dependency groups
require pip 25.1 or newer:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[nisar,geometry,dask]" --group dev --group notebooks
```

This keeps user-facing runtime capabilities in package extras and maintainer
tools in dependency groups. Under the [PyPA Dependency Groups
specification](https://packaging.python.org/en/latest/specifications/dependency-groups/),
build backends must not publish group contents as package metadata; optional
dependencies, by contrast, are published as named extras. See also
[PEP 735](https://peps.python.org/pep-0735/), the PyPA's
[project-metadata specification](https://packaging.python.org/en/latest/specifications/declaring-project-metadata/),
and the [pip 25.1 release notes](https://pip.pypa.io/en/stable/news/) for the
`--group` installer option used below.

The editable installation makes changes under `src/snowin/` visible while
keeping the repository root itself out of the import namespace. Do not add
`sys.path` manipulation to tests, examples, or package code.

## Conda environments

The Conda files provide a convenient full-workflow contributor environment.
`environment.yml` includes optional geospatial, cloud, and lazy-array tools so
the repository notebooks can exercise integrations. It is not the dependency
list for the SnowIn package and must not be copied wholesale into a conda-forge
recipe:

| File | Contents | Apply with |
| --- | --- | --- |
| `environment.yml` | Full local workflow environment: core arrays, Dask, NISAR/GUNW, geospatial, cloud, and vector dependencies | `conda env create -f environment.yml` |
| `environment-notebooks.yml` | JupyterLab and ipykernel, layered onto the runtime | `conda env update -n snowin -f environment-notebooks.yml` |
| `environment-dev.yml` | pytest, Hypothesis, pytest-cov, Ruff, build tools, and documentation tools, layered onto the runtime | `conda env update -n snowin -f environment-dev.yml` |

After creating and activating the environment, upgrade pip and install the
editable checkout with the optional integrations and internal dependency
groups:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[nisar,geometry,dask]" \
  --group dev --group docs --group notebooks
```

Setuptools discovers the installable package under `src/snowin`. The notebooks
stay in this repository as synthetic core examples, NISAR integration guides,
and downstream study workflows. Notebook dependencies are internal
development requirements; they are not SnowIn package extras.

The eventual conda-forge recipe will be submitted separately to
`conda-forge/staged-recipes/recipes/snowin/recipe.yaml` after a versioned source
release is available. Its default requirements should match the base package
metadata in `pyproject.toml` (NumPy and xarray). Optional dependency sets may
be represented as conda outputs only where their maintenance and user value
justify that support. The recipe's package test should import SnowIn without
optional integrations and exercise a small synthetic scientific operation.

## API policy

The stable, recommended facade is the small set of generic scientific
functions exported from `snowin`. Product and domain-specific operations are
public through named submodules such as `snowin.io`, `snowin.reference`, and
`snowin.corrections`. Underscore-prefixed names are internal. Retired compatibility and
convenience APIs are documented in the migration notes. Only the root-level
facade receives long-term stability guarantees. See the full
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

The base package depends on NumPy and xarray. The maintained public extras are
nisar for local NISAR GUNW reading, geometry for NISAR local-incidence
calculation from a prepared DEM, and dask for Dask-backed arrays.

The development, docs, and notebooks requirements are PEP 735 dependency
groups. The notebooks group includes plotting, GIS, Earthdata, cloud, and
notebook libraries used by repository workflows; the groups are not published
as package runtime metadata. The
[PyPA dependency-groups specification](https://packaging.python.org/en/latest/specifications/dependency-groups/)
defines this separation.

The full local Conda environment may install more tools for scripts and
notebooks. It is a contributor convenience and does not define SnowIn's
package requirements.

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

## Current adapter boundary

The NISAR GUNW reader and HDF5 dependencies load only when the NISAR feature is
used. Local-incidence geometry is explicit and requires a prepared DEM. SnowIn
does not search for products, download files, or acquire DEMs. Notebook and
study workflows own those operations.

## Geometry execution decision

NISAR-modified Copernicus DEM reprojection and LOS interpolation remain eager by
default. The phase and normalized product layers remain Dask-compatible and
lazy. The opt-in ``geometry_chunks`` path evaluates the SciPy interpolation
one output chunk at a time and returns a Dask-backed incidence result. On the
4,347 x 4,410 Colorado product, 512 x 512 chunks produced an exactly equal
angle field and reduced observed peak memory from about 6.7 GiB to 5.7 GiB,
with about 4.7 seconds of graph construction and 6.4 seconds of geometry
work. That measured reduction justifies retaining the path as an opt-in for
large-grid workflows. It still loads the DEM, LOS lookup cube, and terrain
normals eagerly, so it is not out-of-core or distributed execution. The eager
default avoids imposing Dask on users who do not need the lower peak.

## Release checks

A release candidate must pass the normal quality checks and an isolated wheel
installation:

    python -m build
    python -m venv /tmp/snowin-wheel-smoke
    /tmp/snowin-wheel-smoke/bin/python -m pip install dist/*.whl
    /tmp/snowin-wheel-smoke/bin/python scripts/wheel_smoke.py

The smoke script verifies that the built artifact, rather than the checkout,
is imported and that its public dSWE API returns the expected scientific
result.
