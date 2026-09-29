# SnowIn notebooks

The notebooks illustrate SnowIn's 0.1 scientific API and NISAR GUNW adapter.
Start with notebooks 01, 02, and 06 for the supported package workflows.
Notebooks 03–05 are downstream study examples with additional local data and
workflow requirements; they are not needed for the core examples or test
suite.

## Core workflow

[`01_core_snowin_workflow.ipynb`](01_core_snowin_workflow.ipynb) is
self-contained. It uses synthetic xarray data to demonstrate the canonical
phase contract, dSWE, reference phase, explicit corrections, support layers,
temporal accumulation, metrics, and plots.

## Real NISAR GUNW workflow

[`02_real_nisar_gunw_workflow.ipynb`](02_real_nisar_gunw_workflow.ipynb) is a
small real-product example. Set `SNOWIN_GUNW` to a local GUNW path. Set `SNOWIN_NISAR_DEM` to a prepared local NISAR-modified Copernicus DEM.

Install the notebook groups and only the integrations exercised by these
examples from the checkout with pip 25.1 or newer:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[nisar,geometry,dask]" \
  --group notebooks
```

The real-product notebook does not store products or generated rasters in the
repository. It opens the product for metadata and phase inspection, including
available correction layers, then calls `add_gunw_incidence` with the prepared local
DEM for the slower geometry step. The reader and DEM geometry are optional
NISAR integrations; general data discovery and ancillary preparation belong to
the caller. Its final plot uses xarray and Matplotlib to show GUNW layers,
incidence, and pairwise dSWE. Correction layers are visualized but not applied
automatically.

[`06_nisar_pytools_search_and_snowin.ipynb`](06_nisar_pytools_search_and_snowin.ipynb)
starts from an ASF search through `nisar_pytools`, downloads selected GUNW
products with its HDF5 validation, and passes the local file to SnowIn's
normalized GUNW reader and dSWE workflow. It displays all layers returned by
`open_gunw`, then plots local incidence in degrees and pairwise dSWE. It
defaults to downloading one matching GUNW; change `max_products` only when you
intend to fetch more. A GSLC search can be run separately, but SnowIn's current
retrieval adapter consumes GUNW rather than GSLC.

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

## NIVAL NISAR comparison (development only)

[NIVAL comparison notebook on `development`](https://github.com/snowin-org/snowin/blob/development/notebooks/05_nival_nisar_comparison.ipynb) adapts the
load-bearing NISAR portion of Zach Hoppinen's
[`tc_brief_nival_validation`](https://github.com/ZachHoppinen/tc_brief_nival_validation)
analysis to SnowIn. It documents the ASC-077 7–19 February 2026 operational
GUNW comparison against NIVAL lidar dHS (7–22 February), reproducing the
outlier gate, per-pixel local-incidence Leinss conversion, lidar SWE anchor,
and coherence-stratified statistics using SnowIn's normalized phase and
`compute_dswe` API. This research comparison stays on the `development` branch
for optional review and is excluded from the 0.1 release on `main`. The
package-facing review sequence is notebooks 01, 02, and 06 above. The notebook
expects the GUNW and two lidar rasters locally;
it derives local incidence through SnowIn using
Copernicus GLO-30, as in Zach's analysis. The download helper fetches the two
required NIVAL snow-depth GeoTIFF assets, the named GUNW, and the one
Copernicus GLO-30 tile covering the Mores Creek AOI:

```bash
python -m pip install -e ".[nisar,geometry,dask]" \
  --group notebooks
python scripts/download_nival_nisar_inputs.py --inputs all --interactive-login
```

The lidar is free from [NSIDC](https://doi.org/10.5067/DPFDH2M49DQG); a free
NASA Earthdata Login is required. `--interactive-login` avoids a stale or
incorrect local `.netrc` entry. The GUNW is about 2.5 GB and comes from ASF
([DOI](https://doi.org/10.5067/NIL2GUNW-P1)); it also requires Earthdata Login.
By default files go under `~/.cache/snowin/nival_nisar/`. The notebook uses
that location, crops the GUNW to Zach's Mores Creek AOI, and uses the local
Copernicus tile for its incidence calculation, avoiding a full-frame DEM
fetch. This follows
the paper's delivered operational GUNW path; the large raw RSLC granules and
the older self-processing stack are not needed. The reference manuscript is
[Hoppinen et al. (2026), EGUsphere preprint](https://doi.org/10.5194/egusphere-2026-5140).
Its reported fitted-density values differ from the current cloned repository's
README, so the notebook calculates the slope from the data and calls out that
version discrepancy. Other remaining method differences are described in the
notebook.

For the inline comparisons, set `NIVAL_REFERENCE_REPO` to a checkout of that
repository before starting Jupyter. The notebook writes a SnowIn-compatible
80 m product, calls Zach's unchanged `nival.paper_figures.results_figure()`
function, and displays the result followed by Zach's source-controlled Figure 2.
It also shows the available SnowIn/ISCE3 ICU 20 m diagnostic and Zach's original
Figure 3 below it, plus tables comparing the 80 m metrics and scene-wide 20 m
correlation. The reference figures are read from Git so a regenerated plot in
the checkout cannot replace the original image. Select the NIVAL analysis
kernel when running the notebook.

Figure 3's 20 m diagnostic uses the GUNW's delivered `wrappedInterferogram`;
Zach's `nival.unwrap_20m` unwraps it with SNAPHU and uses ISCE3 to estimate
effective looks from RSLC metadata. It does not form a new interferogram from
RSLCs.

For a separate ISCE3 unwrap, `scripts/unwrap_gunw_20m_isce3.py` crops the
wrapped GUNW to the Mores Creek AOI and applies ISCE3's ICU algorithm. It writes
a phase GeoTIFF and connected-component GeoTIFF without calling Zach's code.
ICU is a different algorithm from SNAPHU, so its result is an independent
diagnostic rather than a bit-for-bit recreation of his Figure 3. Then
`scripts/derive_unwrapped_gunw_dswe.py` normalizes that output to SnowIn's
phase convention, derives local incidence through SnowIn, and computes 20 m
dSWE. The paper comparison applies the positive conversion to the source GUNW
phase orientation, whereas SnowIn canonicalizes phase to
`secondary_minus_reference`. The 20 m NetCDF therefore stores both `dswe_snowin_canonical` and
`dswe` (negated to match the paper's source-phase polarity). The 80 m notebook
uses the same explicit sign bridge for its Zach-compatible plotting product.
Pass `--cop30-dem` with a local Copernicus GLO-30 tile to limit DEM staging to
the analysis area; SnowIn consumes the supplied DEM and does not stage or
acquire DEM tiles.

Example, using an environment with ISCE3 for the unwrap and the SnowIn geospatial
dependencies for the dSWE step:

```bash
conda run -n isce3 python scripts/unwrap_gunw_20m_isce3.py /path/to/operational_gunw.h5 \
  --output /path/to/nival_20m_isce3_icu.tif
conda run -n nisar_snotel python scripts/derive_unwrapped_gunw_dswe.py \
  --gunw /path/to/operational_gunw.h5 \
  --phase /path/to/nival_20m_isce3_icu.tif \
  --output /path/to/nival_20m_snowin_dswe.nc \
  --cop30-dem /path/to/copernicus_glo30_tile.tif
```

For the complete reviewer environment, install the internal notebook group as well:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[nisar,geometry,dask]" \
  --group dev --group notebooks
```
