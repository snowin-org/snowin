# SnowIn API policy

SnowIn's stable scientific boundary consists of plain xarray
`DataArray` and `Dataset` inputs and outputs. Public functions express
snow/InSAR-specific science; mission details remain in adapters.

## Supported imports

Generic retrieval, reference, support, and temporal functions are available
from `snowin`:

```python
from snowin import (
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

The NISAR product adapter and geometry functions are available from
`snowin.io`. The xarray contributor-based reference helpers are available from
`snowin.reference`. Named support operations live in `snowin.quality.support`.

## Product and data states

`open_gunw()` returns a phase-normalized product with canonical phase,
authoritative wavelength, temporal metadata, and provenance. It intentionally
does not calculate incidence. `add_gunw_incidence()` computes geometry from an
explicit GUNW and caller-prepared DEM, then adds incidence and geometry support
to the same Dataset. The result is a retrieval-ready pair. See the
[data model](data_model.md) for state attributes and required variables.

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
SnowIn; correction application is deferred until a scientifically frozen
xarray contract is established. No automatic reference, correction, mask, or
resampling policy is provided.
