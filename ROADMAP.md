# SnowIn roadmap

SnowIn is a pre-release scientific package. This roadmap records the current
direction without making study-specific Colorado configuration part of the
general package contract.

## Implemented foundations

- xarray Dataset contracts and explicit phase, time, unit, support, and
  provenance conventions.
- Canonical xarray-native `compute_dswe` using the reviewed Leinss relation.
- NISAR GUNW reading, source-phase normalization, product wavelength
  resolution, lazy phase handling, and COP30/local-DEM incidence geometry.
- Reference-phase methods, directed temporal accumulation, named support
  layers, support summaries, and reusable metrics.
- GUNW diagnostics, plotting, CLI scaffolding, and a downstream Colorado
  integration boundary.

## Now

- Resolve the documented COP30 orthometric versus GUNW ellipsoidal vertical
  datum limitation with product-backed evidence.
- Continue real-product geometry characterization and decide whether geometry
  should become chunk-aware/Dask-compatible.
- Keep regression evidence reproducible without storing large external GUNW or
  DEM files in the repository.

## Next

- Characterize reference-phase inputs and support rules using Colorado as
  downstream evidence, without importing its station/date policy.
- Expand optional-dependency and installation checks, including wheel
  installation and explicit CLI smoke coverage.
- Add release-oriented metadata such as `CITATION.cff` before the first tagged
  release.

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
