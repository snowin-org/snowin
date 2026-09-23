# Colorado T019/F021 full-path comparison

This record documents the controlled end-to-end comparison between the
Colorado downstream retrieval and SnowIn's xarray-native workflow. It is a
development validation record, not a CI fixture: the GUNWs, incidence raster,
station-derived offsets, and downstream checkout remain external inputs.

## Frozen inputs

- SnowIn commit: `058990c8b2fffe33c6d2be5fa3fe2bac57db05fc`.
- Downstream checkout: `/Users/jtarrico/ch13_nisar_prelim`.
- Downstream commit: `009005c2c6a415f4b9f74d04300fe62b89167730`.
- Downstream tracked entry point:
  `scripts/nisar_firstlook/analysis/run_pair_retrieval.py` and
  `scripts/nisar_firstlook/analysis/run_path_retrieval.py`.
- The downstream checkout had unrelated untracked atmospheric-correction
  files. They were not imported or used by this comparison.
- Product family: provisional NISAR GUNW, `frequencyA`, `HH`, frame
  `T019_F021`.
- Path source: `data/accepted_path_reference_offsets.csv`, filtered to
  `T019_F021`, method `zhou_cwls_all_finite`, component `ALL_FINITE`.
- Native downstream incidence raster:
  `outputs/nisar_firstlook/erb/local_incidence/20260918T_cop30_incidence_schofield_context_v02/T019_F021_local_incidence_80m_full.tif`.
- The downstream incidence raster declares degrees. SnowIn received the same
  values converted explicitly to radians for the controlled equivalence run.
- Frozen Colorado wavelength: `0.238403545 m`.
- The 23-edge manifest hash was
  `b41bbfc9e870d77fd901cf20bcb8f7d52cae3a890c81ff22b4f84b648da794c0`.

## Downstream commands

The manifest was built with:

```bash
python scripts/nisar_firstlook/analysis/build_path_manifest.py \
  --config config/frozen/paper_reproduction_v2.json \
  --offsets data/accepted_path_reference_offsets.csv \
  --frame T019_F021 \
  --product-root data/nisar/gunw/provisional/erb/asc \
  --incidence /external/T019_F021_local_incidence_80m_full.tif \
  --output /tmp/t019_path_manifest.json
```

The downstream path was then run with:

```bash
python scripts/nisar_firstlook/analysis/run_path_retrieval.py \
  --config config/frozen/paper_reproduction_v2.json \
  --manifest /tmp/t019_path_manifest.json \
  --run-id downstream_t019_f021_path \
  --output-root /tmp/downstream-path
```

This produced 23 pairwise dSWE rasters, 23 provenance rasters, and a strict
cumulative dSWE raster.

## SnowIn controlled workflow

For each manifest edge, SnowIn performed:

```text
open_gunw(product, wavelength_m=0.238403545)
    -> append the declared downstream incidence grid as radians
    -> reference_phase(..., method="manual_offset")
    -> compute_dswe(...)
    -> accumulate_dswe(edges)
```

Because SnowIn normalizes the GUNW to
`secondary_minus_reference`, the downstream raw-phase offset changes sign
when supplied to SnowIn. No additional phase sign conversion was applied.
The connected-component layer was used only to reproduce the downstream
provenance classes; it was not used as a lead retrieval mask.

## Results

| Check | Result |
| --- | ---: |
| Directed edges | 23 |
| Canonical phase + downstream raw phase, maximum absolute residual | `0.0 rad` |
| Canonical referenced phase + downstream referenced phase, maximum absolute residual | `3.81e-6 rad` |
| Pairwise dSWE, maximum absolute residual | `9.16e-5 mm` |
| Pairwise dSWE, mean absolute residual | `3.86e-6 mm` |
| Pairwise support-mask mismatches | `0` |
| Provenance-class mismatches | `0` |
| Final cumulative dSWE, maximum absolute residual | `3.05e-4 mm` |
| Final cumulative dSWE, mean absolute residual | `1.78e-5 mm` |
| Final complete-path support fraction | `0.111294` |

The cumulative result preserved SnowIn's declared policy:
`propagate_missing; never substitute zero`.

## Geometry and wavelength separation

The full-path equivalence above intentionally uses the downstream incidence
grid so phase, reference, support, provenance, and temporal behavior can be
tested independently of DEM differences.

The same first Colorado GUNW was also run through SnowIn's real geometry
workflow using the cached NISAR-modified Copernicus DEM. That run produced:

- incidence source: `NISAR Copernicus DEM plus NISAR GUNW radar-grid LOS`;
- finite incidence fraction: `0.999203`;
- valid `0 < incidence < 90°` fraction: `0.998975`;
- incidence range: `0.168°` to `116.617°`;
- incidence overlap with the downstream raster: `0.309444` of the full grid;
- mean absolute incidence difference over that overlap: `0.3693°`.

Using SnowIn's NISAR DEM incidence therefore produces a real geometry
difference from the retained downstream COP30 raster. That difference is
separate from the controlled retrieval equivalence and must be quantified in
the Colorado migration validation before the downstream duplicate path is
retired.

SnowIn also derives `0.2419632429 m` from this product's center-frequency
metadata, while the frozen Colorado configuration uses `0.238403545 m`. The
controlled comparison uses the frozen value. Colorado has decided to adopt
SnowIn's product-metadata wavelength treatment; the historical value remains
part of this controlled baseline only and should not override the SnowIn
default in the migrated workflow.

## Decision

The controlled SnowIn workflow reproduces the Colorado phase lineage,
reference-offset sign, support policy, connected-component provenance, and
strict temporal accumulation when the same incidence grid and frozen
wavelength are supplied. Colorado has decided to adopt SnowIn's canonical
normalized phase, NISAR-modified Copernicus DEM geometry, and product-metadata
wavelength treatment. The next engineering step is to validate that adopted
configuration across the 23-edge path against this controlled baseline. Keep
the legacy retrieval during that validation; Colorado's station/date and
reviewed-offset policy remains explicit downstream input.
