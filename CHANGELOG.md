# Changelog

## 0.1.0 - unreleased

The first 0.1 release line provides the NumPy/xarray scientific core, named
phase-to-dSWE methods, optional local NISAR GUNW normalization, and optional
local-incidence geometry from caller-prepared DEMs. It also includes reference-
phase operations, directed temporal accumulation, support composition, and
metrics. Product search, downloads, cloud staging, ancillary acquisition,
vector/raster file utilities, and custom reports remain in notebooks, examples,
and companion workflows. xarray plotting is used for routine array plots.

The release line also includes synthetic and regression tests, CI coverage,
wheel-install checks, separate runtime and authoring environments, and
examples for synthetic analysis, real GUNW processing, upstream product search, and
downstream study workflows. dSWE products represent change between radar
epochs, not absolute SWE. Correction layers are exposed and recorded but are
not automatically applied.

SnowIn is not yet published to PyPI or conda-forge. Real-product validation
requires caller-supplied data and remains optional to the fast test suite.
