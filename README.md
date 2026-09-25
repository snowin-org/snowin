# SnowIn

[![CI](https://github.com/snowin-org/snowin/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/snowin-org/snowin/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](#installation)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/snowin-org/snowin/blob/main/LICENSE)

`SnowIn` is a Python package for estimating changes in snow water equivalent
(dSWE) from interferometric phase. The initial 0.1 release focuses on NISAR
geocoded unwrapped interferogram (GUNW) products: it reads and normalizes
product phase, derives local incidence angles from radar geometry and
elevation data, and provides named Leinss, Guneriussen, and Oveisgharan
methods for converting phase to pairwise dSWE. It also provides reusable
operations for reference-phase handling, phase corrections, support and
quality layers, and accumulating dSWE across directed time intervals.

SnowIn works with labeled [`xarray`](https://xarray.dev/) `DataArray` and
`Dataset` objects. Its operations retain coordinates and relevant units,
masks, and processing details. Phase direction, angle units, wavelength, and
geometry assumptions are stated so users can inspect the inputs and results of
a retrieval.

SnowIn is NISAR-first. Other sensor adapters, including Sentinel-1 and ROSE-L,
are future work. SnowIn provides snow-specific analysis around mission
processing tools; it does not replace general InSAR processors such as ISCE or
Dolphin.

**Project links:** [repository](https://github.com/snowin-org/snowin) ·
[roadmap](https://github.com/snowin-org/snowin/blob/main/ROADMAP.md) ·
[scientific conventions](https://github.com/snowin-org/snowin/blob/main/docs/scientific_conventions.md) ·
[data model](https://github.com/snowin-org/snowin/blob/main/docs/data_model.md) ·
[architecture](https://github.com/snowin-org/snowin/blob/main/docs/architecture.md) ·
[contributing](https://github.com/snowin-org/snowin/blob/main/CONTRIBUTING.md) ·
[issues](https://github.com/snowin-org/snowin/issues)

## Status

SnowIn is preparing its first alpha release, version 0.1.0. This release
provides xarray-based snow retrieval operations, a NISAR GUNW reader, local
incidence geometry, named phase-to-dSWE methods, reference-phase operations,
directed temporal accumulation, support and quality tools, and GUNW
diagnostics and quick-look plots. See [Core API and scope](#core-api-and-scope)
for the current feature list.

Important limits remain:

- The retrieval produces pairwise or accumulated changes in SWE (dSWE); it
  does not estimate absolute SWE. Validation metrics are available, but a
  validation workflow still depends on the observations and comparison choices
  supplied by the user.
- The default geometry uses public Copernicus GLO-30 elevation data, whose
  heights are referenced to the EGM2008 geoid, while GUNW radar-grid heights
  use the WGS84 ellipsoid. Without a supplied geoid correction, the geometry
  result is provisional. Geometry is computed eagerly; phase data can remain
  lazy.
- Reading NISAR GSLC products is not included in 0.1.
- `SnowIn` has no published PyPI or Conda release and no hosted documentation
  site yet. Install from a checkout while the public API is still evolving.

The active implementation plan is in
[`ROADMAP.md`](https://github.com/snowin-org/snowin/blob/main/ROADMAP.md).
Scientific contracts and limitations are documented in the
[data model](https://github.com/snowin-org/snowin/blob/main/docs/data_model.md),
[scientific conventions](https://github.com/snowin-org/snowin/blob/main/docs/scientific_conventions.md),
and [architecture](https://github.com/snowin-org/snowin/blob/main/docs/architecture.md)
documents.

## Installation

### Current development checkout

There is not yet a released user installation. For the current repository:

```bash
git clone https://github.com/snowin-org/snowin.git
cd snowin
python -m pip install -e .
```

`SnowIn` requires Python 3.12 or newer. The base runtime depends only on
[`numpy`](https://numpy.org/) and [`xarray`](https://xarray.dev/).

Install optional capabilities as needed:

```bash
python -m pip install -e ".[gunw]"        # NISAR GUNW, HDF5, raster, geometry, plotting
python -m pip install -e ".[cloud]"       # fsspec + S3 access
python -m pip install -e ".[gunw,cloud]"  # both user-facing optional stacks
python -m pip install -e ".[dev]"         # tests, build tools, Dask, GUNW/geospatial dev deps
```

The `dev` extra includes the dependencies used by the repository's test/build
workflow, including [`pytest`](https://docs.pytest.org/),
[`Ruff`](https://docs.astral.sh/ruff/), [`build`](https://build.pypa.io/), and
optional [`Dask`](https://www.dask.org/) support. `Dask` is optional at runtime;
`xarray` is a core dependency.

When releases are published, this section should lead with the normal
`pip install snowin` and `conda`/`mamba` commands and retain source installation
as a development option.

## Quick start

### Phase to dSWE

The canonical kernel accepts normalized phase and incidence-angle
`xarray.DataArray` objects. Both angles use radians, the phase must be
`secondary - reference`, and wavelength is always explicit in metres:

```python
import math
import xarray as xr
from snowin import compute_dswe

phase = xr.DataArray(
    1.2,
    attrs={
        "units": "rad",
        "phase_difference_definition": "secondary_minus_reference",
    },
)
incidence = xr.DataArray(
    math.radians(35.0),
    attrs={"units": "rad", "incidence_angle_reference": "local"},
)

dswe = compute_dswe(phase, incidence, wavelength_m=0.238403545)
print(f"dSWE: {dswe.item():.3f} m")
```

### Open a NISAR GUNW

For a NISAR GUNW, `snowin.io.open_gunw` resolves wavelength from product
metadata and, by default, computes local incidence from GUNW LOS vectors and a
downloaded or cached Copernicus GLO-30 DEM:

```python
from snowin.io import open_gunw

pair = open_gunw("product.h5")
print(pair.attrs["wavelength_m"])
```

The default GUNW path uses [`Dask`](https://www.dask.org/) for lazy loading.
Without `Dask`, pass `chunks=None` for an eager read. The `gunw` extra supplies
the HDF5, raster, geometry, scientific-computing, and plotting dependencies
needed by this workflow.

Use `cop30_dem="/path/to/cop30.tif"` to provide a local DEM, or provide an
explicit `wavelength_m` override only when its scientific provenance is known.
See the
[external-product fixture notes](https://github.com/snowin-org/snowin/blob/main/tests/fixtures/README.md)
and [local/S3 GUNW example](https://github.com/snowin-org/snowin/blob/main/examples/demo_gunw_local_s3_dswe.py)
for fuller workflows.

Authoritative NISAR references are available in the
[ASF NISAR Data User Guide](https://nisar-docs.asf.alaska.edu/), including the
[GUNW product guide](https://nisar-docs.asf.alaska.edu/gunw/),
[product specifications](https://nisar-docs.asf.alaska.edu/product-specification/),
and [NISAR data-access guidance](https://nisar-docs.asf.alaska.edu/accessing-nisar/access-overview/).

## Core API and scope

The public API is still evolving, but the current top-level interface exposes:

| Import | Purpose |
| --- | --- |
| `snowin.compute_dswe` | Convert normalized interferometric phase to pairwise dSWE with the Leinss method. |
| `snowin.compute_leinss_dswe` | Apply the named Leinss phase-to-dSWE method. |
| `snowin.compute_gun_dswe` | Apply the density-dependent Guneriussen method. |
| `snowin.compute_ove_dswe` | Apply the Oveisgharan phase-to-dSWE method. |
| `snowin.reference_phase` | Estimate/apply explicit reference-phase strategies. |
| `snowin.accumulate_dswe` | Accumulate directed dSWE edges through time with explicit support behavior. |
| `snowin.build_support_dataset` | Construct named support/quality layers. |
| `snowin.compose_support_mask` | Combine named support criteria without silently redefining missing data. |
| `snowin.summarize_support` | Summarize retrieval support. |
| `snowin.compute_metrics` | Compute reusable validation-ready metrics. |
| `snowin.io.open_gunw` | Open and normalize supported NISAR GUNW inputs. |
| `snowin.gunw_to_dswe` | Run the legacy GUNW-to-dSWE workflow; new workflows should use `snowin.io.open_gunw`. |
| `snowin.plot_gunw` | Produce GUNW quick-look plots and diagnostics when optional dependencies are installed. |

The package also installs the provisional `snowin-plot-gunw` command-line entry
point. Running that command requires the relevant `gunw` optional dependencies.

`SnowIn` does **not** silently convert missing support to zero, impose a
universal quality mask, or move study-specific station/date policy into the
general package. It is also not intended to replace a general SAR processor,
phase-linking system, phase unwrapper, or deformation time-series package.

## Scientific Python ecosystem

`SnowIn` deliberately builds on established packages rather than reimplementing
their core capabilities.

### Core dependencies

- [`numpy`](https://numpy.org/) — numerical array operations.
- [`xarray`](https://xarray.dev/) — labeled `DataArray`/`Dataset` objects,
  coordinate-aware computation, metadata, and interoperability.

### Optional workflow dependencies

The `gunw`, `cloud`, and `dev` extras use established packages for specific
capabilities. Exact dependency constraints in
[`pyproject.toml`](https://github.com/snowin-org/snowin/blob/main/pyproject.toml)
are the source of truth:

- [`Dask`](https://www.dask.org/) — lazy and parallel array execution.
- [`h5py`](https://www.h5py.org/) and
  [`h5netcdf`](https://h5netcdf.org/) — HDF5/netCDF-backed product access.
- [`Rasterio`](https://rasterio.readthedocs.io/) — raster I/O and geospatial
  grid handling.
- [`pyproj`](https://pyproj4.github.io/pyproj/) — CRS and coordinate
  transformations.
- [`Shapely`](https://shapely.readthedocs.io/) — vector geometry operations.
- [`SciPy`](https://scipy.org/) — scientific numerical routines used by
  optional workflows.
- [`Matplotlib`](https://matplotlib.org/) — diagnostics and quick-look plotting.
- [`fsspec`](https://filesystem-spec.readthedocs.io/) and
  [`s3fs`](https://s3fs.readthedocs.io/) — filesystem abstraction and S3 access.

Because `SnowIn` operates on standard `xarray` objects, downstream workflows
can continue to use the wider `xarray` ecosystem. For example,
[`Zarr`](https://zarr.dev/) can be used through normal `xarray` I/O where that
backend is appropriate; `SnowIn` does not currently define a separate Zarr API.

## Related InSAR software

`SnowIn` is snow-specific and intentionally narrower than general InSAR
processing packages. Related open-source projects include:

- [`isce3`](https://github.com/isce-framework/isce3) — NASA/JPL's InSAR
  scientific-computing environment and core NISAR processing software.
- [`dolphin`](https://github.com/isce-framework/dolphin) — high-resolution
  wrapped-phase estimation and PS/DS phase-linking workflows.
- [`sweets`](https://github.com/isce-framework/sweets) — end-to-end InSAR
  time-series workflows, including Sentinel-1/OPERA and NISAR GSLC pathways.
- [`spurt`](https://github.com/isce-framework/spurt) — spatial and temporal
  phase unwrapping for InSAR time series.
- [`MintPy`](https://github.com/insarlab/MintPy) — general InSAR time-series
  analysis from stacks of unwrapped interferograms.

These projects are **not** `SnowIn` dependencies unless explicitly listed in
`pyproject.toml`. They are linked here to clarify where `SnowIn` fits in the
broader processing ecosystem and where upstream/general-purpose functionality
already exists.

## Scientific conventions and data model

The core contract is deliberately explicit:

- canonical phase is `phi_secondary - phi_reference`;
- temporal edges run from `reference_time` to `secondary_time`;
- phase and incidence angle use radians;
- wavelength is explicit in metres;
- local versus ellipsoid-referenced incidence is declared in metadata;
- dimensions, coordinates, attributes, CRS, support, missing values, and
  provenance are preserved where the operation permits;
- `xarray`/`Dask`-compatible arithmetic is used for reusable phase calculations.

Read the full
[data model](https://github.com/snowin-org/snowin/blob/main/docs/data_model.md)
and
[scientific conventions](https://github.com/snowin-org/snowin/blob/main/docs/scientific_conventions.md)
before building a workflow. The
[code provenance record](https://github.com/snowin-org/snowin/blob/main/docs/code_provenance.md)
lists the scientific equations, external implementations reviewed, and known
uncertainties.

## Examples and documentation

- [Architecture and design status](https://github.com/snowin-org/snowin/blob/main/docs/architecture.md)
- [Detailed architecture plan](https://github.com/snowin-org/snowin/blob/main/docs/snowin_architecture_v1.md)
- [Development guide](https://github.com/snowin-org/snowin/blob/main/docs/development.md)
- [GUNW quick-look example](https://github.com/snowin-org/snowin/blob/main/examples/plot_gunw_quickview.py)
- [Local/S3 GUNW example](https://github.com/snowin-org/snowin/blob/main/examples/demo_gunw_local_s3_dswe.py)
- [External real-product fixture notes](https://github.com/snowin-org/snowin/blob/main/tests/fixtures/README.md)

The repository currently provides source documentation and examples; hosted API
and user documentation are not yet configured. Once hosted documentation is
available, it should become the primary home for tutorials and API detail while
this README remains a concise project entry point.

## Development and testing

After installing the development extra, run the same checks used by the current
GitHub Actions workflow:

```bash
pytest -q
ruff check .
ruff format --check .
python -m build
git diff --check
```

The test suite covers scientific contracts and dSWE/SWE kernels, geometry,
NISAR/GUNW adapters, reference phase, temporal accumulation, support and
metrics, diagnostics, cloud/raster I/O, and workflow/fixture behavior. The
current CI job runs on Ubuntu with Python 3.12 and performs `pytest`, `Ruff`, and
package-build checks; it does not yet publish coverage or hosted documentation.

At the time of this README update, the local baseline is **133 passed and 1
skipped**, with the optional external real-product geometry regression
unavailable. The skipped-test setup is documented in the
[fixture notes](https://github.com/snowin-org/snowin/blob/main/tests/fixtures/README.md).
Re-measure the count when changing the suite rather than treating it as a
permanent quality guarantee.

For release preparation, `README.md` is already declared as the project readme
in `pyproject.toml`; build artifacts should also be checked with
[`twine check`](https://packaging.python.org/en/latest/guides/making-a-pypi-friendly-readme/)
before upload so the long description renders correctly on PyPI.

## Contributing

Please read
[`CONTRIBUTING.md`](https://github.com/snowin-org/snowin/blob/main/CONTRIBUTING.md)
before opening a pull request. Contributions should include relevant tests,
update public API docstrings and documentation, preserve `SnowIn`'s
units/phase/temporal/support conventions, and keep notebooks or exploratory
material out of core package logic.

Use the [GitHub issue tracker](https://github.com/snowin-org/snowin/issues) for
bugs and feature discussion. Small documentation, test, and reproducibility
improvements are useful contributions as well as new retrieval functionality.

## Citation

`SnowIn` does not yet have a tagged release, DOI, or `CITATION.cff`. Until those
are available, cite the repository and the commit used, and cite the primary
scientific publications listed in the
[code provenance record](https://github.com/snowin-org/snowin/blob/main/docs/code_provenance.md)
for the relevant retrieval methods. A formal software citation file should be
added before the first tagged release.

## License

`SnowIn` is distributed under the
[Apache License 2.0](https://github.com/snowin-org/snowin/blob/main/LICENSE).
