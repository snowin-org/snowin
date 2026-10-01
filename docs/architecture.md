# Architecture

SnowIn is a thin, scientifically explicit snow-InSAR layer built on xarray
and the Scientific Python stack. It accepts and returns ordinary
`DataArray` and `Dataset` objects. It does not define a custom scene, product,
stack, or workflow model.

## Data flow

```text
mission product or caller-prepared arrays
                 |
                 v
        thin product adapter
                 |
                 v
       phase-normalized xarray
                 |
       explicit SnowIn science
                 |
                 v
      pairwise or cumulative dSWE
                 |
                 v
       caller-owned workflow
```

`snowin.io.open_gunw()` normalizes NISAR GUNW phase, records its source
convention and provenance, and resolves wavelength from center frequency. It
does not compute incidence. `add_gunw_incidence()` separately uses the
explicit GUNW path and a prepared DEM to derive local incidence. The resulting
Dataset is retrieval-ready.

The scientific layer provides three named phase-to-dSWE equations, explicit
xarray reference estimation and application, named support composition, and
chronological accumulation over a caller-ordered contiguous path. Missing
support propagates as missing. No correction or mask policy is implicit.

## Package boundary

The package owns reusable snow/InSAR scientific semantics that general
libraries do not supply: canonical phase direction, named snow retrieval
equations, local-incidence interpretation, explicit reference offsets,
separate support meaning, and directed dSWE path accumulation.

Product discovery and downloads belong to `nisar-pytools`; DEM acquisition,
GIS preparation, station and validation data, generic metrics, plotting,
export, and study decisions belong to downstream workflows. NISAR correction
layers are exposed with provenance but are not applied. A correction operation
will belong in SnowIn only after a scientifically reviewed xarray contract
defines the quantities, signs, and alignment requirements.

## Modules and dependencies

- `snowin.snow`: named phase-to-dSWE models.
- `snowin.io`: NISAR GUNW normalization and local-incidence geometry.
- `snowin.reference`: contributor-based xarray phase referencing.
- `snowin.quality.support`: separately named support layers and composition.
- `snowin.temporal`: chronological accumulation over explicit edges.

Base runtime dependencies are NumPy and xarray. NISAR file access, geometry,
and Dask support are optional extras. Development, documentation, and notebook
tools are dependency groups and do not enter wheel runtime metadata.
