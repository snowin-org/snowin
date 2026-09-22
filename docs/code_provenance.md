# Code and science provenance

Every reusable scientific capability added to SnowIn should have a record here
or in a linked, versioned provenance record before it replaces downstream
study code. The record should answer:

| Field | Required information |
| --- | --- |
| Capability | SnowIn module and public function |
| Scientific source | Paper, ATBD, equation, or authoritative documentation |
| Repositories inspected | Relevant prior implementations and versions/commits |
| Implementation relationship | Copied, adapted, independently reimplemented, or wrapper |
| License implications | Source license and any notice/attribution requirements |
| Validation evidence | Invariants, characterization cases, regression products, and tolerances |
| Status | Prototype, reviewed, validated, or deferred |

Stage 0 establishes the framework only. The existing prototype capabilities
still require capability-specific records before they are treated as validated
SnowIn science. In particular, the dSWE formulations, GUNW product adapter,
reference-phase behavior, correction signs, and raster-grid assumptions need
primary scientific references and regression evidence in their respective
stages.

The migration rule is: define the scientific behavior, inspect the primary
reference and relevant upstream implementations, write invariant or
characterization tests, implement the smallest general version, record
provenance, and only then replace duplicate downstream code. Study-specific
basin choices, dates, station lists, paper metrics, and figure configuration
remain downstream.

## Stage 1 normalized-contract proposal

| Field | Record |
| --- | --- |
| Capability | Pairwise retrieval-ready xarray Dataset contract and scientific terminology. |
| Scientific source | `docs/snowin_architecture_v1.md`, `docs/data_model.md`, and `docs/scientific_conventions.md`, including the adopted `secondary_minus_reference` project contract; no production dSWE equation was changed. |
| Repositories inspected | Current SnowIn prototype modules and tests at the Stage 1 baseline; no external implementation was copied. |
| Implementation relationship | Independently specified schema and synthetic contract tests. |
| License implications | No third-party code copied or adapted. |
| Validation evidence | `tests/test_contracts.py` synthetic xarray objects and existing prototype characterization tests. |
| Status | Stage 1 contract finalized; GUNW source-sign transformation and Colorado sign-lineage regression audit are deferred to later stages. |

## Stage 2 canonical phase-to-dSWE kernel

