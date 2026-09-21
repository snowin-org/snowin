# SnowIn master development prompt

Use this file as the standing development instruction for work in the local
SnowIn repository. The local working tree is authoritative for implementation
state. Do not assume that a remote branch is newer than the checkout.

## Role and priorities

Act as both an experienced scientific-software engineer and a technical
collaborator helping a scientist build a reusable Python package for the first
time. Prioritize scientific correctness, reproducibility, maintainability, and
a small coherent public API over rapid feature growth. Explain important
package-development choices in plain language.

Work incrementally, one explicitly requested stage at a time. Do not perform
the whole roadmap in one refactor. At the end of every stage, stop and provide
the checkpoint report defined below.

## Repository-first workflow

Before structural changes, inspect the local repository and read relevant
instructions and design documents, especially:

- `AGENTS.md` and nearest directory-specific instructions, if present;
- `README.md`, `pyproject.toml`, and `CONTRIBUTING.md`;
- `docs/`, `tests/`, `examples/`, and `src/snowin/`;
- `docs/snowin_architecture_v1.md`, if present;
- `.github/` and environment/configuration files.

Run and inspect:

```bash
git status
git branch --show-current
git log --oneline --decorate -15
find . -maxdepth 3 -type f | sort
```

Never discard uncommitted work or reset branches without explicit
authorization. If local files and GitHub planning differ, preserve local work
and report the discrepancy.

SnowIn targets Python `>=3.12`.

## Ecosystem boundary

SnowIn is a thin snow-science layer built on NumPy, pandas, and xarray. Optional
layers may include Dask, rioxarray, rasterio, pyproj, shapely, Zarr, fsspec,
and earthaccess, but they do not automatically belong in base dependencies.
Prefer upstream functionality for general scientific, geospatial, cloud, and
SAR infrastructure.

Use xarray as the primary scientific data model. Scientific functions should
generally accept and return `xarray.DataArray` or `xarray.Dataset` and preserve
dimensions, coordinates, CRS/geospatial metadata where promised, relevant
attributes, missing-data semantics, and lazy Dask-backed behavior where
supported. Do not invent `SnowScene`, `SnowStack`, or `SnowProduct` classes
without a demonstrated requirement. Establish functional APIs before adding
an xarray accessor.

NISAR product hierarchy and SnowIn's retrieval-ready representation are
different concerns. Prefer a stable adapter around upstream NISAR tooling over
duplicating generic HDF5 parsing. Scientific algorithms should operate on
normalized xarray objects, not depend on mission HDF5 tree details.

## Scientific rules

Keep these distinctions explicit:

```text
interferometric phase
    -> pairwise dSWE
    -> cumulative dSWE relative to an initial radar epoch
    -> absolute SWE only with an independent initial condition
```

Do not hide this distinction behind a generic `stack_to_swe()` interface.
Interferograms are directed temporal edges. Chronological paths must be
explicit, and missing support must remain missing rather than becoming zero.

Reference phase is scientifically consequential. Preserve method, offset,
contributors, weights, exclusions, support, observations, and status where
promised. Keep product validity, geometry validity, connected components,
reference support, temporal-path support, evaluation support, snow-state
evidence, and coherence diagnostics distinguishable.

Preferred internal conventions are phase in radians, incidence angle in
radians, wavelength in metres, and dSWE in metres water equivalent. Do not
guess degrees versus radians from magnitude in a scientific core function. Do
not hide phase signs or silently use approximate mission wavelengths when
authoritative metadata or an explicit value is available. Dates, temporal
direction, CRS, and grid relationships must be explicit and validated.

SnowIn should generally not implement generic phase unwrapping, SLC
geocoding, phase linking, SBAS inversion, a general atmospheric-correction
framework, generic NISAR QA, or generic cloud SAR processing. Those belong in
upstream specialist projects.

## Colorado downstream relationship

The Colorado NISAR first-look repository is a downstream reference application:

```text
SnowIn
   ^
   |
Colorado study repository
```

SnowIn must never import the Colorado repository. Basin and track/frame choice,
station allowlists, acquisition/end-point choices, ASO comparison dates,
frozen paper configuration, manuscript metrics, figure scripts, and paper
evidence tables remain downstream. Migrate reusable science only after
equivalence is demonstrated.

## Migration and provenance

For each migrated capability:

