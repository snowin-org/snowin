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
python -m pip install -e ".[dev,gunw,vectors]"
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

To evaluate the basin-limited Colorado areas, also set
`SNOWIN_ERB_VECTOR=/path/to/erb.gpkg` and
`SNOWIN_TAYLOR_VECTOR=/path/to/taylor.gpkg`. Use `SNOWIN_ERB_LAYER` and
`SNOWIN_TAYLOR_LAYER` when a GeoPackage has multiple layers.

## Transferable NISAR and SNOTEL workflow

[`04_transferable_nisar_snotel_workflow.ipynb`](04_transferable_nisar_snotel_workflow.ipynb)
is a template for testing a different NISAR box, analysis-region vector, and
SNOTEL station set. It demonstrates the same canonical two-step workflow,
caller-owned station reference inputs, explicit support layers, and
transferability checks. The station table must provide station IDs,
latitude/longitude, expected phase in SnowIn's canonical convention, and
coherence weights. The notebook samples observed phase from the GUNW unless an
`observed_phase_rad` column is supplied.

For the complete reviewer environment, install the notebook extra as well:

```bash
python -m pip install -e ".[dev,gunw,vectors,notebooks]"
```
