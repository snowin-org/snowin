# Reviewer handoff: Ross and Zach

This is the pre-release review setup for SnowIn. The review target is the
`development` branch, currently containing the canonical xarray workflow, real
NISAR validation, vector analysis masks, and the Colorado 23-edge comparison
baseline.

## Environment setup

Use Python 3.12 or newer:

```bash
git clone https://github.com/snowin-org/snowin.git
cd snowin
git switch development
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,gunw,vectors,notebooks]"
python -m pytest -q
jupyter lab
```

On an existing checkout, use `git fetch` and `git switch development` before
installing the editable package. The expected baseline is `153 passed, 3
skipped`; warnings from Rasterio and one legacy synthetic workflow are known
and do not currently fail the suite.

## Review order

Run these notebooks from the repository root:

1. `notebooks/01_core_snowin_workflow.ipynb` — synthetic core API and support
   behavior.
2. `notebooks/02_real_nisar_gunw_workflow.ipynb` — fast product inspection,
   explicit incidence calculation, and real dSWE preview.
3. `notebooks/03_colorado_comparison_workflow.ipynb` — controlled baseline
   versus Colorado's adopted SnowIn-native phase, DEM geometry, and
   product-metadata wavelength, with basin masks and residuals.
4. `notebooks/04_transferable_nisar_snotel_workflow.ipynb` — a template for a
   different NISAR box and SNOTEL station set.

For the real-product notebooks, configure local paths rather than committing
products or generated output:

```bash
export SNOWIN_GUNW=/path/to/NISAR_GUNW
export SNOWIN_NISAR_DEM=/path/to/nisar_modified_cop30.tif
```

Notebook 03 additionally accepts `SNOWIN_COLORADO_INCIDENCE`,
`SNOWIN_COLORADO_OFFSET_RAD`, `SNOWIN_ERB_VECTOR`, `SNOWIN_TAYLOR_VECTOR`,
and the corresponding layer variables. Notebook 04 accepts
`SNOWIN_ANALYSIS_VECTOR`, `SNOWIN_ANALYSIS_LAYER`, and
`SNOWIN_SNOTEL_TABLE`; it can use `SNOWIN_REFERENCE_OFFSET_RAD` while station
inputs are being prepared.

## Canonical workflow to inspect

Reviewers should use this path for new work:

```python
from snowin import compute_dswe, reference_phase
from snowin.io import add_gunw_incidence, open_gunw

pair = open_gunw(gunw_path, chunks="auto")
add_gunw_incidence(pair, gunw_path, dem_source="nisar_cop30")
pair = reference_phase(pair, ...)
dswe = compute_dswe(
    pair["phase_referenced"],
    pair["incidence_angle"],
    wavelength_m=pair.attrs["wavelength_m"],
)
```

The GUNW path is supplied again to the incidence function intentionally. The
first step is for inspection; the second step performs the slower DEM/LOS
geometry calculation and appends `incidence_angle` to the same Dataset.

## Required review observations

For each real test, record:

- GUNW granule, polarization, frequency, and analysis-box/vector path;
- xarray Dataset dimensions, coordinates, and data variables;
- phase definition and sign transform;
- wavelength and `wavelength_source`;
- DEM source, height reference, and incidence source;
- station IDs, station/date matching, expected-phase construction, weights,
  and exclusions;
- analysis-region, geometry, and retrieval support fractions;
- runtime, memory behavior, warnings, and usability issues.

The vector mask must remain separate from phase normalization and station
selection. The station table supplies study-specific policy; SnowIn only
applies the explicit reference inputs and records their provenance.

## Colorado acceptance check

Notebook 03 should reproduce the documented basin-matched behavior:

- ERB incidence correlation approximately `0.999183`, MAE approximately
  `0.389°`;
- Taylor incidence correlation approximately `0.999110`, MAE approximately
  `0.348°`;
- controlled SnowIn versus Colorado cumulative RMSE near `0.000005 mm` for
  ERB and `0.000004 mm` for Taylor.

The adopted SnowIn-native mode uses the wavelength resolved from product
metadata and the NISAR-modified Copernicus DEM. It is expected to differ from
the controlled historical baseline, which used Colorado's frozen wavelength
and retained incidence raster. Report phase, wavelength, and geometry effects
separately across the 23-edge path; assess the migrated result against its
declared conventions rather than expecting zero residual to the old baseline.
Keep the legacy retrieval available until this validation is reviewed.

## Review outcome

Please return:

1. the exact notebook and cell where an issue occurred;
2. the input type and product metadata involved;
3. the printed provenance and support fractions;
4. whether the issue is reproducible with a synthetic or local product;
5. a proposed fix or clarification.

Use [reviewer_feedback_template.md](reviewer_feedback_template.md) for a
consistent record, or copy its fields into the project issue tracker.

Keep the legacy `gunw_to_dswe()` path unchanged during this review. Its
migration boundary should be revisited only after the new real-product and
transferability checks are complete.
