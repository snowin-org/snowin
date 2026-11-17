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
    compute_oveisgharan_2026_dswe,
    compute_oveisgharan_dswe,
    project_swe_to_vertical,
    reference_phase,
    summarize_support,
)
```

The complete supported module exports are:

- `snowin.snow`: `compute_leinss_dswe`, `compute_guneriussen_dswe`,
  `compute_oveisgharan_dswe`, `compute_oveisgharan_2026_dswe`,
  `project_swe_to_vertical`.
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
- `compute_oveisgharan_2026_dswe`

`compute_oveisgharan_dswe` retains the polynomial printed in the 2024 paper.
The separately named 2026 function uses coefficients
`[-0.3385, 0.0486, -0.8647]` in descending powers of incidence in radians.
Both return signed pairwise dSWE in metres with the canonical phase contract.

`project_swe_to_vertical(swe, slope_angle)` divides slope-normal SWE by
`cos(slope_angle)` for a layer parallel to terrain. The caller must declare
`swe_thickness_reference="slope_normal"`, metre or millimetre units, and an
aligned slope in radians. The result declares vertical thickness. This
operation preserves signed dSWE, NaNs, coordinates, metadata, and Dask laziness.
The caller determines whether the input retrieval represents normal thickness
and recomputes any in situ phase reference consistently with the chosen
geometry. The geometric relation follows
[Eppler et al. (2022), Eqs. 1–3](https://tc.copernicus.org/articles/16/1497/2022/).

All require `wavelength_m`; product adapters should obtain it from
authoritative metadata when available. There is no generic model selector,
sensor wavelength registry, or Leinss alias. Reference estimation requires
explicit contributors or a manual offset. Support layers remain separately
named and are combined only when the caller names them. Temporal accumulation
accepts an explicitly ordered, contiguous chronological path. Each input dSWE
variable must explicitly declare
`dswe_difference_definition="secondary_minus_reference"`, including schema 0.2
pairs and edges without a schema label. Dataset-level metadata is insufficient;
missing or unsupported definitions fail before accumulation. All retrieval
methods provide this attribute.

## Caller responsibilities

Product discovery, cloud access, ancillary data, GIS file operations, plots,
generic evaluation metrics, and study-specific validation remain caller-owned.
The GUNW adapter may expose correction layers but does not apply them. Callers
choose reference observations and support variables and explicitly reproject or
resample grids when needed.

## Phase contract compatibility (schema 0.2)

Public function names remain unchanged. Phase now requires
`phase_difference_definition="reference_minus_secondary"`; dSWE remains
`SWE_secondary - SWE_reference`, explicitly recorded as
`dswe_difference_definition="secondary_minus_reference"`. NISAR ingestion uses
identity, while explicitly declared opposite numeric phase converts once at
`normalize_gunw_pair`. Observed/expected reference contributors and offsets
require the canonical convention. This is a breaking scientific contract change
within the unreleased 0.1.0 package; package version alone cannot identify the
old behavior. Pin the reviewed commit and inspect schema/provenance. See
[the migration guide](../docs/phase_migration.md). Saved dSWE must not be
implicitly inverted.
