# Migrating to delivered NISAR phase (schema 0.2)

Canonical phase is `phi_reference - phi_secondary` in radians. dSWE is
`SWE_secondary - SWE_reference` in metres, with the secondary acquisition later
than reference. Schema 0.2 is a breaking scientific contract change within the
unreleased 0.1.0 API; public function names are retained. Pin the reviewed commit,
not just the package version. The old reader negated delivered NISAR phase; the
new reader preserves it. All three retrieval equations keep their coefficients.

## Fresh ingestion and removal of compensation

```python
from snowin import compute_leinss_dswe, reference_phase
from snowin.io import open_gunw, add_gunw_incidence

with open_gunw("product.h5", chunks="auto") as pair:
    # pair.phase equals delivered unwrappedPhase; no -pair.phase inversion.
    assert pair.attrs["phase_transform"] == "identity"
    add_gunw_incidence(pair, "product.h5", dem="prepared_dem.tif",
                       dem_source="nisar_cop30")
    # Example only: caller establishes an offset in the canonical convention.
    referenced = reference_phase(pair, method="manual_offset", offset_rad=0.1)
    dswe = compute_leinss_dswe(referenced.phase_referenced,
                              pair.incidence_angle,
                              wavelength_m=pair.attrs["wavelength_m"])
    # Positive referenced snow-related phase now gives positive dSWE.
    # OLD compensated workflow: dswe = -compute_leinss_dswe(...)
    # NEW workflow: use dswe directly; remove that compensating negation.
    dswe = dswe.compute()  # finish file-backed work before closing the pair
```

A scalar demonstration independent of the measured phase is the README quick
start: +1.2 rad gives positive dSWE. Snow attribution still requires explicit
corrections, reference handling, and support; positive measured phase alone
is not proof of accumulation. Correction layers retain their delivered values
and native grids; their signs and application remain caller-owned.

## Explicit conversion of old normalized phase

Prefer fresh ingestion. Otherwise verify the old numeric phase convention from
recorded processing provenance. An unmodified schema 0.1 normalized phase is
secondary-minus-reference. Convert its phase explicitly at the adapter boundary:

```python
from snowin.io import normalize_gunw_pair

assert old.attrs["snowin_schema_version"] == "0.1"
assert old.attrs["phase_difference_definition"] == "secondary_minus_reference"
new = normalize_gunw_pair(
    old.phase, old.incidence_angle,
    source_phase_difference_definition="secondary_minus_reference",
    wavelength_m=old.attrs["wavelength_m"],
    reference_time=old.attrs["reference_time"],
    secondary_time=old.attrs["secondary_time"],
    spatial_ref=old.spatial_ref,
    source_metadata={"migration_origin_schema": "0.1",
                     "migration_history": "explicit inversion of old normalized phase"},
)
# new.phase = -old.phase, schema 0.2; dates and temporal direction are unchanged.
# Re-estimate the reference and recompute dSWE from this phase.
```

`source_phase_difference_definition` describes the **current numeric input**,
not the original product before an earlier transform. The adapter rejects a
conflict with the input's declared phase definition. Re-normalizing canonical
phase must declare reference-minus-secondary and uses identity, preventing a
second inversion. Do not relabel old values. Known schema 0.1 pairs are rejected
by referencing and accumulation; phase carrying schema 0.1 or the old convention
is rejected by retrieval. Bare arrays without source provenance cannot reveal
past processing: callers must supply an accurate declaration.

Observed/expected reference contributors and reference-offset arrays now require
`phase_difference_definition="reference_minus_secondary"` and radians. Old
contributor phase and offsets need the same explicit conversion as phase, or
re-estimation. Residual, weighted mean, and subtraction equations are unchanged.

Never automatically negate previously saved dSWE. Some workflows already applied
compensating negation; others changed phase or reference offsets earlier. Audit
reader revision, phase transform, retrieval, referencing, and subsequent signs
before deciding whether to recompute. Keep the original artifact and migration
history. No automatic migration of saved dSWE is provided. Chronological edges
and cumulative changes retain secondary-minus-reference SWE semantics.
