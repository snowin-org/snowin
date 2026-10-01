# SnowIn contributor guidance

SnowIn is a Python 3.12+ package for snow-focused SAR/InSAR analysis. The
scientific core uses NumPy and xarray. Optional integrations provide local
NISAR GUNW reading, prepared-DEM incidence geometry, and Dask support. Follow
the [public API guide](maintainer/public_api.md) before changing public exports.

## Development

Install the package and development tools from the repository root. Dependency
groups require pip 25.1 or newer:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[nisar,geometry,dask]" --group dev --group docs
```

The normal tests must remain synthetic, fast, and offline. Real-product checks
are marked `integration`; follow `tests/fixtures/README.md` for their inputs.
Do not place credentials or local data paths in tests or commits.

## Scientific and implementation rules

- Preserve phase `secondary_minus_reference`, dSWE
  `SWE_secondary - SWE_reference`, and temporal edge `reference_to_secondary`.
- Never guess phase sign, angle units, metadata, or source conventions.
- Preserve xarray labels, coordinates, metadata, missing support, and Dask
  laziness where promised. Do not silently align or resample science grids.
- Convert product-specific representations in adapters and keep general
  science equations in retrieval functions.
- Use established Earth-science, Xarray, Dask, Rasterio, and Python terminology.
  Prefer names that identify a scientific quantity, data structure, or
  operation. Keep phase sign, units, CRS, coordinates, missing values, and
  other scientifically important metadata explicit rather than guessed.
- Add or update tests with public behavior. Cover analytical values, scientific
  invariants, invalid inputs, xarray metadata, support, and eager/lazy behavior
  where applicable. Justify numerical tolerances.

Read [the scientific testing policy](maintainer/testing.md) before changing
scientific behavior. Before completing a code change, run:

```bash
pytest -q
pytest --cov=snowin --cov-report=term-missing --cov-report=xml
ruff check .
ruff format --check .
python -m build
git diff --check
```
