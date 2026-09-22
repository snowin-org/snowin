# SnowIn architecture and development plan v1

Status: design source of truth for the next SnowIn development cycle.

This document records the architecture decisions and development sequence established after reviewing the current SnowIn prototype, the Colorado NISAR first-look repository, relevant snow/InSAR repositories, NISAR/ISCE tooling, and the broader PyData/Pangeo scientific Python ecosystem.

SnowIn should be developed incrementally. The goal is a small, scientifically defensible package that grows only as real snow-InSAR workflows require new capabilities.

## 1. Project identity

SnowIn is a reusable scientific Python package for snow-focused SAR and InSAR analysis.

It is not a manuscript repository and should not encode study-specific station choices, basin choices, figure layouts, paper endpoint dates, or frozen publication configurations.

It is also not intended to become:

- a general SAR processor;
- a replacement for ISCE3;
- a replacement for MintPy;
- a phase-unwrapping library;
- a general NISAR QA package;
- a generic cloud-storage framework;
- a manuscript-figure framework;
- an all-sensor Earth-observation framework.

SnowIn should provide reusable scientific machinery needed to interpret SAR/InSAR observations of seasonal snow.

## 2. Relationship to study repositories

Study repositories such as the Colorado NISAR first-look repository should consume SnowIn as a downstream dependency.

Target dependency direction:

```text
SnowIn
  ^
  |
  +-- study repositories
      +-- frozen study configuration
      +-- study-specific inputs
      +-- paper metrics
      +-- paper figures
      +-- manuscript evidence
```

SnowIn must never import a study repository.

The Colorado repository should become the first major downstream reference application and regression case for SnowIn.

## 3. Scientific Python foundation

SnowIn should sit above the existing PyData/Pangeo stack rather than recreate it.

Conceptually:

```text
NumPy + pandas
       |
     xarray
       |
  SnowIn science
       |
optional scale/access through Dask, Zarr, fsspec, Earthdata, etc.
```

The preferred internal scientific data model is xarray.

Scientific functions should generally accept and return `xarray.DataArray` or `xarray.Dataset` objects while preserving:

- dimension names;
- coordinates;
- CRS and geospatial metadata where relevant;
- scientific attributes;
- missing-data semantics;
- lazy-array behavior when inputs are Dask-backed.

SnowIn should not require Dask merely to be Dask-compatible.

## 4. NISAR product boundary

NISAR product hierarchy and snow-science representation are different concerns.

A preferred boundary is:

```text
NISAR HDF5
    |
upstream product reader / adapter
    |
xarray DataTree or product-specific representation
    |
SnowIn normalization adapter
    |
retrieval-ready xarray Dataset
    |
SnowIn scientific algorithms
```

`nisar_pytools` is currently the most relevant candidate upstream implementation for lazy NISAR HDF5-to-DataTree handling, GUNW/GSLC extraction, product search, metadata handling, validation, and local-incidence utilities.

SnowIn should evaluate wrapping or depending on this functionality rather than maintain duplicate NISAR-reader logic.

ASF/NISAR product documentation remains authoritative for product semantics.

## 5. Do not invent custom object hierarchies prematurely

Do not introduce custom `SnowScene`, `SnowStack`, `SnowProduct`, or similar classes until a demonstrated use case requires behavior that xarray does not already provide cleanly.

Begin with explicit functions operating on xarray objects.

An xarray accessor such as `ds.snowin...` may be considered later only after the functional API is stable.

## 6. Scientific distinctions that must be explicit

### 6.1 Pairwise dSWE is not absolute SWE

SnowIn must distinguish:

```text
interferometric phase
    -> pairwise dSWE
    -> cumulative dSWE relative to an initial radar epoch
    -> absolute SWE only if an independent initial condition is supplied
```

Preferred conceptual API:

```python
compute_dswe(...)
accumulate_dswe(...)
initialize_swe(...)
```

Do not use a generic `stack_to_swe()` abstraction that hides this distinction.

### 6.2 Interferograms are directed temporal edges

An interferometric observation represents a directed interval between acquisitions.

Cumulative change requires a valid chronological path.

Missing pairwise support must remain missing. It must never be silently interpreted as zero accumulation or zero ablation.

