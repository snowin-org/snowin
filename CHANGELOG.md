# Changelog

## 0.1.0 - unreleased

The first 0.1 release line provides xarray-native scientific contracts and
named phase-to-dSWE methods; NISAR GUNW phase normalization and product
metadata; `nisar_pytools`-based ASF search and validated downloads; DEM/LOS
local-incidence geometry with explicit geometry support; GUNW correction
layers for inspection; reference-phase operations, directed temporal
accumulation, quality/support layers, metrics, and diagnostic plots.

The release line also includes synthetic and regression tests, CI coverage,
wheel-install checks, separate runtime and authoring environments, and
examples for synthetic analysis, real GUNW processing, product search, and
downstream study workflows. dSWE products represent change between radar
epochs, not absolute SWE. Correction layers are exposed and recorded but are
not automatically applied.

SnowIn is not yet published to PyPI or conda-forge. Real-product validation
requires caller-supplied data and remains optional to the fast test suite.
