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
