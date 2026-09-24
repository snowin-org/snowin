# SnowIn contributor guidance for coding agents

## Project overview and code map

SnowIn is a Python 3.12+ scientific package for snow-focused SAR/InSAR
analysis. It uses a `src/` layout, with NumPy and xarray as core dependencies;
GUNW, geospatial, plotting, cloud, and Dask capabilities are optional. Read
`docs/api_policy.md` before changing exports or choosing a public import path.

| Area | Main files | Responsibility |
|---|---|---|
| Public API | `src/snowin/__init__.py` | Stable, generic root-level functions |
| Retrieval science | `src/snowin/snow/` | Named phase-to-dSWE methods and SWE helpers |
| Product I/O | `src/snowin/io/` | GUNW reading, phase normalization, DEM and incidence adapters |
| Corrections and reference | `src/snowin/corrections/`, `src/snowin/reference/` | Phase correction and reference methods |
| Quality and time | `src/snowin/quality/`, `src/snowin/temporal.py` | Support masks, metrics, directed accumulation |
| Workflows | `src/snowin/workflows/` | Composition of product readers and scientific operations |
| Spatial and plots | `src/snowin/spatial.py`, `src/snowin/plotting/` | Vector masks and GUNW diagnostics |

Keep product-specific normalization in adapters and general equations in the
scientific layer. Prefer the root facade for stable generic operations and
domain modules for product-specific operations; do not promote an API without
following the API policy.

## Development environment

Install the editable development environment from the repository root:

```bash
python -m pip install -e ".[dev]"
```

Other extras are declared in `pyproject.toml` for GUNW/geospatial, cloud,
vector, docs, and notebook workflows. Do not assume Pixi or another dependency
manager is configured. The base package should remain usable without optional
mission-product dependencies.

Use focused tests while iterating, then run the full quality commands listed
under Repository quality before completing a code change. Examples:

```bash
pytest -q tests/test_dswe_kernel.py tests/test_dswe_properties.py
pytest -q tests/test_nisar_adapter.py tests/test_geometry.py
```

The normal suite must stay synthetic, fast, and offline. Real-product checks
are marked `integration`; follow `tests/fixtures/README.md` for their input
provenance and environment variables. Do not put credentials or local data
paths in tests or commits.

## Implementation conventions

- Preserve xarray labels and metadata as scientific state, and use the public
  API policy to decide which import path to extend.
- Keep Dask-compatible operations lazy until an explicitly documented
  reduction or materialization boundary; test eager/lazy equivalence where
  applicable.
- Use Ruff for lint and formatting. Mypy is not a required gate; see
  `docs/development.md` before proposing type-checking rules.
- Keep public behavior and its tests together. For scientific changes, follow
  `docs/testing.md` rather than copying generic test counts or patterns.

## Scientific correctness

- Preserve SnowIn's canonical phase `secondary_minus_reference`, dSWE
  `secondary_minus_reference`, and temporal edge `reference_to_secondary`.
- Do not change signs, equations, constants, units, CRS semantics, grid
  alignment, or missing-data behavior without explicit scientific evidence
  and a documented rationale.
- Never guess unknown phase conventions, angle units, or scientific metadata.
- Keep product normalization/adapters separate from general scientific
  kernels.

## Tests with implementation

- Add or update tests in the same change as public scientific behavior.
- Prefer independent analytical expected values; distinguish oracle,
  characterization, and regression evidence.
- Test xarray dimensions, coordinates, metadata, units, masks, and provenance,
  not only numeric values.
- Check Dask equivalence and retained laziness where the API supports it.
- Protect missing support and invalid/ambiguous input behavior explicitly.
- Add a small synthetic regression test for each substantive bug fix.

## Numerical discipline

- Do not loosen tolerances merely to pass CI; justify every scientific
  tolerance.
- Do not replace missing values with zero unless that behavior is scientifically
  defined.
- Do not silently align or resample grids inside scientific kernels.
- Do not introduce a phase-sign switch or guess a phase convention.

## Repository quality

Read `docs/testing.md` and follow its scientific testing policy. Before
declaring a change complete, run:

```bash
pytest -q
pytest --cov=snowin --cov-report=term-missing --cov-report=xml
ruff check .
ruff format --check .
python -m build
git diff --check
```

Keep the required suite data-free and fast. Do not use private files,
credentials, cloud access, or large mission products in pull-request tests.