Temporal path semantics should therefore become first-class package behavior.

### 6.3 Reference phase requires provenance

A reference-phase calculation is scientifically consequential and should not be represented only by a scalar offset.

The eventual result should preserve enough information to identify:

- reference method;
- offset;
- contributing observations/stations/pixels;
- weights;
- rejected contributors;
- reference support;
- relevant status/diagnostic information.

This is required because calibration/reference observations affect later claims of validation independence.

### 6.4 Support is not a generic quality mask

Do not collapse the following into one implicit Boolean quality mask:

- product-sample validity;
- valid geometry;
- connected-component identity;
- reference availability;
- temporal-path completeness;
- evaluation-data support;
- physical snow-state evidence;
- coherence diagnostics.

These concepts should remain distinguishable so downstream science can state exactly which support policy was applied.

## 7. Scientific conventions

Scientific conventions must be explicit and documented.

Initial internal conventions should favor:

- phase: radians;
- incidence angle: radians in scientific kernels;
- wavelength: metres;
- dSWE: metres water equivalent internally;
- dates: explicit acquisition ordering;
- coordinates/CRS: preserved and validated.

Do not infer degrees versus radians from value magnitude in scientific core functions.

Do not hide phase sign conventions.

Do not hard-code approximate mission wavelength when product metadata or an explicit scientifically justified wavelength is available.

Unit-aware extensions such as pint-xarray may be evaluated later, but explicit contracts come first.

## 8. Initial package structure

Start small. Do not create empty modules for future ambitions.

A reasonable early target is:

```text
snowin/
├── .github/
│   └── workflows/
├── docs/
│   ├── architecture.md
│   ├── data_model.md
│   ├── scientific_conventions.md
│   ├── development.md
│   └── code_provenance.md
├── examples/
├── src/
│   └── snowin/
│       ├── __init__.py
│       ├── dswe.py
│       ├── geometry.py
│       ├── reference.py
│       ├── support.py
│       ├── temporal.py
│       ├── metrics.py
│       └── io/
│           ├── __init__.py
│           └── nisar.py
├── tests/
│   ├── unit/
│   ├── invariants/
│   └── integration/
├── CHANGELOG.md
├── CITATION.cff
├── CONTRIBUTING.md
├── LICENSE
├── README.md
└── pyproject.toml
```

This tree is a direction, not a requirement to create every path immediately.

## 9. Python version

SnowIn will target Python 3.12 and newer for the next development cycle.

Update package metadata and development tooling accordingly:

```toml
requires-python = ">=3.12"
```

Rationale:

- SnowIn is a new package, so there is no installed-user compatibility burden yet.
- A narrower support matrix reduces maintenance and CI burden.
- Python 3.12 remains within the Scientific Python SPEC 0 support window as of this design update.
- Dependency compatibility must still be verified before release.

The decision should be revisited under a documented dependency-support policy rather than changed ad hoc.

## 10. Packaging principles

Follow established Python packaging standards rather than inventing project-specific packaging conventions.

Use:

- `src/` layout;
- `pyproject.toml` as the packaging/configuration authority;
- PEP 621-style project metadata;
- editable installs for development;
- tests against the installed package;
- a simple build backend unless a demonstrated technical reason requires something more complex.

The current setuptools approach is sufficient for a small pure-Python package and should not be changed only because larger ecosystem packages use different build systems.

## 11. Dependency philosophy

Keep the base installation small.

Add dependencies only when they are required by stable core functionality.

Potential future extras may include:

- NISAR/product I/O;
- geospatial functionality;
- data access;
- plotting;
- development/testing.

Compatibility with Pangeo does not mean depending on the entire Pangeo ecosystem.

Prefer upstream tools for capabilities they already own.

## 12. Code provenance

SnowIn will draw scientific ideas and candidate implementations from multiple repositories.

Every migrated scientific capability should record:

- scientific source/reference;
- source repository or repositories inspected;
- exact implementation adopted or reimplemented;
- licensing implications;
- SnowIn module/function;
- validation/regression evidence.

Prefer reimplementation from authoritative equations or documented behavior when that avoids unnecessary code-copying and licensing ambiguity.

## 13. Migration rule

