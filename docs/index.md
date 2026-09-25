# SnowIn

SnowIn is a snow-focused SAR/InSAR Python package, initially NISAR-first. It
turns phase-based snow retrieval inputs into analysis-ready xarray objects
while keeping units, coordinates, support, and scientific provenance explicit.

SnowIn is pre-release software. Start with the [data model](data_model.md),
[scientific conventions](scientific_conventions.md),
[DEM vertical-datum notes](vertical_datums.md), and
[API policy](api_policy.md). The [development guide](development.md) covers
installation, environments, and quality checks. The [scientific testing
policy](testing.md) explains how SnowIn protects equations, signs, xarray
structure, failure behavior, and eager/lazy equivalence.

The [reviewer handoff](reviewer_handoff.md) gives the focused package review
sequence. The [review feedback template](reviewer_feedback_template.md) records
results and reproducible issues. The repository's `notebooks/` directory
contains a synthetic example and a real-GUNW example.
