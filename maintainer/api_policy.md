# SnowIn API policy

SnowIn's stable scientific boundary consists of plain xarray
`DataArray` and `Dataset` inputs and outputs. Public functions express
snow/InSAR-specific science; mission details remain in adapters.

## Public exports

The root package exports the stable generic functions and version:

```python
from snowin import (
    __version__,
    accumulate_dswe,
    build_support_dataset,
    compose_support_mask,
    compute_guneriussen_dswe,
    compute_leinss_dswe,
    compute_oveisgharan_dswe,
    reference_phase,
    summarize_support,
)
```

The complete supported module exports are:

- `snowin.snow`: `compute_leinss_dswe`, `compute_guneriussen_dswe`,
  `compute_oveisgharan_dswe`.
- `snowin.io`: `DEMSource`, `NISAR_GUNW_PHASE_TRANSFORM`,
  `NISAR_GUNW_SOURCE_PHASE_DEFINITION`, `open_gunw`, `normalize_gunw_pair`,
  `read_gunw_wavelength_m`, `compute_gunw_incidence`, `add_gunw_incidence`,
  `compute_cop30_local_incidence`.
- `snowin.reference`: `estimate_reference_offset`, `apply_reference_offset`,
  `reference_phase`, `REFERENCE_CONTRIBUTOR_DIM`, `REFERENCE_METHODS`,
  `MANUAL_OFFSET_METHOD`, `SINGLE_STATION_METHOD`, `MEAN_OFFSET_METHOD`,
  `MEDIAN_OFFSET_METHOD`, `COHERENCE_WEIGHTED_METHOD`.
- `snowin.quality`: `build_support_dataset`, `compose_support_mask`,
  `summarize_support`, `SUPPORT_CATEGORIES`.
- `snowin.temporal`: `accumulate_dswe`.

The constants name source conventions, result dimensions, supported reference
methods, and support categories used in returned metadata and validation.
Private helpers are not part of the supported API. Re-exports such as
`snowin.reference_phase` and `snowin.snow.compute_leinss_dswe` are intentional
facade and domain-module import paths.

## Product and data states

`open_gunw()` returns a phase-normalized product using the SnowIn phase
convention, authoritative wavelength, temporal metadata, and source metadata. It intentionally
does not calculate incidence. `add_gunw_incidence()` computes geometry from an
explicit GUNW and caller-prepared DEM, then adds incidence and geometry support
to the same Dataset. The result is a retrieval-ready pair. See the
[data model](../docs/data_model.md) for state attributes and required variables.

`add_gunw_incidence()` mutates its target and returns that same Dataset. This
preserves the `close()` callback that owns lazy GUNW file resources.

## Scientific methods

Each dSWE equation has one explicit public function:

- `compute_leinss_dswe`
- `compute_guneriussen_dswe`
- `compute_oveisgharan_dswe`

All require `wavelength_m`; product adapters should obtain it from
authoritative metadata when available. There is no generic model selector,
sensor wavelength registry, or Leinss alias. Reference estimation requires
explicit contributors or a manual offset. Support layers remain separately
named and are combined only when the caller names them. Temporal accumulation
accepts an explicitly ordered, contiguous chronological path.

## Outside the package boundary

Product discovery, cloud access, ancillary data, GIS file operations, plots,
generic evaluation metrics, and study-specific validation remain caller-owned.
Correction layers can be exposed by the GUNW adapter but are not applied by
SnowIn 0.1. No automatic reference, correction, mask, or science-grid
resampling policy is provided.
