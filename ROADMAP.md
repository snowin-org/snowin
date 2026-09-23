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
- The controlled 23-edge Colorado comparison reproduces phase lineage,
  reference application, dSWE algebra, support, provenance, and strict
  temporal accumulation. The independent station-row offset reconstruction
  matches Colorado's all-station calculation for all 23 edges; the reviewed
  path offsets remain a distinct downstream policy input.
- The native 23-edge NISAR DEM benchmark is complete. Geometry remains eager
  while phase/product arrays remain Dask-compatible; the measured high-water
  memory is recorded before deciding whether the opt-in chunk-aware prototype
  should become a supported execution mode.
- Notebook 03 now demonstrates controlled versus SnowIn-native Colorado
  comparison without importing Colorado station/date policy into SnowIn.
- Vector-defined analysis-region masks now support GeoPackage, Shapefile,
  GeoJSON, and in-memory geometries with CRS-aware rasterization. The first
  ERB/Taylor basin-matched comparison shows near-identical incidence fields
  over the actual study regions.
- Keep regression evidence reproducible without storing large external GUNW or
  DEM files in the repository.

## Next

- Have collaborators run Notebooks 01–03 and the canonical
  `open_gunw()` → `add_gunw_incidence()` → `compute_dswe()` workflow against
  their environments and products.
- Use the explicit ERB/Taylor region masks for future Colorado residual,
  support, and regional metric comparisons.
- Colorado has decided to adopt SnowIn's canonical `secondary_minus_reference`
  phase, NISAR-modified Copernicus DEM geometry, and product-metadata wavelength
  treatment. Validate this configuration across the controlled 23-edge path,
  keeping Colorado's reviewed station/path offsets as explicit downstream
  inputs unless their policy is separately changed.
- Keep the legacy retrieval available during migration validation. Rewire the
  Colorado workflow to the canonical SnowIn API only after the adopted
  phase/DEM/wavelength path is reviewed against the controlled baseline; then
  decide whether `gunw_to_dswe` remains as compatibility support.
- Add broader synthetic/product robustness coverage for alternate polarization,
  missing layers, product variants, and larger grids.
- Refactor the NISAR adapter only after the scientific boundaries above are
  settled and the current tested behavior can be preserved.
- Publish the source docs site through the repository workflow and create the
  annotated release tag after the phase-lineage gate is closed. The local
  Python 3.12 wheel install, CLI help smoke test, strict docs build, package
  build, and release metadata checks now pass.

## Later

- Broaden supported product adapters, including Sentinel-1, ROSE-L when its
  products become available, and other sensors where their scientific and data
  contracts can be verified. This is a future direction, not active v0.1 work;
  the current implementation remains deliberately NISAR-first.
- Keep the product-adapter boundary focused on converting mission-specific
  inputs into SnowIn's common snow-analysis contract. SnowIn is not intended to
  replace general InSAR processors such as ISCE or Dolphin.
- Add coverage, documentation publishing, and broader Python/platform testing
  when those services and maintenance needs justify the additional process.
- Prepare PyPI/Conda packaging only after the scientific workflow and public API
  are stable and reproducible.

Colorado first-look workflows remain downstream applications. Their frozen
station lists, dates, basin choices, sensitivity analyses, and output policies
must remain in the Colorado repository.
