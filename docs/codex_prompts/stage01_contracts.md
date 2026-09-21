# Stage 1 prompt: define scientific and data contracts

Using `docs/codex_prompts/master.md`, execute Stage 1 only after Stage 0 has
been reviewed. Do not implement Stage 2 or later functionality.

## Goal

Define the smallest explicit scientific and data contracts SnowIn needs before
new retrieval architecture is added. This stage should make meaning and
interoperability testable without introducing a new snow algorithm.

## Required work

1. Reinspect the local repository and the Stage 0 checkpoint. Preserve any
   uncommitted work and do not assume remote branches supersede it.
2. Define the normalized xarray representation for retrieval-ready data:
   dimensions, coordinate names and roles, required variables, units,
   attributes, nodata/missing semantics, CRS/grid relationships, and the
   distinction between absent product layers and invalid samples.
3. Define terminology and contracts for phase, pairwise dSWE, cumulative dSWE,
   and absolute SWE. State phase sign, temporal direction, reference/secondary
   ordering, and wavelength/incidence-angle units explicitly.
4. Define how support/provenance will remain distinguishable for product
   validity, geometry, connected components, reference support, temporal paths,
   evaluation data, snow-state evidence, and coherence diagnostics.
5. Define the public/private API boundary using functions over xarray objects.
   Do not introduce custom scene/stack/product classes or an xarray accessor
   without a demonstrated requirement.
6. Add documentation and contract/invariant tests for the decisions. Tests may
   use small synthetic xarray objects and must remain independent of private
   NISAR products.
7. Review whether xarray belongs in the base dependency set or an explicit
   optional boundary based on the contract. Do not add dependencies without a
   concrete need.
8. Update `docs/code_provenance.md` only with sources actually inspected and
   implementation decisions actually made.

## Explicit non-goals

Do not implement a new dSWE equation, NISAR HDF5 adapter, local-incidence
algorithm, reference-phase method, temporal accumulation engine, support
metrics, Colorado integration, or release process. Do not silently change the
existing prototype's numerical behavior to make a contract test pass; record
conflicts as scientific debt and decide them explicitly.

## Validation and checkpoint

Run the smallest complete installed-package test and quality suite relevant to
the changes, including `pytest -q`, `ruff check .`, `ruff format --check .`,
`python -m build`, and `git diff --check` where available. Stop and provide the
full master checkpoint report before proposing Stage 2.