Do not copy an old repository into SnowIn.

For each capability:

1. identify the scientific behavior required;
2. identify the authoritative scientific reference;
3. inspect relevant prior implementations;
4. define the SnowIn public contract;
5. write characterization or scientific-invariant tests;
6. implement the smallest correct version;
7. compare against trusted study outputs;
8. document provenance;
9. only then replace duplicate downstream implementations.

A method belongs in SnowIn when it represents reusable scientific behavior rather than a decision specific to one study and can be tested independently of that study.

## 14. Testing strategy

Follow Scientific Python's outside-in testing logic while adding scientific regression checks.

Test classes:

1. public-interface tests;
2. project-level integration tests;
3. unit tests;
4. scientific invariant/regression tests.

High-priority scientific invariants include:

- zero phase gives zero dSWE;
- phase-sign convention is explicit;
- wavelength and unit handling are explicit;
- degree/radian ambiguity is rejected;
- reference subtraction direction is tested;
- missing temporal edge remains missing;
- chronological edge direction is enforced;
- CRS/grid incompatibility fails clearly;
- xarray coordinates and metadata are preserved where promised;
- NumPy-backed and Dask-backed inputs produce equivalent numerical results when both are supported.

Coverage percentage is secondary to scientific behavior and API correctness.

## 15. v0.1 scope

The first release should prove one scientifically coherent path:

```text
delivered NISAR GUNW
    -> normalized retrieval-ready xarray Dataset
    -> explicit reference phase
    -> pairwise dSWE
    -> strict chronological accumulation
    -> support/provenance
    -> simple evaluation metrics
```

Do not require v0.1 to own:

- GSLC-to-interferogram processing;
- phase linking;
- phase unwrapping;
- generic SBAS inversion;
- MintPy integration;
- broad multi-sensor support;
- arbitrary atmospheric-correction frameworks;
- cloud virtualization;
- absolute SWE initialization;
- interactive dashboards;
- manuscript figure generation.

These are later capabilities and should be added only when a demonstrated workflow requires them.

## 16. Development stages

### Stage 0: stabilize the project

Goals:

- inspect current local state before changing architecture;
- clean generated/cache files from version control;
- update Python minimum to 3.12;
- verify editable installation;
- verify package imports only from the installed package;
- establish CI;
- establish formatting/lint/test commands;
- update package metadata;
- create/update architecture, data-model, scientific-conventions, development, and provenance documentation;
- do not redesign scientific algorithms yet.

### Stage 1: define scientific contracts

Goals:

- define normalized xarray schema;
- define dimensions, coordinates, required variables, metadata, units, nodata, CRS behavior;
- define terminology for phase, pairwise dSWE, cumulative dSWE, and absolute SWE;
- define sign and temporal-direction conventions;
- define public/private API boundaries.

No major new capability should be added until these contracts are reviewed.

### Stage 2: build the dSWE kernel

Goals:

- implement one well-supported phase-to-dSWE method needed by the Colorado workflow;
- ground the implementation in the primary scientific reference;
- remove silent unit/angle inference;
- make wavelength/sign behavior explicit;
- add unit and scientific-invariant tests;
- regression-test against the Colorado implementation.

### Stage 3: build the NISAR adapter

Goals:

- evaluate `nisar_pytools` as the upstream product reader;
- normalize a delivered GUNW into the Stage-1 SnowIn schema;
- preserve lazy loading where possible;
- preserve relevant product metadata and provenance;
- avoid duplicating generic NISAR HDF5 parsing unless required.

Stage 3 implementation decisions:

- `snowin.io.open_gunw()` is a thin xarray/h5netcdf boundary after evaluating
  `nisar_pytools`; `nisar_pytools` is not a SnowIn runtime dependency.
- The default retrieval incidence is COP30 DEM-derived local incidence from
  the GUNW radar-grid LOS cube. The product ellipsoid-normal `incidenceAngle`
  is an explicit opt-in compatibility mode, never a silent substitute.
- If no DEM is supplied, `open_gunw()` downloads and caches the public COP30
  tiles covering the GUNW phase-grid footprint; callers may provide a local
  DEM or cache directory to control network and storage behavior.
