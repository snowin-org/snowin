# GitHub issues starter set

## 1. Define SnowIn public API boundaries
**Why:** lock down naming and public-vs-internal rules before migration accelerates.
**Deliverables:** API naming guide, top-level namespace decisions, doc update.

## 2. Implement and document core `phase_to_dswe(...)` methods
**Why:** establish a tested scientific core for the package.
**Deliverables:** method implementations, tests, docs, examples.

## 3. Design normalized GUNW/GSLC reader interfaces
**Why:** create stable SnowIn I/O entry points before importing legacy code.
**Deliverables:** design doc, stub interfaces, example usage.

## 4. Map legacy functions from `nisar_pytools` and `snowsar`
**Why:** migration should be deliberate and traceable.
**Deliverables:** migration matrix with source file, target module, action, owner.

## 5. Set up contributor workflow and CI
**Why:** prevent code sprawl as the team grows.
**Deliverables:** issue templates, CI, CONTRIBUTING.md, code review rules.
