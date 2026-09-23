# Colorado downstream evidence

This note records what SnowIn learned from the Colorado first-look
repository. It is evidence for the generic interfaces; it is not a transfer
of Colorado's station list, date policy, basin selection, or output policy
into SnowIn.

## Real GUNW and DEM check

The comparison used the real Poudre/Colorado provisional GUNW

`NISAR_L2_PR_GUNW_004_019_A_021_005_4000_SH_20251030T121115_20251030T121143_20251111T121116_20251111T121144_P05023_N_F_J_001`.

The product declares:

- reference acquisition: `2025-10-30T12:11:15.000000000` UTC;
- secondary acquisition: `2025-11-11T12:11:16.000000000` UTC;
- unwrapped phase units: radians;
- radar-grid height description: above the WGS84 ellipsoid;
- phase grid: 4,347 × 4,410 cells, EPSG:32613.

SnowIn opened the complete phase grid with the NISAR-modified Copernicus DEM
downloaded from the ASF/NASA Earthdata distribution. In the current
development environment, the direct eager workflow took 0.37 seconds to open
the product and 9.29 seconds for incidence geometry; the process peak was
approximately 6.7 GiB for this eager full-grid geometry run. It produced local
incidence angles from 0.00293 to 2.03534 radians (0.17° to 116.62°). The
finite fraction was 99.92%, and 99.90% of cells fell within the retrieval's
valid 0–90° geometry domain. A central 128 × 128 window was used for the
numerical retrieval comparison.

The DEM is retained outside the repository cache/workspace because it is a
large external product. SnowIn natively downloads, mosaics, caches, and
records this DEM source; raw GUNW and DEM files are not release artifacts.

## Phase-sign lineage

The downstream Colorado reader returns the delivered `unwrappedPhase` values
unchanged. Its frozen configuration then applies historical `phase_sign=+1`
in the phase-to-dSWE kernel. The SnowIn NISAR adapter records the GUNW source
definition as `reference_minus_secondary` and transforms it to SnowIn's
canonical `secondary_minus_reference` convention with `multiply_by_-1`.

On the real product's 128 × 128 window, with zero reference offset and the
same wavelength/path constant, the old downstream retrieval and the SnowIn
retrieval were exact negatives: maximum absolute residual of
`1.14e-13 mm` after adding the two arrays. This is an explicit lineage
result, not a sign inferred from numerical values.

This resolves the historical Colorado boundary: `T0_DELIVERED` is the raw
delivered GUNW `unwrappedPhase` field, not a phase-normalized intermediate.
Consequently, the frozen Colorado `phase_sign=+1` retrieval is opposite to
SnowIn's product-normalized canonical phase. Colorado has decided to migrate
to SnowIn's `secondary_minus_reference` phase, NISAR-modified Copernicus DEM
geometry, and product-metadata wavelength treatment. The duplicate downstream
retrieval code remains in place during validation of that adopted configuration;
SnowIn must not silently rewire `gunw_to_dswe()` before the Colorado workflow
has been explicitly migrated and checked.

## Downstream pair reproduction

The downstream Colorado pair driver was rerun for the same T019/F021 raw GUNW
with the retained native local-incidence raster and `offset_rad=0`. Its test
suite passed (`51 passed`), and the fresh pair run wrote raw phase,
referenced phase, pairwise dSWE, and provenance-class rasters under the
external directory `/private/tmp/snowin-colorado-downstream-baseline/`.

The SnowIn canonical phase and the downstream raw phase were exact negatives
over the complete product (`max(abs(phi_snowin + phi_downstream_raw)) = 0.0`
radians). Using the same downstream incidence raster and frozen Colorado
wavelength `0.238403545` m, SnowIn dSWE plus downstream dSWE had a maximum
absolute residual of `3.99e-05 mm` over 16,368 valid pixels in a 128 × 128
valid window. This reproduces the expected sign-lineage difference without
confounding it with the new NISAR DEM geometry.

The new NISAR DEM incidence is not numerically identical to the retained
downstream COP30 raster: over their finite overlap, the absolute difference
was 0.489° mean, 1.412° at the 95th percentile, and 31.98° maximum. The
retained downstream raster has nodata outside its prepared analysis footprint
(1.23% finite over the full product), so those geometry statistics are an
overlap characterization rather than a whole-scene validation. Validate the
adopted NISAR DEM geometry against the retained downstream raster before
retiring the duplicate retrieval path.

## Reference-phase inputs and support rules

The downstream frozen configuration and methods documentation characterize
the following caller-owned inputs and rules:

| Area | Downstream evidence | SnowIn boundary |
| --- | --- | --- |
| Reference contributors | Five explicit Colorado SNOTEL stations, one offset per eligible directed pair/component | Accept contributor-level observed phase, expected phase, weights, IDs, and exclusion reasons; no station I/O or allowlist |
| Expected phase | `y_i = K_i * dSWE_i` using the directed pair | Caller constructs `expected_phase` |
| Station dates | Exact local-date dSWE for the directed NISAR pair; no interpolation | Caller supplies matched dates/values |
| Station sampling | Existing native 5×5 window | Caller supplies sampled phase/geometry |
| Coherence | Calibration weight and diagnostic only; never a raster support threshold | SnowIn keeps weighting and support as separate concerns |
| Raster support | Finite phase plus finite valid geometry; reference and pairwise support are named layers | Caller composes named support layers |
| Connected components | Provenance and sensitivity evidence, not the lead raster mask | SnowIn preserves component/provenance data without selecting Colorado policy |
| ASO | Downstream spatial/endpoint context, not sign, branch, reference, support, threshold, or case selection | No ASO dependency |

These rules are sufficient to validate SnowIn's generic reference and support
contracts, but not to make Colorado's study policy part of the package API.
The downstream repository still owns station selection, date matching,
component handling, and study-case selection.

The frozen station allowlist is `380:CO:SNTL`, `680:CO:SNTL`, `737:CO:SNTL`,
`1141:CO:SNTL`, and `1326:CO:SNTL`. A station contribution is eligible only
when it is in that allowlist, has an exact local-date SNOTEL pair, is inside
the native grid, has finite phase, positive finite coherence, and finite
positive sensitivity; component and exact-zero-window gates are explicit
sensitivity rules. The lead raster support remains finite delivered phase
plus finite valid geometry, not positive connected-component labels or a
coherence threshold.

## Geometry execution decision

The full real-product eager benchmark completed, but its approximately 6.7 GiB
peak motivated an opt-in prototype. With ``geometry_chunks=512``, SnowIn built
a Dask-backed incidence result for the same 4,347 x 4,410 product. The result
was exactly equal to the eager angle field (`max_abs_rad = 0.0` in the direct
comparison), with a measured peak of approximately 5.7 GiB and a total
geometry time of approximately 6.4 seconds after a 4.7-second graph-building
step. The reduction is useful but not yet a complete out-of-core solution:
the DEM, LOS lookup cube, and terrain normals are still eager, and graph
construction adds overhead. The eager path therefore remains the default;
``geometry_chunks`` is retained for validation and future optimization work.

## Reproduction record

- SnowIn commit containing the NISAR DEM integration: `92f0206`.
- Colorado downstream checkout: `/Users/jtarrico/ch13_nisar_prelim`.
- Colorado downstream tests at the audited checkout: `51 passed`.
- External DEM cache used for the run: `/private/tmp/snowin_real_nisar_cop30/`.
