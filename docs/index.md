# SnowIn

SnowIn estimates changes in snow water equivalent (dSWE) from interferometric
phase. The initial 0.1 release focuses on NISAR GUNW products and provides
phase normalization, local-incidence geometry, named dSWE methods, and
xarray-based reference, correction, support, and temporal operations.

Start with the [data model](data_model.md),
[scientific conventions](scientific_conventions.md),
[DEM vertical-datum notes](vertical_datums.md), and
[API policy](api_policy.md). The [development guide](development.md) covers
installation, environments, and quality checks. The [scientific testing
policy](testing.md) explains how SnowIn protects equations, signs, xarray
structure, failure behavior, and eager/lazy equivalence.

The [reviewer handoff](reviewer_handoff.md) gives the review sequence, and the
[feedback template](reviewer_feedback_template.md) records results and
reproducible issues. The notebook collection includes a synthetic core example
(`01`), a local-product GUNW workflow (`02`), and the NISAR search-to-dSWE
workflow (`06`). Notebooks `03` and `04` are downstream study templates. The
[NIVAL research notebook](https://github.com/snowin-org/snowin/blob/development/notebooks/05_nival_nisar_comparison.ipynb)
remains development-only and is not included in the 0.1 release on `main`.
