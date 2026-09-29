# GitHub issues starter set

## 1. Maintain the normalized scientific API
Keep phase direction, units, grid alignment, missing support, and provenance
explicit in the named xarray retrieval methods.

## 2. Add source adapters only for demonstrated user needs
A new adapter should normalize an authoritative product convention into the
SnowIn pair contract without adding provider access or ancillary-data policy
to the scientific core.

## 3. Keep study workflows composable
Station/date selection, vector loading, DEM acquisition, calibration policy,
validation outputs, and report figures belong in companion tools and
notebooks. Pass prepared, aligned arrays or local inputs to SnowIn.

## 4. Review dependency and API costs together
Add a runtime extra only for a maintained package feature. Keep repository-only
notebook, docs, and development tools in dependency groups.

## 5. Preserve analytical and integration evidence
Add independent equation checks for scientific changes, plus small synthetic
tests for xarray labels, support, missing values, and eager/lazy behavior.
Real products remain opt-in integration evidence.
