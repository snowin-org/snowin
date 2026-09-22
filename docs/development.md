# SnowIn development workflow

## Supported Python

SnowIn targets Python 3.12 and newer. The requirement is declared in
`pyproject.toml`, Ruff targets Python 3.12 syntax, and continuous integration
runs the package on Python 3.12. Local development may use a newer supported
interpreter.

SnowIn uses a `src/` layout. Install the package before importing it from a
checkout:

```bash
python -m pip install -e ".[dev]"
```

The editable installation makes changes under `src/snowin/` visible while
keeping the repository root itself out of the import namespace. Do not add
`sys.path` manipulation to tests, examples, or package code.

## Quality checks

The intentionally small required check set is:

```bash
pytest -q
ruff check .
ruff format --check .
python -m build
git diff --check
```

The test suite is data-free and should run in continuous integration. It
covers the current prototype's public imports, the canonical xarray dSWE
kernel, numerical characterization, I/O helpers, diagnostics, and workflow
plumbing. Product adapters and study-specific retrieval orchestration remain
outside the Stage 2 kernel.

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

`.github/workflows/ci.yml` runs the same install, test, lint, format, and build
checks on a clean Python 3.12 runner. It does not require NISAR products,
cloud credentials, or private study data.

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
/tmp/snowin-wheel-smoke/bin/python -c "import snowin; print(snowin.__version__)"
/tmp/snowin-wheel-smoke/bin/snowin-plot-gunw --help
```

The wheel smoke test verifies that the built artifact, rather than the checkout,
contains the package and console entry point.
