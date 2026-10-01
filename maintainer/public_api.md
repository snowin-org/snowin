# SnowIn public API

Public science functions take and return xarray `DataArray` and `Dataset`
objects. NISAR-specific file handling stays in `snowin.io`.

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
  `compute_local_incidence`.
- `snowin.reference`: `estimate_reference_offset`, `apply_reference_offset`,
  `reference_phase`, `REFERENCE_CONTRIBUTOR_DIM`, `REFERENCE_METHODS`,
  `MANUAL_OFFSET_METHOD`, `SINGLE_STATION_METHOD`, `MEAN_OFFSET_METHOD`,
  `MEDIAN_OFFSET_METHOD`, `COHERENCE_WEIGHTED_METHOD`.
- `snowin.quality`: `build_support_dataset`, `compose_support_mask`,
  `summarize_support`, `SUPPORT_CATEGORIES`.
- `snowin.temporal`: `accumulate_dswe`.

The constants name source conventions, result dimensions, supported reference
methods, and support categories used in returned metadata and validation.
Private helpers are not part of the supported API. Both root imports such as
`snowin.reference_phase` and submodule imports such as
`snowin.snow.compute_leinss_dswe` are supported.

## NISAR GUNW functions

`open_gunw()` returns a Dataset with phase in the SnowIn convention, wavelength,
acquisition times, and source metadata. It does not calculate incidence.
`add_gunw_incidence()` calculates incidence from the GUNW and, for local
incidence, a caller-prepared DEM. It adds incidence and geometry support to the
same Dataset. See the [data model](../docs/data_model.md) for required
variables and attributes.

`add_gunw_incidence()` updates its target and returns that same Dataset. This
keeps the `close()` callback for lazy GUNW file resources.

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

## Caller responsibilities

Product discovery, cloud access, ancillary data, GIS file operations, plots,
generic evaluation metrics, and study-specific validation remain caller-owned.
The GUNW adapter may expose correction layers but does not apply them. Callers
choose reference observations and support variables and explicitly reproject or
resample grids when needed.