| Field | Record |
| --- | --- |
| Capability | `snowin.snow.compute_dswe`: xarray-native pairwise phase-to-dSWE conversion in metres water equivalent. |
| Scientific source | Leinss et al., *Snow Water Equivalent of Dry Snow Measured by Differential Interferometry*, IEEE JSTARS (2015), DOI [`10.1109/JSTARS.2015.2432031`](https://doi.org/10.1109/JSTARS.2015.2432031), Eq. 18 and the open DLR manuscript [PDF](https://elib.dlr.de/100787/1/Leinss-2015-04.pdf). Guneriussen et al. (2001), DOI [`10.1109/36.957273`](https://doi.org/10.1109/36.957273), and Oveisgharan et al. (2024), DOI [`10.5194/tc-18-559-2024`](https://doi.org/10.5194/tc-18-559-2024), were audited as distinct supporting formulations. |
| Exact equation | `k_i = 2*pi / wavelength_m`; `dSWE = phase / (k_i*alpha*(1.59 + incidence_angle_rad**2.5))`, equivalently `phase*wavelength_m / (2*pi*alpha*(1.59 + incidence_angle_rad**2.5))`. |
| Terms and units | `phase` is canonical `phi_secondary - phi_reference` in radians; `dSWE` is `SWE_secondary - SWE_reference` in metres water equivalent; `wavelength_m` is metres; `k_i` is m^-1; incidence is radians; `alpha` is dimensionless. |
| Assumptions and domain | Dry snow, negligible liquid water, and the dry-snow scattering conditions described by Leinss et al.; this is a change retrieval, not absolute SWE. The physical angle is incidence relative to the snow surface. The empirical approximation has documented incidence/density error limits and does not establish a universal accuracy bound. |
| Implementation relationship | Independently reimplemented in `src/snowin/snow/dswe.py` with native xarray arithmetic. No external source code was copied or adapted. The legacy `swe.py` method dispatch was corrected so its Leinss and Oveisgharan compatibility methods represent their distinct published equations. |
| Repositories inspected | `SnowEx/uavsar_pytools` (`51fed9a`, setup metadata identifies MIT); `SnowEx/uavsar_snow` (`c76c4de`); `rpalomaki/SWE_error_analysis` tag `v1.0` (`1b01509`); `ehavazli/snowsar` tag `v0.1.1` (`5181f9b`, Apache-2.0); `ZachHoppinen/uavsar-validation` (`d9f94ae`, MIT); and the verified Colorado checkout `jacktarricone/nisar-grl-colorado-firstlook`, remote-confirmed at `/Users/jtarrico/ch13_nisar_prelim`, committed `HEAD f5c17ef`. The Colorado evidence was read from committed `src/nisar_firstlook/analysis/phase.py`, `config/frozen/paper_reproduction_v2.json`, and committed tests; its unrelated dirty working-tree changes were not used. |
| External implementation findings | `uavsar_snow`/`uavsar_pytools` contain both the Guneriussen density-dependent relation and separate Leinss and Oveisgharan approximations. `uavsar-validation` uses the Leinss path-constant equation with explicit degree-to-radian conversion. `SWE_error_analysis` reproduces the Leinss forward/inverse relation. The current `snowsar` Python tree did not expose an independent phase-to-dSWE kernel. Colorado's committed frozen equation uses the same Leinss denominator and frozen `0.238403545` m wavelength, but retains an explicit historical `phase_sign` branch. |
| License implications | SnowIn contains no copied third-party code. External repository license metadata was recorded where present (MIT for `uavsar_pytools` setup metadata and `uavsar-validation`; Apache-2.0 for `snowsar`); no license file/metadata was found in the inspected `uavsar_snow` or `SWE_error_analysis` checkouts. Equation use and independent implementation do not substitute for any future code-level attribution review. |
| Validation evidence | `tests/test_dswe_kernel.py` covers zero/sign invariants, a known scalar, wavelength and angle dependence, NaN propagation, explicit units and wavelength errors, alignment, metadata, Dask laziness/equivalence, and Colorado frozen-parameter characterization. The frozen Colorado constants are used as numerical characterization only; no ASO or validation dataset was used for tuning. |
| Status | Stage 2 canonical kernel is implemented and tested; the product-specific NISAR phase normalization and authoritative wavelength extraction are implemented in the Stage 3 adapter. Temporal accumulation, corrections, reference phase, and Colorado workflow integration remain deferred. |

## Stage 3 NISAR GUNW adapter

| Field | Record |
| --- | --- |
| Capability | `snowin.io.open_gunw`, `snowin.io.compute_gunw_incidence`, `snowin.io.add_gunw_incidence`, `snowin.io.normalize_gunw_pair`, `snowin.io.compute_cop30_local_incidence`, `snowin.io.download_nisar_cop30_dem_for_gunw`, `snowin.io.download_cop30_dem_for_gunw`, and `snowin.io.read_gunw_wavelength_m`. |
| Scientific source | NASA/ASF [NISAR GUNW user guide](https://nisar-docs.asf.alaska.edu/gunw/) and [metadata guide](https://nisar-docs.asf.alaska.edu/metadata/), plus JPL D-102272 Rev E, *NISAR L2 GUNW Product Specification* (November 8, 2024; checked-in text at `external/reference/nisar/NISAR_D-102272_RevE_L2_GUNW.txt` in the verified Colorado repository), for GUNW layers, phase units, center frequency, LOS vectors, radar-grid interpolation, and product structure; the SnowIn Stage 1 canonical source-to-phase contract remains authoritative where the product specification does not spell out the sign in a user-facing equation. The COP30 local-incidence definition follows the verified Colorado repository's committed implementation and is independently reimplemented in SnowIn in radians. |
| Exact adapter behavior | `open_gunw()` reads GUNW unwrapped phase in radians, normalizes the documented source `reference_minus_secondary` phase with `multiply_by_-1` to SnowIn `secondary_minus_reference`, and derives wavelength as `299792458.0 / centerFrequency_hz` unless an explicit `wavelength_m` override is supplied. It stops before DEM/LOS geometry and records `incidence_angle_status="not_computed"`. `compute_gunw_incidence()` requires the explicit GUNW path and an opened target Dataset; `add_gunw_incidence()` appends the result. The default geometry path downloads/caches the ASF/NASA modified Copernicus DEM used by NISAR, covering the GUNW phase-grid footprint, unless a local `nisar_cop30_dem` raster is supplied. The legacy public COP30 downloader remains available with `dem_source="cop30"`; `dem_source="tandem30"` and `dem_source="srtm30"` accept explicit local rasters and never auto-download or substitute sources. Local incidence is derived from the selected DEM and GUNW target-to-sensor LOS vectors, interpolated through the radar-grid height/y/x lookup cube, and normalized to radians. The explicit `product_ellipsoid` mode uses the product `incidenceAngle` field only when requested. Slow I/O/geometry functions emit simple progress text unless `progress=False`. |
| Units and assumptions | Wavelength is metres; phase and normalized incidence are radians; DEM elevation is projected metres; the NISAR-modified Copernicus DEM is treated as WGS84 ellipsoidal, raw COP30 as EGM2008 orthometric, TanDEM-X 30 m as WGS84-G1150 ellipsoidal, and SRTM30 as EGM96 orthometric unless the input metadata declares otherwise; local incidence is the angle between the target-to-sensor LOS and the DEM-derived terrain normal; product ellipsoid incidence is not a substitute for local incidence. The adapter does not apply ionospheric/tropospheric corrections, reference phase, masks beyond the optional product layers, or Colorado study selection. |
| Repositories inspected | Verified Colorado checkout `/Users/jtarrico/ch13_nisar_prelim`, remote-confirmed as `jacktarricone/nisar-grl-colorado-firstlook`, `HEAD f5c17ef`; `ZachHoppinen/nisar_pytools`, remote `https://github.com/ZachHoppinen/nisar_pytools`, inspected commit `0a8f6b9`; NASA/ASF NISAR product documentation; existing SnowIn GUNW readers and Stage 1 contracts. |
| Implementation relationship | Independently reimplemented adapter and COP30 local-incidence calculation. `nisar_pytools` was evaluated but not imported as a SnowIn runtime dependency: its lazy `open_nisar`/DataTree reader is useful, but its current GUNW metadata helpers do not expose the authoritative center-frequency-to-wavelength resolution or the SnowIn normalized pair contract. SnowIn therefore uses a thin direct xarray/h5netcdf boundary and keeps product-reader internals private. No Colorado code was copied. |
| Licensing implications | `nisar_pytools` declares MIT, but no code was copied or adapted. NASA/ASF product documentation is referenced as documentation, not bundled code. SnowIn's Apache-2.0 license remains applicable to the independent implementation. |
| Validation evidence | Synthetic GUNW HDF5 tests cover source-sign normalization, missing/unknown source conventions, explicit radian metadata, center-frequency wavelength resolution, COP30 local-incidence generation, normalized metadata, and eager/lazy opening. The opt-in chunked geometry prototype is tested for lazy backing and exact synthetic equivalence, and the Colorado real product produced an exact eager/chunked match. A real downloaded GUNW was inspected for authoritative paths and units; no Colorado study output or ASO data was used to tune the adapter. |
| Remaining uncertainties | The public GUNW user guide describes the reference/secondary product lineage and layer semantics but does not provide a compact standalone phase-sign equation. The adapter follows the Stage 1 NISAR/ISCE3 contract and records the transform; a future product-level sign regression should use a formally documented ISCE3/NISAR fixture. The default NISAR-modified Copernicus DEM is WGS84 ellipsoidal and requires Earthdata access or a local cached raster; raw COP30 remains EGM2008 orthometric and requires explicit correction. NISAR local incidence remains eager by default for v0.1; `geometry_chunks` is an opt-in prototype that still loads DEM/LOS/normals eagerly. Download failures are surfaced and never replaced by another DEM. |
| Status | Stage 3 adapter implemented and characterized; Stage 5 reference-phase foundation and Stage 6 explicit-path accumulation are implemented separately. Corrections beyond the documented vertical-datum hook and Colorado workflow integration remain out of scope. |

## Stage 5 reference phase

| Field | Record |
| --- | --- |
| Capability | Public `snowin.reference_phase`; implementation helpers `snowin.reference.estimate_reference_offset` and `snowin.reference.apply_reference_offset`. |
| Scientific source | The verified Colorado frozen configuration `config/frozen/paper_reproduction_v2.json` at Colorado repository `HEAD f5c17ef` declares method `zhou_cwls_all_finite` and the additive offset equation. The primary scientific reference for the coherence-weighted phase calibration algebra is Zhou et al., *Snow water equivalent retrieval and analysis using 12 d Sentinel-1 interferometry*, The Cryosphere (2025), Eq. 6 ([DOI](https://doi.org/10.5194/tc-19-5361-2025)). |
| Colorado audit | The frozen method uses one offset per eligible frame pair; five explicit SNOTEL stations; the existing native 5x5 station window; exact local-date dSWE with no interpolation; coherence as a station calibration weight and diagnostic, never a raster support threshold; and `phi_calibrated = phi_observed - C_hat`. ASO, VIIRS, models, and downstream metrics are excluded from reference estimation and branch selection. |
| Exact generic behavior | The coherence-weighted mode uses `C_hat = sum(weight * (observed_phase - expected_phase)) / sum(weight)` over finite, non-excluded observed/expected phases and finite positive weights; `phase_referenced = phase - C_hat`. Manual mode uses the supplied finite `offset_rad`; single-station mode requires exactly one eligible residual; mean mode uses the unweighted mean residual; median mode uses the robust median residual. Unsupported estimates return a NaN offset, missing referenced phase, explicit `reference_estimate_supported=False`, contributor-level exclusion reasons, and status metadata rather than assuming zero. |
| API boundary | The xarray API accepts a normalized pair Dataset and either a manual offset or explicit contributor-level observed phase, expected phase, weights, optional IDs, and optional exclusion reasons. SnowIn does not embed SNOTEL I/O, station allowlists, date matching, native window selection, or Colorado expected-phase construction. |
| Implementation relationship | Independently reimplemented in `src/snowin/reference/phase.py`; no Colorado code was copied. The legacy NumPy `apply_reference_phase()` strategies remain compatibility behavior and are not the canonical Stage 5 workflow. |
| Validation evidence | `tests/test_reference.py` covers zero, positive, and negative offsets; subtraction direction; manual, single-station, unweighted mean, robust median, and Colorado weighted algebra; exclusions and missing contributors; unsupported estimates; NaN propagation; explicit units; xarray dimensions/coordinates/attributes; and Dask-backed phase equivalence. |
| Remaining uncertainties | The generic offset algebra is identified, but the scientific construction of `expected_phase` and the selection/date-matching policy for any production station source remain caller-owned and require a later Colorado workflow characterization. Vertical-datum geometry uncertainty from Stage 4 remains documented and is not hidden by reference processing. |

## Stage 4 geometry validation

| Field | Record |
| --- | --- |
| Capability | Hardening and regression validation of `snowin.io.nisar.compute_cop30_local_incidence` and its DEM/LOS preparation path. |
| Equation | `n = normalize((-dz/dx, -dz/dy, 1))`; interpolate the target-to-sensor LOS unit vector `l = (los_x, los_y, los_z)` through the GUNW radar-grid `(heightAboveEllipsoid, y, x)` cube at each DEM surface height; `incidence_angle = arccos(clip(dot(l, n), -1, 1))`. The returned angle is radians in `[0, pi]`. |
| Grid and interpolation rules | GUNW projected x/y coordinates and the selected DEM elevations are placed on the exact requested phase-grid coordinates. DEM source values are bilinearly reprojected with validity weights; radar-grid LOS components use linear regular-grid interpolation in height, y, and x; out-of-range lookup is rejected rather than extrapolated. Coordinates must be strictly monotonic. |
| Reference semantics | GUNW radar-grid heights are `heightAboveEllipsoid` in the WGS84 ellipsoid reference. The NISAR-modified Copernicus DEM is explicitly re-referenced to WGS84 ellipsoidal heights; the original GLO-30 source is EGM2008 orthometric. SnowIn accepts a same-grid geoid-undulation correction for orthometric compatibility sources with the explicit convention `ellipsoidal_height = orthometric_height + geoid_undulation`, records whether it was applied, and can reject uncorrected geometry with `require_vertical_datum_match=True`. |
| Regression fixture | `tests/fixtures/real_product_geometry.json` records one verified GUNW, one public Copernicus GLO-30 tile, a 128x128 projected subset, expected incidence statistics, a 2e-6 rad tolerance, and the independent Colorado comparison (`f5c17ef`). The test runs when `SNOWIN_STAGE4_GUNW` and `SNOWIN_STAGE4_COP30_DEM` point to the external fixture files; otherwise it skips without bundling large external rasters. |
| Validation evidence | `tests/test_geometry.py` covers analytic flat and sloped DEMs, explicit vertical correction and required-datum failure, CRS absence, DEM non-overlap, out-of-range LOS interpolation, non-monotonic coordinates, legal LOS-Z derivation from X/Y, impossible missing-X/Y input, and the real-product regression path. The fixture expected values were generated independently with the verified Colorado implementation; no ASO data was used for tuning. |
| Execution model | Phase/product arrays remain lazy in `open_gunw`; NISAR DEM reprojection and SciPy LOS interpolation are eager by default. `geometry_chunks` provides an opt-in Dask-backed prototype that evaluates output chunks separately but still loads the DEM, LOS cube, and terrain normals eagerly. The real Colorado benchmark was numerically exact and reduced observed peak memory from about 6.7 GiB to about 5.7 GiB, but the eager default remains until broader benchmarking and review. |

## Stage 6 temporal accumulation

| Field | Record |
| --- | --- |
| Capability | Public `snowin.accumulate_dswe`. |
| Scientific contract | A sequence of pairwise dSWE Datasets forms an explicit directed path only when every edge declares `temporal_edge="reference_to_secondary"`, each secondary time is later than its reference time, and each next reference time equals the prior secondary time. |
| Exact behavior | The result is cumulative dSWE at each edge's secondary time. Finite pairwise dSWE and optional `pairwise_supported=True` are required for sample support; unsupported samples propagate as missing through later path endpoints and are never replaced by zero. |
| Implementation relationship | Independently implemented as xarray-native path accumulation in `src/snowin/temporal.py`; no Colorado temporal code or study-specific path configuration was copied. |
| Validation evidence | `tests/test_temporal.py` covers accumulation algebra, path support propagation, explicit support variables, chronology, contiguity, input ordering, initial-time validation, incompatible grids, metadata, coordinates, and Dask-backed equivalence. |
| Remaining uncertainties | The API intentionally accepts one explicit path sequence. General graph selection, branching paths, temporal gap policies, and study-specific path construction remain outside Stage 6 and require a later contract. |

## Stage 7 support and metrics

| Field | Record |
| --- | --- |
| Capability | Public `snowin.build_support_dataset`, `snowin.compose_support_mask`, `snowin.summarize_support`, and `snowin.compute_metrics`. |
| Scientific contract | Product validity, geometry validity, reference support, pairwise support, temporal-path support, evaluation support, snow-state support, and coherence policy remain separate named layers. No layer is silently promoted to a universal quality mask. |
| Exact behavior | Derived support masks are explicit conjunctions chosen by the caller. Unknown support is not assumed true; summaries report known and supported counts separately. Metrics use `estimated - observed` for bias and report finite/support counts, support fraction, units, metric status, and support-policy provenance. |
| Implementation relationship | Independently implemented as xarray-native helpers in `src/snowin/quality/support.py` and `src/snowin/quality/metrics.py`. The existing NumPy GUNW quality helper remains compatibility behavior and is not used by the canonical Stage 7 API. |
| Validation evidence | `tests/test_support_metrics.py` covers named-layer separation, unknown-versus-false support, explicit mask composition, grid validation, invalid support values, bias/MAE/RMSE/correlation algebra, unsupported metrics, and Dask-backed equivalence. |
| Remaining uncertainties | Colorado-specific evaluation subsets, thresholds, effective sample-size treatment for spatial autocorrelation, and validation-data adapters remain outside Stage 7. No ASO or other validation data were used for tuning. |

## Stage 8 Colorado downstream integration

| Field | Record |
| --- | --- |
| Capability | First downstream integration boundary for the verified Colorado NISAR first-look repository. |
| Downstream identity | `jacktarricone/nisar-grl-colorado-firstlook`, verified checkout `/Users/jtarrico/ch13_nisar_prelim`; integration branch `codex/stage8-snowin-integration`. |
| SnowIn dependency | Colorado pins SnowIn Git commit `e5783fc`; the current checkout requires SSH Git access because no public release artifact exists yet. |
| Implementation relationship | Colorado independently added `analysis/snowin_adapter.py`, which translates its reviewed NumPy/raster arrays into SnowIn's xarray contract and delegates dSWE, reference offset application, temporal accumulation, support composition, metrics, and COP30 local incidence. No Colorado station, date, basin, output, or sensitivity configuration was moved into SnowIn. |
| Validation evidence | Colorado focused integration tests pass `4/4`; the full downstream suite passes `50/50`; Ruff, formatting, package build, and `git diff --check` pass. Synthetic algebra matches the legacy Colorado calculation to `1e-12` mm when the input is explicitly declared canonical. |
| Scientific gate | The frozen Colorado path records historical `phase_sign=+1`, while SnowIn's verified NISAR adapter records delivered GUNW phase as `reference_minus_secondary` and transforms it to canonical `secondary_minus_reference`. The real-product comparison must establish whether Colorado's `T0_DELIVERED` phase was already normalized before duplicate retrieval code is removed. No ASO tuning or silent sign selection was performed. |
| Status | Integration boundary implemented side-by-side; real GUNW/COP30 reproduction and duplicate-code removal remain gated by phase-lineage evidence. |
