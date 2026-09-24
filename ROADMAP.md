# SnowIn roadmap

SnowIn is a pre-release, NISAR-first snow InSAR analysis package. The roadmap
focuses on reusable package behavior; study-specific inputs, station policies,
analysis masks, and result figures belong in downstream applications.

## Implemented foundation

- xarray-native scientific contracts for phase, dSWE, support, provenance, and
  directed temporal edges.
- Named phase-to-dSWE methods with explicit units, wavelength handling, and
  model-specific inputs.
- NISAR GUNW reading, source-phase normalization, product wavelength
  resolution, and local-incidence geometry from DEM and LOS data.
- Reference-phase operations, support composition, metrics, and temporal
  accumulation with explicit missing-data behavior.
- Synthetic and regression tests, property-based invariants, CI coverage,
  formatting, build, and wheel-install checks.

## Current focus

- Review the public scientific API, phase conventions, product metadata, and
  the xarray data model with domain collaborators.
- Exercise the generic synthetic workflow and real-GUNW example in clean
  environments.
- Broaden synthetic coverage for spatial, plotting, and NISAR product variants.
- Keep NISAR DEM/LOS geometry eager by default while evaluating chunked
  execution with documented memory and runtime measurements.

## Next

- Add optional real-product fixtures with public input provenance and no
  downloads or credentials in the required test suite.
- Complete executable documentation for examples that can run without
  external mission products.
- Prepare a conda-forge recipe after a versioned source release and reviewed
  package contents are available.
- Add scientific benchmarks and stricter static typing when their maintenance
  value is clear.

## Later

Broaden sensor adapters only when their product metadata, phase conventions,
geometry, and scientific contracts can be tested. SnowIn is the snow-analysis
layer around mission-specific InSAR processors; it is not a replacement for
general processors such as ISCE or Dolphin.
