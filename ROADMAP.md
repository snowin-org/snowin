# SnowIn roadmap

SnowIn is a pre-release scientific package. This roadmap records the current
direction without making study-specific Colorado configuration part of the
general package contract.

## Implemented foundations

- xarray Dataset contracts and explicit phase, time, unit, support, and
  provenance conventions.
- Canonical xarray-native `compute_dswe` using the reviewed Leinss relation.
- NISAR GUNW reading, source-phase normalization, product wavelength
  resolution, lazy phase handling, and NISAR-modified Copernicus/local-DEM
  incidence geometry.
- Reference-phase methods, directed temporal accumulation, named support
  layers, support summaries, and reusable metrics.
- GUNW diagnostics, plotting, CLI scaffolding, and a downstream Colorado
  integration boundary.

## Now

- Use the NISAR-modified Copernicus DEM by default for real products; retain
  the original public orthometric COP30 path as an explicit compatibility
  source requiring correction.
- Continue real-product geometry characterization. The v0.1 decision is to
  keep geometry eager while phase/product arrays remain Dask-compatible; revisit
  chunk-aware geometry only after a representative benchmark. The first full
  Colorado benchmark completed on the real 4,347 × 4,410 product; retain the
  decision unless a larger production case changes the memory/performance
  result.
- Keep regression evidence reproducible without storing large external GUNW or
  DEM files in the repository.

## Next

- Characterize reference-phase inputs and support rules using Colorado as
  downstream evidence, without importing its station/date policy. The generic
  input/support characterization is recorded in
  `docs/colorado_downstream_evidence.md`; the remaining gate is an explicit
  Colorado declaration of whether `T0_DELIVERED` is raw or pre-normalized
  GUNW phase.
- Resolve the explicit Colorado declaration of whether `T0_DELIVERED` is raw
  or pre-normalized GUNW phase, reproduce the downstream output comparison
  with that declaration, and only then remove duplicate retrieval code.
- Publish the source docs site through the repository workflow and create the
  annotated release tag after the phase-lineage gate is closed. The local
  Python 3.12 wheel install, CLI help smoke test, strict docs build, package
  build, and release metadata checks now pass.

## Later

- Broaden supported product adapters, including GSLC where its scientific and
  data contracts are verified.
- Add coverage, documentation publishing, and broader Python/platform testing
  when those services and maintenance needs justify the additional process.
- Prepare PyPI/Conda packaging only after the scientific workflow and public API
  are stable and reproducible.

Colorado first-look workflows remain downstream applications. Their frozen
station lists, dates, basin choices, sensitivity analyses, and output policies
must remain in the Colorado repository.
