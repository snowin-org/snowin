# Code and science provenance

Every reusable scientific capability added to SnowIn should have a record here
or in a linked, versioned provenance record before it replaces downstream
study code. The record should answer:

| Field | Required information |
| --- | --- |
| Capability | SnowIn module and public function |
| Scientific source | Paper, ATBD, equation, or authoritative documentation |
| Repositories inspected | Relevant prior implementations and versions/commits |
| Implementation relationship | Copied, adapted, independently reimplemented, or wrapper |
| License implications | Source license and any notice/attribution requirements |
| Validation evidence | Invariants, characterization cases, regression products, and tolerances |
| Status | Prototype, reviewed, validated, or deferred |

Stage 0 establishes the framework only. The existing prototype capabilities
still require capability-specific records before they are treated as validated
SnowIn science. In particular, the dSWE formulations, GUNW product adapter,
reference-phase behavior, correction signs, and raster-grid assumptions need
primary scientific references and regression evidence in their respective
stages.

The migration rule is: define the scientific behavior, inspect the primary
reference and relevant upstream implementations, write invariant or
characterization tests, implement the smallest general version, record
provenance, and only then replace duplicate downstream code. Study-specific
basin choices, dates, station lists, paper metrics, and figure configuration
remain downstream.

## Stage 1 normalized-contract proposal

| Field | Record |
| --- | --- |
| Capability | Pairwise retrieval-ready xarray Dataset contract and scientific terminology. |
| Scientific source | `docs/snowin_architecture_v1.md`, `docs/data_model.md`, and `docs/scientific_conventions.md`, including the adopted `secondary_minus_reference` project contract; no production dSWE equation was changed. |
| Repositories inspected | Current SnowIn prototype modules and tests at the Stage 1 baseline; no external implementation was copied. |
| Implementation relationship | Independently specified schema and synthetic contract tests. |
| License implications | No third-party code copied or adapted. |
| Validation evidence | `tests/test_contracts.py` synthetic xarray objects and existing prototype characterization tests. |
| Status | Stage 1 contract finalized; GUNW source-sign transformation and Colorado sign-lineage regression audit are deferred to later stages. |
