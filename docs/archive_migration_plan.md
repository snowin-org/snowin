# First-pass migration plan for attached legacy scripts

This plan converts the current R/Python archive into SnowIn package functions plus short reproducible drivers. The first commit should not try to port every exploratory plot. It should establish stable package seams, tests, and one working migrated function: `plot_gunw()`.

## Migration rule

- Keep package code in `src/snowin/`.
- Keep site-specific paths, basin lists, date lists, and paper-specific figure settings outside the package in `examples/`, `scripts/`, or project notebooks.
- Add tests for numerical transforms, parsing, masking assumptions, and diagnostic outputs before expanding workflows.

## Legacy script mapping

| Legacy script | Current role | SnowIn destination | First-pass action |
|---|---|---|---|
| `gunw_quickview_amplitude_db_crop_masked_v2.py` | GUNW diagnostic plotting and pair screening | `snowin.io.gunw`, `snowin.plotting.gunw`, `snowin.diagnostics.raster` | Ported as `plot_gunw()` with compact PNG, summary CSV, metadata JSON, and CLI. |
| `clip_gunw.py`, `clip_gunw.R` | Extract GUNW layers to cropped GeoTIFFs | Future `snowin.io.gunw`, `snowin.subset`, `snowin.workflows.gunw_export` | Next package target after plotting. Reuse reader and cropper logic rather than duplicating NetCDF paths. |
| `make_inc_cli.py`, `make_inc.py`, `local_incidence_angle.py` | Incidence-angle interpolation and DEM-native incidence products | Future `snowin.geometry.incidence` or `snowin.preprocessing.incidence` | Do not port in first commit. Needs stricter CRS, DEM vertical datum, height-axis, and interpolation tests. |
| `swe_retrieval_test.py` | Minimal dSWE test from phase/incidence rasters | `snowin.snow.phase_to_dswe`, future `snowin.workflows.dswe` | Replace local `leinss_swe_cm()` with `phase_to_dswe(..., method="leinss")` and unit conversion. |
| `prelim_nisar_aso_test.R` | Main exploratory Tuolumne dSWE/ASO/CDEC workflow | Future `snowin.workflows.gunw_to_dswe`, `snowin.calval`, `snowin.corrections` | Split into functions before porting: phase read, quality mask, correction variants, calibration, validation, plotting. |
| `compare_nisar_swe_timeseries.R` | NISAR/ASO/CDEC elevation-band comparison | Future `snowin.calval.elevation_bands`, `snowin.plotting.timeseries` | Keep as project script until raster/time-series APIs stabilize. |
| `plot_tuo_cdec_swe.R` | CDEC SWE time series and acquisition markers | Future `snowin.ancillary.cdec`, `snowin.plotting.snow_timeseries` | Port after deciding whether CDEC support lives in Python package or separate local project utilities. |
| `plot_style.R` | R publication plotting helpers | Future Python plotting style module only if needed | Do not port wholesale. SnowIn should not become an R style library. Recreate only styles needed for Python outputs. |
| `prelim_swe_deb25jan18_analysis.R`, `prop_tuo_plot.R` | Paper/proposal-specific figures | Project-level scripts using SnowIn APIs | Do not package directly. Use SnowIn outputs as inputs. |
| `tuo_ion_correct_test.R` | Ionospheric correction sign exploration | Future `snowin.corrections.ionosphere` | Keep as exploratory until sign convention is tested against known truth/reference behavior. |
| `download_tuo_isnobal_wy26.py`, `download_tuo_isnobal_wy26_all.sh`, notebook | iSnobal data listing/download/stacking | Future `snowin.ancillary.isnobal` or project utility | Useful, but not core GUNW first commit. Needs auth/S3 and provenance tests. |

## Recommended first commit contents

1. Add `snowin.io.gunw` for GUNW layer reading and metadata parsing.
2. Add `snowin.diagnostics.raster` for reusable summary statistics.
3. Add `snowin.plotting.gunw.plot_gunw()`.
4. Add `snowin-plot-gunw` CLI.
5. Add tests for parsing, diagnostics, dB conversion, and existing dSWE behavior.
6. Fix current test imports so they import from `snowin.snow` rather than a local `swe` module.
7. Add an example driver under `examples/`.

## Second commit target

Build `export_gunw_layers()`:

```python
from snowin.io import detect_pol
from snowin.workflows import export_gunw_layers

export_gunw_layers(
    gunw_files=[...],
    out_dir="data/rasters/nisar/clipped",
    crop_vector="data/vectors/tuolumne.geojson",
    layers=["unwrappedPhase", "coherenceMagnitude", "connectedComponents", "mask"],
)
```

This replaces `clip_gunw.py` and `clip_gunw.R`.

## Third commit target

Build `gunw_to_dswe()` as a controlled workflow:

```python
from snowin.workflows import gunw_to_dswe

gunw_to_dswe(
    gunw_file="...GUNW...nc",
    incidence_angle="...incidenceAngle_dem_interp_native.tif",
    method="leinss",
    sensor="nisar",
    band="L",
    quality_mask={"coherence_min": 0.10, "dominant_connected_component": True},
    corrections={"ionosphere": "subtract", "planar_ramp": True},
    reference={"mode": "basin_median_zero"},
    out_dir="outputs/dswe",
)
```

That workflow should not be merged until sign convention, masking, and correction behavior are explicitly tested.
