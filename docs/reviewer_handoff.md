# Reviewer handoff: Ross and Zach

This handoff describes the `development` branch review for SnowIn 0.1. The
branch includes the xarray scientific API, NISAR GUNW normalization and
geometry, ASF search and validated downloads through `nisar_pytools`, the
correction layers exposed by the GUNW reader, and synthetic/regression tests.
The NIVAL comparison notebook remains on `development` for optional research
review; it is not part of the planned 0.1 merge to `main`.

## Set up

Use Python 3.12 or newer. From the branch checkout, install SnowIn and the
notebook and test dependencies:

```bash
git clone https://github.com/snowin-org/snowin.git
cd snowin
git switch development
python -m pip install -e ".[dev,gunw,vectors,notebooks]"
pytest -q
jupyter lab
```

No external product is needed for the standard test suite or Notebook 01.
Notebook 02 uses a local GUNW and optional local NISAR-modified Copernicus DEM.
Notebook 06 searches ASF and downloads one product by default; it requires
network access and any Earthdata credentials requested by ASF. The NISAR
search dates in the example begin after the mission's first acquisitions.

## Review sequence

1. `notebooks/01_core_snowin_workflow.ipynb` — synthetic phase, dSWE,
   reference, correction, support, temporal, and metrics workflow.
2. `notebooks/02_real_nisar_gunw_workflow.ipynb` — inspect an existing GUNW,
   expose its phase and correction layers, add local incidence, and view
   incidence and pairwise dSWE.
3. `notebooks/06_nisar_pytools_search_and_snowin.ipynb` — search ASF, download
   and validate a GUNW through `nisar_pytools`, then process it with SnowIn.
4. `notebooks/03_colorado_comparison_workflow.ipynb` and
   `notebooks/04_transferable_nisar_snotel_workflow.ipynb` — optional,
   caller-supplied study inputs and downstream policies.
5. [NIVAL comparison notebook on `development`](https://github.com/snowin-org/snowin/blob/development/notebooks/05_nival_nisar_comparison.ipynb)
   — optional development-only research comparison; it depends on external
   products and Zach's reference checkout.

For real-product runs, set `SNOWIN_GUNW` and, if available,
`SNOWIN_NISAR_DEM`. Set `SNOWIN_DEM_CACHE` to choose the local DEM cache.
Notebook 03 also accepts Colorado incidence, reference-offset, and vector
paths. Notebook 04 accepts an analysis vector and caller-prepared station
table. The NIVAL notebook on `development` documents its own environment and
data setup in that branch's `notebooks/README.md`.

## Canonical GUNW workflow

```python
from snowin import compute_dswe
from snowin.io import add_gunw_incidence, open_gunw

pair = open_gunw(gunw_path, chunks="auto")
add_gunw_incidence(pair, gunw_path)
dswe = compute_dswe(
    pair["phase"],
    pair["incidence_angle"],
    wavelength_m=pair.attrs["wavelength_m"],
)
```

`open_gunw` returns a normalized xarray Dataset. Its phase is
`secondary_minus_reference`; product wavelength and source provenance are
recorded. Available ionosphere and troposphere correction layers are exposed
for inspection and are not applied automatically. `add_gunw_incidence` adds
local incidence and the `geometry_valid` support mask. Cells without valid
terrain/LOS support, including back-facing terrain, have missing incidence.
Incidence is in radians for calculations; Notebook 02 and Notebook 06 plot it
in degrees for readability.

## What to report

For each run, record the commit and environment, notebook and cell, product
granule and polarization/frequency, phase definition and transform, wavelength
and source, CRS/grid, DEM and vertical datum, correction-layer status, geometry
support fraction, output units, warnings, runtime, and any failure with enough
information to reproduce it. Do not include credentials or private input paths
in issues or commits.

Use [reviewer_feedback_template.md](reviewer_feedback_template.md) to record
observations. Report product-specific scientific choices separately from
package behavior; station selection, date matching, and downstream validation
policies remain caller-owned.
