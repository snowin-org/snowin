# SnowIn architecture

## Current package areas

- `snow/`: core snow-science transforms, including phase-to-dSWE and snow-depth-change relationships.
- `io/`: mission/product readers and normalized loading interfaces. First implemented target: NISAR GUNW.
- `plotting/`: user-facing quick-look and publication-adjacent plotting functions. First implemented target: `plot_gunw()`.
- `diagnostics/`: reusable raster and workflow summary statistics. These are intentionally independent of a specific product where possible.
- `cli.py`: thin command-line wrappers around public package functions.

Upcoming:

- `subset/`: spatial cropping, masking, and AOI tools that are reusable outside plotting.
- `corrections/`: atmospheric, ionospheric, ramp, and reference-phase correction utilities.
- `calval/`: CDEC/SNOTEL/ASO/iSnobal alignment, extraction, and validation summaries.
- `workflows/`: end-to-end user-facing workflows built from lower-level modules.

## Why this layout

This layout keeps the public API predictable and makes it easier to migrate legacy scripts without preserving their one-off naming, local paths, or mixed R/Python implementation details.

The key rule is:

> exploratory scripts should become short workflow drivers; scientific logic should live in package modules.

## Public API philosophy

Users should see stable names such as:

- `phase_to_dswe`
- `plot_gunw`
- `read_gunw_layer`
- `read_gslc`
- `load_snotel`
- `crop_to_basin`
- `remove_planar_ramp`
- `apply_quality_mask`
- `run_gunw_to_dswe_workflow`

Internal helpers may be specialized, but the user-facing package should feel unified.

## Implemented first-pass GUNW plotting flow

`plot_gunw()` is the first workflow-style function. It currently:

1. Detects or accepts HH/VV polarization.
2. Reads standard GUNW diagnostic layers from `frequencyA`:
   - unwrapped phase
   - unwrapped and wrapped coherence
   - connected components
   - wrapped interferogram phase and amplitude in dB
   - ionospheric phase screen and uncertainty
   - mask
   - pixel offsets and correlation peak
   - radar-grid incidence angle, baselines, slant range, and tropospheric phase screens
3. Optionally crops and masks all panels/summaries to a GeoJSON AOI.
4. Writes one standard compact PNG quick-look figure.
5. Writes one CSV row per layer/derived layer with reproducible summary statistics.
6. Writes metadata JSON with granule, orbit, track/frame, version, DOI, look direction, and acquisition timing.

## `plot_gunw()` outputs

For a file `NISAR_L2_PR_GUNW_...nc`, the function writes:

- `*_quickview.png`
- `*_summary_stats.csv`
- `*_metadata.json`, unless disabled

The summary CSV includes:

- layer name
- source layer
- transform, such as native, magnitude, magnitude dB, angle, integer labels, or QA mask
- presence flag
- total and valid pixel counts
- valid and NaN fraction
- mean, standard deviation, min, max
- p01, p05, p50, p95, p99
- product-provided summary attributes when present
- connected-component dominant label/fraction when applicable
- mask unique values and fill-255 fraction when applicable

## CLI entry point

Install in development mode with GUNW dependencies:

```bash
python -m pip install -e ".[dev]"
```

Then run:

```bash
snowin-plot-gunw /path/to/NISAR_L2_PR_GUNW_....nc \
  --out-dir plots/gunw_quicklooks \
  --crop-geojson /path/to/basin.geojson \
```

If the grid CRS cannot be auto-detected, pass `--grid-epsg 32611` or the relevant projected EPSG.
