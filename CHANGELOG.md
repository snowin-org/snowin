# Changelog

## 0.1.0 (unreleased)

Initial release: xarray-based phase-to-dSWE methods, explicit reference and
support operations, directed temporal accumulation, and optional NISAR GUNW
phase conversion and local-incidence geometry. Pair Datasets use layout
version `0.2`.

### Breaking scientific contract: delivered NISAR phase

Canonical phase is now `phi_reference - phi_secondary`, preserving delivered
NISAR GUNW values with identity provenance. dSWE remains
`SWE_secondary - SWE_reference` along chronological reference-to-secondary
edges. All three positive phase-to-dSWE equations retain their coefficients.
Schema 0.2 and explicit dSWE metadata distinguish this revision from old
normalized products. Legacy phase requires an explicit adapter conversion or
fresh ingestion; referencing contributors and offsets require canonical phase
metadata. See [migration](docs/phase_migration.md). Remove compensating dSWE
negation used with the old reader. Never automatically invert saved dSWE;
first audit its processing provenance. Public function names and the unreleased
package version 0.1.0 remain unchanged; downstream environments must pin a
reviewed revision.
