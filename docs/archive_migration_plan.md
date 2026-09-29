> Historical migration record. The current package boundary is described in the [architecture guide](architecture.md); convenience features listed here were not all retained in SnowIn.

# Historical first-pass migration plan for attached legacy scripts

This document predates SnowIn's current package boundary and is retained as
archive context. Its proposed package destinations are candidates only, not
commitments. Apply the current scope in [`architecture.md`](architecture.md):
SnowIn owns reusable snow–InSAR retrieval science and a narrow optional NISAR
adapter; provider access and study-specific workflows remain downstream.
In particular, CDEC, SNOTEL, ASO, lidar, and iSnobal acquisition or validation
utilities should stay in companion tools unless a small, source-independent
scientific operation is shown to belong in SnowIn.

## Migration rule

- Keep package code in `src/snowin/`.
- Keep site-specific paths, basin lists, date lists, and paper-specific figure settings outside the package in `examples/`, `scripts/`, or project notebooks.
- Add tests for numerical transforms, parsing, masking assumptions, and diagnostic outputs before expanding workflows.

## Legacy script mapping

| Legacy script | Current role | SnowIn destination | First-pass action |
|---|---|---|---|
| `gunw_quickview_amplitude_db_crop_masked_v2.py` | GUNW diagnostic plotting and pair screening | Study workflow using `snowin.io.open_gunw` | The custom report was reviewed and retired from package scope; use xarray plotting in a workflow. |
| `clip_gunw.py`, `clip_gunw.R` | Extract GUNW layers to cropped GeoTIFFs | a study workflow or companion export tool using the normalized GUNW adapter | Keep file export and crop policy caller-owned; use the supported adapter for normalized GUNW inputs. |
| `make_inc_cli.py`, `make_inc.py`, `local_incidence_angle.py` | Incidence-angle interpolation and DEM-native incidence products | Future `snowin.geometry.incidence` or `snowin.preprocessing.incidence` | Do not port in first commit. Needs stricter CRS, DEM vertical datum, height-axis, and interpolation tests. |
| `swe_retrieval_test.py` | Minimal dSWE test from phase/incidence rasters | `snowin.compute_dswe`, future `snowin.workflows.dswe` | Use the canonical xarray kernel after an adapter supplies normalized phase, incidence, and authoritative wavelength. |
| `prelim_nisar_aso_test.R` | Main exploratory Tuolumne dSWE/ASO/CDEC workflow | Caller-owned study workflow; reusable corrections remain in SnowIn | Keep station, ancillary-data, and validation policy downstream |
| `compare_nisar_swe_timeseries.R` | NISAR/ASO/CDEC elevation-band comparison | Future `snowin.calval.elevation_bands`, `snowin.plotting.timeseries` | Keep as project script until raster/time-series APIs stabilize. |
| `plot_tuo_cdec_swe.R` | CDEC SWE time series and acquisition markers | Future `snowin.ancillary.cdec`, `snowin.plotting.snow_timeseries` | Port after deciding whether CDEC support lives in Python package or separate local project utilities. |
| `plot_style.R` | R publication plotting helpers | Future Python plotting style module only if needed | Do not port wholesale. SnowIn should not become an R style library. Recreate only styles needed for Python outputs. |
| `prelim_swe_deb25jan18_analysis.R`, `prop_tuo_plot.R` | Paper/proposal-specific figures | Project-level scripts using SnowIn APIs | Do not package directly. Use SnowIn outputs as inputs. |
| `tuo_ion_correct_test.R` | Ionospheric correction sign exploration | Future `snowin.corrections.ionosphere` | Keep as exploratory until sign convention is tested against known truth/reference behavior. |
| `download_tuo_isnobal_wy26.py`, `download_tuo_isnobal_wy26_all.sh`, notebook | iSnobal data listing/download/stacking | Future `snowin.ancillary.isnobal` or project utility | Useful, but not core GUNW first commit. Needs auth/S3 and provenance tests. |

## Historical first-pass proposal (not adopted)

The following list records the original proposal only. The current package
boundary and retained capabilities are defined in the [API policy](api_policy.md)
and [architecture guide](architecture.md).

1. Keep GUNW reading and normalization in the supported adapter; low-level HDF5 helpers remain private.
2. Add `snowin.diagnostics.raster` for reusable summary statistics.
3. Keep routine array plots in notebooks and companion workflows.
4. Keep product search, staging, and reports outside the package API.
5. Add tests for parsing, diagnostics, dB conversion, and existing dSWE behavior.
6. Fix current test imports so they import from `snowin.snow` rather than a local `swe` module.
7. Add an example driver under `examples/`.

## Later package target

The proposed generic GUNW exporter and layer-cropping API below was not adopted. File export, crop vectors, and raster writing remain caller-owned workflow operations. SnowIn's supported adapter reads and normalizes local GUNW products; callers can use xarray, rioxarray, or their study tools to prepare downstream files.

The former method-selector gunw_to_dswe example was retired. It mixed product reading, method selection, corrections, masking, and reference policy in one workflow. Current code should compose the explicit interfaces described in the architecture guide.

## Historical status

The former method-selector `gunw_to_dswe()` example has been removed. It
predated SnowIn's canonical xarray kernel and mixed product reading, method
selection, corrections, masking, and reference policy in one unverified
workflow. Current implementation guidance is the staged architecture and the
Stage 3 NISAR adapter contract; a later workflow must compose those explicit
interfaces rather than reintroduce a legacy method selector.
