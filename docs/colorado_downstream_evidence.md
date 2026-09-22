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
downloaded from the ASF/NASA Earthdata distribution. The eager geometry run
completed in 14.6 seconds in the validation environment and produced local
incidence angles from 0.00252 to 2.03073 radians (0.14° to 116.35°). The
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

Therefore duplicate downstream retrieval code must not be deleted yet. The
Colorado workflow must first declare whether its `T0_DELIVERED` input is raw
GUNW phase or a phase-normalized intermediate. If it is raw, the current
`phase_sign=+1` path is opposite to SnowIn's product-normalized path; if it
is already normalized upstream, that normalization must be made explicit and
tested at the boundary.

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

## Geometry execution decision

The full real-product benchmark completed without requiring chunk-aware
geometry. SnowIn therefore keeps DEM reprojection and LOS interpolation eager
for v0.1 while phase/product arrays remain Dask-compatible. A chunk-aware or
Dask geometry implementation remains a later optimization if a larger or
representative production benchmark shows a memory or throughput need.

## Reproduction record

- SnowIn commit containing the NISAR DEM integration: `92f0206`.
- Colorado downstream checkout: `/Users/jtarrico/ch13_nisar_prelim`.
- Colorado downstream tests at the audited checkout: `51 passed`.
- External DEM cache used for the run: `/private/tmp/snowin_real_nisar_cop30/`.
