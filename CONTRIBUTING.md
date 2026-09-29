# Contributing to SnowIn

Thanks for contributing.

## Development setup

```bash
python --version  # Python 3.12 or newer
python -m pip install --upgrade pip  # dependency groups need pip 25.1+
python -m pip install -e ".[nisar,geometry,dask]" --group dev --group notebooks
pytest -q
pytest --cov=snowin --cov-report=term-missing --cov-report=xml
ruff check .
ruff format --check .
python -m build
git diff --check
```

SnowIn uses a `src/` layout. Tests and examples should import the installed
package (`snowin`), not files by path or by modifying `sys.path`.

The base package contains the snow–InSAR science API and depends on NumPy and
xarray. NISAR/GUNW reading, local-incidence geometry, and Dask support are
optional. Keep product discovery, provider acquisition, cloud staging, GIS
operations, plots, and study selection policies in upstream tools or
workflows; pass prepared inputs through the normalized xarray contract.

## Branch naming

Use short, descriptive branch names:

- `feature/core-swe-methods`
- `feature/gunw-reader`
- `docs/architecture`
- `fix/incidence-angle-validation`
- `chore/ci-setup`

## Pull request expectations

A PR should:
- address one issue or one tightly related issue set
- include tests for new functionality
- include docstring updates for public functions
- keep notebooks as examples, not as the home of core logic

## Scientific testing checklist

For every new or changed public scientific operation, consider each item and
cover it when applicable:

- [ ] Is there an independent analytical or reference-value test?
- [ ] Are important mathematical and scientific invariants tested?
- [ ] Are invalid or ambiguous inputs tested?
- [ ] Are units, dimensions, coordinates, CRS, and metadata protected?
- [ ] Does NumPy/eager behavior match Dask/lazy behavior when applicable?
- [ ] Are missing-data and masking semantics tested?
- [ ] Is a regression test included for bug fixes?
- [ ] Are numerical tolerances explicit and scientifically justified?
- [ ] Do tests, coverage, Ruff, build, and installation checks pass?

Some items do not apply to every operation; record the relevant reasoning in
the test or PR summary. See the canonical [scientific testing policy](docs/testing.md)
for test design, coverage, and numerical tolerance guidance.

## Style

- use snake_case for functions and variables
- keep public APIs stable and explicit
- prefer small modules with clear roles
- avoid copying large chunks from legacy repos without refactoring
- keep scientific conventions and provenance explicit
- do not commit generated caches, plots, or workflow outputs
