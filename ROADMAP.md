# SnowIn roadmap

SnowIn 0.1 is a small xarray-native snow-InSAR science package with an
optional NISAR GUNW adapter and local-incidence geometry.

## Implemented

- Named Leinss, Guneriussen, and Oveisgharan pairwise dSWE equations.
- NISAR GUNW phase normalization and authoritative wavelength extraction.
- Prepared-DEM local incidence with explicit CRS, vertical-datum, LOS, and
  invalid-support handling.
- Contributor-based xarray reference estimation and application.
- Separate named support layers and explicit support composition.
- Chronological, contiguous dSWE path accumulation with missing-support
  propagation.

## 0.1 release work

- Review scientific assumptions, product phase lineage, metadata, and the
  documented public API.
- Validate the package metadata, optional features, wheel contents, base
  installation, and strict documentation build.
- Publish a tagged source release after scientific and API review.

## Outside the package

Search, downloads, DEM acquisition, GIS preparation, plotting, generic
evaluation metrics, correction application, station data, and study-specific
validation remain caller-owned. Additional sensor adapters will be considered
only with authoritative metadata and a testable scientific contract.
