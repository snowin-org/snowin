# Colorado T019/F021 reference-offset reconstruction

This development record independently rebuilds the Colorado reference offset
from the per-station rows produced by the downstream correction audit. It is
separate from the reviewed/frozen path-offset table: the former tests the
offset algebra and station gates, while the latter is a study-policy input.

## Inputs and method

- Frame: `T019_F021`.
- Edges: all 23 products in the Colorado path, from `2025-10-30` through
  `2026-08-14`.
- Station evidence: downstream `*_station_rows.csv` files from the
  `20260922T_t019_f021_v04/all_finite` audit.
- For each edge, SnowIn consumed only `phase_observed_rad`,
  `expected_phase_rad`, `coherence_observed`, `eligible`, `station_id`, and
  `reason` from the station rows.
- The independent calculation used SnowIn's generic
  `coherence_weighted_additive_offset` estimator:

  ```text
  offset = sum(coherence * (observed_phase - expected_phase)) /
           sum(coherence)
  ```

- It was compared against the downstream `all_station_offset_rad` values in
  retrieval `v01`, and separately against the reviewed values in
  `data/accepted_path_reference_offsets.csv`.

## Results

The independent reconstruction matches the downstream all-station calculation
for every edge:

| Check | Result |
| --- | ---: |
| Edges reconstructed | `23` |
| Maximum absolute difference from downstream all-station offset | `0.0 rad` |
| Eligible-station counts | `4` or `5` |
| Repeated excluded station | `737:CO:SNTL` when its corrected window was invalid |
| Maximum absolute difference from reviewed/frozen path offset | `2.552449 rad` |

The exact difference from the reviewed path offsets is scientifically useful.
It shows that the accepted path is not simply the raw all-eligible weighted
station calculation. For example, the first edge reconstructs to
`-19.968189 rad`, while the reviewed path input is `-19.947856 rad`; the edge
starting `2025-12-05` reconstructs to `-13.401094 rad`, while the reviewed
input is `-12.916696 rad`. The largest observed difference is the edge starting
`2026-05-10`, at `2.552449 rad`.

Therefore SnowIn should expose the generic offset algebra and preserve the
station-level provenance, but should not import Colorado's station/date
allowlist or silently replace reviewed path offsets. Those remain downstream
study policy until the Colorado phase-boundary decision is approved.

## Reproduction evidence

The calculation was run with SnowIn's xarray-native reference estimator and
the following external artifacts:

- downstream audit output:
  `outputs/nisar_firstlook/erb/atmospheric_correction_audit/20260922T_t019_f021_v04/all_finite/`;
- downstream all-station comparison:
  `outputs/nisar_firstlook/erb/atmospheric_correction_retrieval/20260922T_t019_f021_v01/pairwise_reference_and_support.csv`;
- reviewed path offsets:
  `data/accepted_path_reference_offsets.csv`;
- downstream checkout commit:
  `009005c2c6a415f4b9f74d04300fe62b89167730`.

The external products are intentionally not vendored into SnowIn. Notebook 03
contains the same two-mode comparison pattern for an individual real edge.

The per-edge values are preserved in
[`colorado_t019_reference_offsets.csv`](colorado_t019_reference_offsets.csv).
