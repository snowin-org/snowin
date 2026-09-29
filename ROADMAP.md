# SnowIn roadmap

SnowIn is a pre-release, NISAR-first snow InSAR analysis package. The roadmap
focuses on reusable package behavior; study-specific inputs, station policies,
analysis masks, and result figures belong in downstream applications.

## Implemented foundation

- xarray-native scientific contracts for phase, dSWE, support, provenance, and
  directed temporal edges.
- Named phase-to-dSWE methods with explicit units, wavelength handling, and
  model-specific inputs.
- `nisar_pytools`-based ASF search and validated downloads, plus NISAR GUNW
  reading, source-phase normalization, and product wavelength resolution.
- Local-incidence geometry from DEM and GUNW LOS data, with explicit invalid
  support for missing or back-facing terrain. GUNW correction layers are
  available for inspection and retain their source metadata; they are not
  applied automatically.
- Reference-phase operations, support composition, metrics, and temporal
  accumulation with explicit missing-data behavior.
- GUNW layer, incidence-angle, and pairwise dSWE plots.
- Synthetic and regression tests, property-based invariants, CI coverage,
  formatting, build, and wheel-install checks.

## Current focus

- Have domain collaborators review the public scientific API, phase
  conventions, product metadata, xarray data model, and NISAR search-to-dSWE
  workflow.
- Keep the base package focused on retrieval science over normalized xarray
  pairs; keep NISAR reading and geometry as opt-in integrations.
- Keep notebooks in this repository as synthetic core examples, integration
  guides, and downstream study workflows. Keep their data access and study
  policies out of SnowIn's runtime API.
- Keep NISAR DEM/LOS geometry eager by default while evaluating chunked
  execution with documented memory and runtime measurements.

## Next

- Add optional real-product fixtures with public input provenance and no
  downloads or credentials in the required test suite.
- Finish the 0.1 review by checking installation, public imports, package
  contents, and documented scientific limitations.
- Publish a versioned source release and prepare a conda-forge recipe after
  external review and release metadata checks. The recipe's default
  requirements should match the NumPy/xarray core, not the full contributor
  environment.
- Add scientific benchmarks and stricter static typing when their maintenance
  value is clear.

## Later

Broaden sensor adapters only when their product metadata, phase conventions,
geometry, and scientific contracts can be tested. SnowIn is the snow-analysis
layer around mission-specific InSAR processors; it is not a replacement for
general processors such as ISCE or Dolphin.