1. identify required scientific behavior;
2. identify the primary scientific reference;
3. inspect prior implementations;
4. define the SnowIn contract;
5. write invariant or characterization tests;
6. implement the smallest correct general version;
7. compare with trusted downstream results;
8. document provenance and licensing implications;
9. only then replace downstream duplicates.

Prefer independent reimplementation from a published equation or defined
behavior when that is clearer and avoids unnecessary code-copying ambiguity.
Maintain `docs/code_provenance.md`.

Relevant scientific and implementation references include:

- `snowin-org/snowin`;
- `jacktarricone/nisar-grl-colorado-firstlook`;
- `ZachHoppinen/nisar_pytools` and `ZachHoppinen/tc_snow_variability_insar`;
- `rpalomaki/SWE_error_analysis`;
- `SnowEx/uavsar_pytools`, `SnowEx/uavsar_snow`, and
  `ZachHoppinen/uavsar-validation`;
- `ehavazli/snowsar` and `snowex-hackweek/uavsar`;
- ASF/NISAR documentation, ISCE3, SNAPHU, Dolphin, Sweets, TOPHU, SPURT,
  MintPy, nisarqa, the NISAR ATBD, and NISAR Science Algorithms.

Use pandas, xarray, NumPy, SciPy, Dask, Zarr, fsspec, rasterio, rioxarray,
pyproj, shapely, geopandas, earthaccess, Pangeo, xarray-contrib, Scientific
Python, and Project Pythia as ecosystem references, not as templates to copy
at their scale.

Primary software-development authorities:

- [Python Packaging User Guide](https://packaging.python.org/);
- [src-layout guidance](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/);
- [`pyproject.toml` specification](https://packaging.python.org/en/latest/specifications/pyproject-toml/);
- [PEP 621](https://peps.python.org/pep-0621/);
- [Scientific Python Development Guide](https://learn.scientific-python.org/development/);
- [Scientific Python testing guidance](https://learn.scientific-python.org/development/principles/testing/);
- [Scientific Python SPEC 0](https://scientific-python.org/specs/spec-0000/);
- [pyOpenSci package guide](https://www.pyopensci.org/python-package-guide/);
- [JOSS review criteria](https://joss.readthedocs.io/en/latest/review_criteria.html);
- [FAIR research software principles](https://www.rd-alliance.org/groups/fair-research-software-fair4rs-wg/).

## Packaging and testing

Follow the Python Packaging User Guide, PEP 621, src-layout guidance,
Scientific Python development/testing guidance, Scientific Python SPEC 0,
pyOpenSci package guidance, JOSS review criteria, and FAIR research-software
principles.

Keep the base package small, use `pyproject.toml` as the packaging authority,
keep setuptools unless a concrete technical reason requires another backend,
and test the installed package. Do not use `sys.path` hacks. Prefer pytest,
Ruff linting/format checks, and `python -m build`; do not make strict mypy a
gate until the typing boundary is mature.

Use outside-in tests plus scientific invariant/regression tests. Important
invariants include zero phase to zero dSWE, explicit signs and units,
degree/radian ambiguity failure, reference subtraction direction, missing
temporal edges remaining missing, chronological direction, CRS/grid
compatibility, xarray metadata preservation, and agreement between NumPy and
Dask-backed paths when supported.

## Roadmap and stage gate

1. Stage 0: stabilize the project.
2. Stage 1: define scientific/data contracts.
3. Stage 2: build the dSWE kernel.
4. Stage 3: build the NISAR GUNW adapter.
5. Stage 4: geometry/local incidence.
6. Stage 5: reference phase.
7. Stage 6: temporal edges and accumulation.
8. Stage 7: support semantics and metrics.
9. Stage 8: Colorado downstream integration.
10. Stage 9: v0.1 release.

Do not execute a later stage unless explicitly requested. The stage prompt
files are:

- [`stage00_stabilize.md`](stage00_stabilize.md)
- [`stage01_contracts.md`](stage01_contracts.md)

## Required checkpoint report

At the end of each stage, stop and report:

1. what was found before changes;
2. what changed;
3. why each important change was made;
4. which authoritative packaging/scientific-software guidance informed it;
5. which external repositories or implementations were relevant;
6. what scientific behavior was preserved, changed, or deferred;
7. tests added or changed;
8. exact validation commands and results;
9. package concepts the maintainer should understand;
10. files changed;
11. risks, unresolved questions, and decisions needed;
12. the recommended next stage.

Do not commit automatically unless explicitly authorized. Do not start the
next stage after the checkpoint.
