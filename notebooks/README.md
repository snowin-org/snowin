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

## NIVAL NISAR comparison reference

[`05_nival_nisar_comparison.ipynb`](05_nival_nisar_comparison.ipynb) adapts the
load-bearing NISAR portion of Zach Hoppinen's
[`tc_brief_nival_validation`](https://github.com/ZachHoppinen/tc_brief_nival_validation)
analysis to SnowIn. It documents the ASC-077 7–19 February 2026 operational
GUNW comparison against NIVAL lidar dHS (7–22 February), reproducing the
outlier gate, per-pixel local-incidence Leinss conversion, lidar SWE anchor,
and coherence-stratified statistics using SnowIn's normalized phase and
`compute_dswe` API. The notebook expects the GUNW, two lidar rasters, and
lidar rasters locally; it derives local incidence through SnowIn using
Copernicus GLO-30, as in Zach's analysis. The minimal download helper fetches
only the two required NIVAL snow-depth GeoTIFF assets plus the named GUNW:

```bash
python -m pip install -e ".[gunw]"
python scripts/download_nival_nisar_inputs.py --inputs lidar --interactive-login
python scripts/download_nival_nisar_inputs.py --inputs gunw --interactive-login
```

The lidar is free from [NSIDC](https://doi.org/10.5067/DPFDH2M49DQG); a free
NASA Earthdata Login is required. `--interactive-login` avoids a stale or
incorrect local `.netrc` entry. The GUNW is about 2.5 GB and comes from ASF
([DOI](https://doi.org/10.5067/NIL2GUNW-P1)); it also requires Earthdata Login.
By default files go under `~/.cache/snowin/nival_nisar/`. The notebook uses
that location, crops the GUNW to Zach's Mores Creek AOI, and lets SnowIn fetch
or reuse the Copernicus DEM for its local-incidence calculation. This follows
the paper's delivered operational GUNW path; the large raw RSLC granules and
the older self-processing stack are not needed. The reference manuscript is
[Hoppinen et al. (2026), EGUsphere preprint](https://doi.org/10.5194/egusphere-2026-5140).
Its reported fitted-density values differ from the current cloned repository's
README, so the notebook calculates the slope from the data and calls out that
version discrepancy. Other remaining method differences are described in the
notebook.

To reuse Zach's plotting code for the headline 80 m result, set
`NIVAL_REFERENCE_REPO` to a checkout of that repository before starting
Jupyter. The last notebook cell writes a copy of the SnowIn result to the
reference checkout's `outputs/retrieval/dswe_dhs_operational.nc`, which is the
file consumed by the unchanged `nival.paper_figures.results_figure()` function.
Run that function in Zach's `nival` environment to render his Figure 2. Figure
3's 20 m diagnostic still requires his `nival.unwrap_20m` step: it unwraps the
delivered GUNW `wrappedInterferogram` with SNAPHU, using ISCE3 only to estimate
effective looks from RSLC metadata. SnowIn's current NISAR reader consumes the
delivered 80 m `unwrappedPhase` layer and does not perform phase unwrapping.

For the complete reviewer environment, install the notebook extra as well:

```bash
python -m pip install -e ".[dev,gunw,vectors,notebooks]"
```