- GUNW center-frequency metadata is converted to wavelength with `c / f`;
  `open_gunw()` resolves this automatically, while an explicit `wavelength_m`
  override is available for documented special cases. No mission wavelength
  default is embedded in the generic kernel.
- The adapter rejects missing or unknown source phase conventions and records
  the NISAR-to-SnowIn sign transformation in the normalized Dataset.

### Stage 4: geometry

Goals:

- define and implement local-incidence handling required by dSWE retrieval;
- validate CRS, grid, units, and source semantics;
- compare candidate implementation with Colorado and `nisar_pytools`;
- add synthetic and regression tests.

### Stage 5: reference phase

Goals:

- implement an explicit reference interface;
- make reference provenance first-class;
- first production reference method should be the one required by the Colorado study;
- retain diagnostics needed to understand contributors, weights, exclusions, and support.

### Stage 6: temporal accumulation

Goals:

- model interferometric pairs as directed temporal edges;
- validate chronological paths;
- accumulate pairwise dSWE only across complete supported paths;
- propagate missing support instead of inserting zero;
- add edge/path invariant tests.

### Stage 7: support and metrics

Goals:

- separate product validity, geometry, reference support, connected components, temporal support, and evaluation support;
- provide simple reusable metrics without embedding paper-specific evaluation choices;
- avoid universal coherence thresholds or dominant-component assumptions.

### Stage 8: Colorado integration

Goals:

- make the Colorado first-look repository import SnowIn for migrated stable capabilities;
- reproduce frozen Colorado results within declared tolerances;
- remove downstream duplicate implementations only after equivalence is demonstrated;
- use this study as an integration/regression test, not as hidden package configuration.

### Stage 9: first public release

Goals:

- complete user documentation;
- provide small real examples;
- add citation metadata;
- establish changelog/versioning/release process;
- run installation/build/test checks in a clean environment;
- prepare a defensible v0.1 release.

## 17. Required developer communication

This project is also a learning process for maintainers who are new to Python package development.

After each meaningful development unit, report:

- what changed;
- why the change belongs in a package;
- how it differs from study-repository code;
- which authoritative guidance informed the decision;
- which source repositories were inspected;
- what scientific behavior was preserved or changed;
- what tests were added;
- what commands were run;
- what the maintainer should understand about the packaging/software concept involved;
- what should happen next.

Do not perform large opaque multi-stage rewrites.

Stop at meaningful review checkpoints.

## 18. Repository review lessons

### Colorado NISAR first-look repository

Primary role:

- strongest source of currently exercised snow-specific scientific behavior;
- candidate source for dSWE, incidence, reference, support, temporal, and metric logic;
- first downstream regression case.

Do not migrate study-specific choices such as station lists, basin/frame/date selection, paper figure code, or frozen publication configuration.

### nisar_pytools

Primary role:

- strongest candidate upstream NISAR data/product layer;
- lazy HDF5 -> xarray DataTree handling;
- GUNW/GSLC extraction;
- metadata and validation;
- search/access;
- local-incidence utilities.

SnowIn should prefer a stable adapter boundary rather than make nisar_pytools internals part of SnowIn's public API.

### uavsar_pytools / uavsar_snow / uavsar-validation

Primary role:

- historical snow-retrieval implementations;
- UAVSAR workflow and incidence-angle lessons;
- evidence of useful snow-science decomposition.

Use as scientific/implementation references, not architecture templates.

### SWE_error_analysis

Primary role:

- non-snow error mechanisms and candidate equations;
- useful scientific reference for atmospheric, soil, vegetation, ionospheric, and deformation effects.

Its study-specific paths, constants, plotting, and mixed responsibilities should not be migrated directly.

### tc_snow_variability_insar

Primary role:

- strong example of a reproducible study repository;
- useful provenance patterns such as explicit statistics mapping and rebuild scripts;
- NISAR coherence/scaling studies.

Keep its paper-specific workflow outside SnowIn.

### snowsar

Primary role:

- evidence of demand for snow-focused NISAR streaming, ancillary integration, and workflow abstraction.

Avoid importing its large dependency footprint or general interfaces uncritically.

### ISCE3, Dolphin, SNAPHU, TOPHU, SPURT, Sweets, MintPy, nisarqa

