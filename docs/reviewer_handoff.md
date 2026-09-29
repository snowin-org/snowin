# Reviewer handoff: SnowIn core

This handoff describes the current SnowIn package boundary. SnowIn's core is
the xarray-based snow–InSAR retrieval science. The optional NISAR adapter reads
local GUNW files, normalizes phase, and can calculate local incidence from a
prepared DEM. Product search, downloads, cloud staging, ancillary data access,
file export, and study policy remain in notebooks or companion workflows.

## Set up

Use Python 3.12 or newer. From the checkout, install the maintained optional
integrations and the internal notebook and test groups:

    python -m pip install --upgrade pip
    python -m pip install -e ".[nisar,geometry,dask]" --group dev --group notebooks
    pytest -q
    jupyter lab

The notebook dependency group uses pip 25.1 or newer. The standard test suite
and Notebook 01 need no external products. Notebook 02 requires a local GUNW
and a prepared local NISAR-modified Copernicus DEM. Notebook 06 calls
nisar-pytools directly for ASF search and validated download, then passes the
local product to SnowIn. Network access and Earthdata credentials may be
required for that workflow.

## Review sequence

1. notebooks/01_core_snowin_workflow.ipynb — synthetic phase, retrieval,
   reference, correction, support, temporal, and metrics workflow.
2. notebooks/02_real_nisar_gunw_workflow.ipynb — inspect a local GUNW, review
   normalized phase and correction layers, supply a prepared DEM, and compute
   local incidence and pairwise dSWE.
3. notebooks/06_nisar_pytools_search_and_snowin.ipynb — use upstream search
   and download helpers, then process one local GUNW with SnowIn.
4. notebooks/03_colorado_comparison_workflow.ipynb and
   notebooks/04_transferable_nisar_snotel_workflow.ipynb — optional study
   workflows with caller-supplied inputs and policies.
5. The NIVAL comparison notebook, when present in the checkout, is an optional
   research workflow with external products and its own data setup.

For notebooks 02–04 and 06, set SNOWIN_GUNW and SNOWIN_NISAR_DEM to local
paths. SnowIn does not download, stage, or cache DEMs. Notebook 03 also accepts
Colorado incidence, reference-offset, and vector paths. Notebook 04 accepts an
analysis vector and caller-prepared station table.

## Canonical GUNW workflow

    from snowin import compute_dswe
    from snowin.io import add_gunw_incidence, open_gunw

    pair = open_gunw(gunw_path, chunks="auto")
    add_gunw_incidence(
        pair,
        gunw_path,
        dem=prepared_dem_path,
        dem_source="nisar_cop30",
    )
    dswe = compute_dswe(
        pair["phase"],
        pair["incidence_angle"],
        wavelength_m=pair.attrs["wavelength_m"],
    )

open_gunw returns a normalized xarray Dataset. Its phase is
secondary_minus_reference; product wavelength and source provenance are
recorded. Available ionosphere and troposphere correction layers are exposed
for inspection and are not applied automatically. add_gunw_incidence adds
local incidence and the geometry_valid support mask. Cells without valid
terrain/LOS support, including back-facing terrain, remain missing. Incidence
is in radians for calculations; notebooks may plot it in degrees with
xarray's plotting interface and Matplotlib.

## What to report

For each run, record the commit and environment, notebook and cell, product
granule and polarization/frequency, phase definition and transform, wavelength
and source, CRS/grid, DEM path and vertical datum, correction-layer status,
geometry support fraction, output units, warnings, runtime, and any failure
with enough information to reproduce it. Do not include credentials or
private input paths in issues or commits.

Use reviewer_feedback_template.md to record observations. Report
product-specific scientific choices separately from package behavior;
station selection, date matching, and downstream validation policies remain
caller-owned.
