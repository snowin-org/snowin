# SnowIn contributor guidance for coding agents

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
