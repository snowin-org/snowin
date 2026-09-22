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
- Continue real-product geometry characterization. The v0.1 default remains
  eager while phase/product arrays remain Dask-compatible. An opt-in
  `geometry_chunks` prototype now has an exact real-product comparison and a
  modest memory reduction, but it is not yet fully out-of-core.
- Keep regression evidence reproducible without storing large external GUNW or
  DEM files in the repository.

## Next

- Characterize reference-phase inputs and support rules using Colorado as
  downstream evidence, without importing its station/date policy. The generic
  input/support characterization is recorded in
  `docs/colorado_downstream_evidence.md`; current evidence resolves
  `T0_DELIVERED` as raw delivered GUNW phase.
- Treat `gunw_to_dswe` as a legacy compatibility workflow and decide whether
  to rewire or retire it only after an explicit Colorado migration decision.
- Reproduce the downstream output comparison after Colorado decides whether to
  adopt SnowIn's canonical phase; until then, retain the duplicate retrieval
  path and do not silently change its frozen sign semantics.
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