Primary role:

- upstream general SAR/InSAR infrastructure;
- examples of mature testing, configuration, CLI, workflows, and narrow specialist packages.

SnowIn should interoperate rather than duplicate their generic capabilities.

### NISAR Science Algorithms / NISAR ATBD repositories

Primary role:

- mission-science workflow and contribution references;
- examples of configuration and algorithm-documentation practices.

They are not direct SnowIn architecture templates.

### pandas and xarray

Primary role:

- API stability, explicit data models, missing-data semantics, alignment, documentation, testing, deprecation discipline, and ecosystem interoperability.

SnowIn should learn from these principles without imitating their project scale.

### Pangeo and xarray-contrib ecosystem

Primary role:

- establishes the preferred geoscience interoperability model around xarray, lazy arrays, cloud/file abstractions, and small domain-specific extensions.

SnowIn should behave naturally inside this ecosystem.

## 19. Authoritative software-development references

Primary packaging and scientific-Python references:

- Python Packaging User Guide:
  https://packaging.python.org/
- src layout guidance:
  https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/
- pyproject.toml specification:
  https://packaging.python.org/en/latest/specifications/pyproject-toml/
- PEP 621:
  https://peps.python.org/pep-0621/
- Scientific Python Development Guide:
  https://learn.scientific-python.org/development/
- Scientific Python testing recommendations:
  https://learn.scientific-python.org/development/principles/testing/
- Scientific Python SPEC 0:
  https://scientific-python.org/specs/spec-0000/
- pyOpenSci Python package guide:
  https://www.pyopensci.org/python-package-guide/
- JOSS review criteria:
  https://joss.readthedocs.io/en/latest/review_criteria.html
- FAIR Principles for Research Software:
  https://www.rd-alliance.org/groups/fair-research-software-fair4rs-wg/

Primary ecosystem references inspected:

- https://github.com/pydata/xarray
- https://github.com/pandas-dev/pandas
- https://github.com/pangeo-data
- https://github.com/xarray-contrib
- https://github.com/scientific-python
- https://github.com/ProjectPythia
- https://github.com/numpy/numpy
- https://github.com/scipy/scipy
- https://github.com/dask/dask
- https://github.com/dask/distributed
- https://github.com/zarr-developers/zarr-python
- https://github.com/fsspec/filesystem_spec
- https://github.com/rasterio/rasterio
- https://github.com/corteva/rioxarray
- https://github.com/OSGeo/gdal
- https://github.com/OSGeo/PROJ
- https://github.com/pyproj4/pyproj
- https://github.com/shapely/shapely
- https://github.com/geopandas/geopandas
- https://github.com/earthaccess-dev/earthaccess

Primary SAR/snow references inspected:

- https://github.com/jacktarricone/nisar-grl-colorado-firstlook
- https://github.com/ZachHoppinen/nisar_pytools
- https://github.com/ZachHoppinen/tc_snow_variability_insar
- https://github.com/rpalomaki/SWE_error_analysis/tree/v1.0
- https://github.com/ua-asf/nisar-docs
- https://github.com/isce-framework/isce3
- https://github.com/isce-framework/nisarqa
- https://github.com/isce-framework/dolphin
- https://github.com/isce-framework/snaphu-py
- https://github.com/isce-framework/sweets
- https://github.com/isce-framework/tophu
- https://github.com/isce-framework/spurt
- https://github.com/insarlab/MintPy
- https://github.com/nisar-solid/ATBD
- https://github.com/SnowEx/uavsar_pytools
- https://github.com/SnowEx/uavsar_snow
- https://github.com/ZachHoppinen/uavsar-validation
- https://github.com/ehavazli/snowsar
- https://github.com/snowex-hackweek/uavsar
- https://github.com/NISAR-Science-Algorithms

## 20. Decision principle

When in doubt:

1. preserve scientific meaning;
2. prefer explicit behavior over hidden convenience;
3. use upstream infrastructure rather than duplicate it;
4. keep the public API smaller than the internal implementation;
5. add capabilities only after a real workflow demonstrates the need;
6. test scientific invariants before expanding abstraction;
7. explain each development step before moving to the next.
