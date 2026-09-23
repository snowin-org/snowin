# SnowIn notebooks

These notebooks are training material and executable baseline checks for the
pre-release package.

## Core workflow

[`01_core_snowin_workflow.ipynb`](01_core_snowin_workflow.ipynb) is
self-contained. It uses synthetic xarray data to demonstrate the canonical
phase contract, dSWE, reference phase, explicit corrections, support layers,
temporal accumulation, metrics, and plots.

## Real NISAR GUNW workflow

[`02_real_nisar_gunw_workflow.ipynb`](02_real_nisar_gunw_workflow.ipynb) is a
small real-product example. Set `SNOWIN_GUNW` to a local GUNW path. Optionally
set `SNOWIN_NISAR_DEM` to a local NISAR-modified Copernicus DEM and
`SNOWIN_DEM_CACHE` to choose the automatic DEM cache directory.

Install the notebook/runtime dependencies from the checkout with:

```bash
python -m pip install -e ".[dev,gunw]"
```

The real-product notebook does not store products or generated rasters in the
repository. It first opens the product for metadata/phase inspection, then
explicitly calls `add_gunw_incidence` for the slower DEM/LOS step before the
local-incidence and simple pairwise dSWE preview.

## Colorado comparison workflow

[`03_colorado_comparison_workflow.ipynb`](03_colorado_comparison_workflow.ipynb)
keeps two real-product modes separate: controlled Colorado reproduction with a
declared incidence raster and frozen wavelength, and SnowIn-native geometry
with the NISAR-modified Copernicus DEM and product-derived wavelength. It
displays the intermediate xarray objects, provenance, support fractions, and
an optional signed residual against a downstream dSWE raster.

Set `SNOWIN_COLORADO_INCIDENCE` and `SNOWIN_COLORADO_OFFSET_RAD` to enable the
controlled mode. The notebook never embeds Colorado station/date policy; it
accepts the already-derived edge offset as an explicit input.
