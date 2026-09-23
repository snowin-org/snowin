# SnowIn

[![CI](https://github.com/snowin-org/snowin/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/snowin-org/snowin/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](#installation)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

SnowIn is a snow-focused SAR/InSAR Python package, initially NISAR-first. It
turns phase-based snow retrieval inputs into analysis-ready xarray objects while
keeping units, coordinates, support, and scientific provenance explicit.

The long-term scope is broader snow-based InSAR analysis across sensors such as
Sentinel-1 and future ROSE-L products, but those adapters are planned rather
than active work. SnowIn is intended to be the snow-analysis layer around
mission-specific InSAR processors, not a replacement for general processors
such as ISCE or Dolphin.

## Status

SnowIn is under active pre-release development. The current line provides
xarray-native contracts and phase-to-dSWE calculations, a NISAR GUNW adapter,
COP30-based local-incidence geometry, reference-phase methods, directed
temporal accumulation, named support layers, reusable metrics, and GUNW
diagnostics/plotting scaffolding.

Important limits remain:

- The canonical retrieval produces pairwise or accumulated dSWE. It is not an
  absolute SWE product or a universal validation workflow.
- The default GUNW geometry path uses the NISAR-modified Copernicus DEM, whose
  heights are WGS84 ellipsoidal like the GUNW radar-grid heights. The original
  public COP30 compatibility path remains orthometric and requires an explicit
  EGM2008 geoid-undulation correction. Geometry is currently eagerly
  materialized; phase data can remain lazy.
- SnowIn has no published PyPI or Conda release and no hosted documentation
  site yet. Install from a checkout while the public API is still evolving.

Read the [API policy](docs/api_policy.md) for the distinction between the
stable root-level facade, domain-specific submodules, and legacy compatibility
paths.

The active implementation plan is in [`ROADMAP.md`](ROADMAP.md). Scientific
contracts and limitations are documented in the [data model](docs/data_model.md),
[scientific conventions](docs/scientific_conventions.md),
[DEM vertical-datum notes](docs/vertical_datums.md), and
[architecture](docs/architecture.md) documents.

## Installation

There is not yet a released user installation. For the current development
checkout:

```bash
git clone https://github.com/snowin-org/snowin.git
cd snowin
python -m pip install -e ".[dev]"
```

The base package requires Python 3.12 or newer, NumPy, and xarray. Optional
extras are available for specific workflows:

```bash
python -m pip install -e ".[gunw]"    # GUNW, raster, geometry, and plotting I/O
python -m pip install -e ".[cloud]"   # fsspec and S3 access
```

The `dev` extra includes the test, build, plotting, raster, geometry, and
optional Dask dependencies used by the repository checks. Dask is optional;
xarray is a core runtime dependency.

## Quick start

The canonical kernel accepts normalized phase and incidence-angle DataArrays.
Both angles use radians, the phase must be `secondary - reference`, and the
wavelength is always explicit in metres:

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

For a NISAR GUNW, `open_gunw` resolves wavelength from product metadata and
opens the normalized phase/product data without waiting for DEM geometry:

```python
from snowin.io import add_gunw_incidence, open_gunw

pair = open_gunw("product.h5")
print(pair.attrs["wavelength_m"])
add_gunw_incidence(pair, "product.h5")
```

The explicit `add_gunw_incidence` step computes local incidence from the
GUNW LOS vectors and the modified Copernicus DEM used by NISAR, then appends
`pair["incidence_angle"]` and its provenance. It requires the GUNW path so a
slow geometry calculation cannot accidentally use a different product.

The default GUNW path uses Dask for lazy loading; the `dev` extra includes it.
Without Dask, pass `chunks=None` for an eager read. The `gunw` extra supplies
the product, raster, geometry, and plotting dependencies.

Use `nisar_cop30_dem="/path/to/dem.tif"` to provide a local NISAR DEM and
avoid network access:

```python
pair = open_gunw("product.h5")
add_gunw_incidence(
    pair,
    "product.h5",
    nisar_cop30_dem="/path/to/nisar_dem.tif",
    require_vertical_datum_match=True,
)
```

The default incidence calculation is eager. For benchmarking a Dask-backed
prototype, pass `geometry_chunks=512` (or a `(y, x)` chunk pair) to
`add_gunw_incidence`; it preserves the eager default and is not yet a fully
out-of-core geometry implementation.

The default `dem_source="nisar_cop30"` downloads and caches the modified
Copernicus DEM used by NISAR. Use `dem_cache_dir=...` to control that cache.
The ASF Earthdata service may require standard Earthdata credentials in
`~/.netrc`. Other named local sources can be selected explicitly:

```python
pair = open_gunw("product.h5")
add_gunw_incidence(
    pair,
    "product.h5",
    dem_source="tandem30",
    tandem30_dem="/path/to/tandem30.tif",
    require_vertical_datum_match=True,
)
```

Supported sources are `nisar_cop30`, `cop30`, `tandem30`, and `srtm30`.
Only `nisar_cop30` and `cop30` have automatic download paths. TanDEM-X 30 m
and SRTM 30 m inputs must be provided locally; SnowIn does not silently
substitute one source for another. TanDEM-X is treated as ellipsoidal
WGS84-G1150, while SRTM30 is treated as orthometric and normally requires a
geoid correction for strict matching.

For public orthometric COP30 tiles selected with `dem_source="cop30"`, pass
`dem_vertical_correction_m="/path/to/egm2008_geoid.tif"` or a same-grid
xarray DataArray. The legacy `cop30_vertical_correction_m` spelling remains
accepted. Set `require_vertical_datum_match=True` to fail rather than run
provisionally. An explicit `wavelength_m` override should only be used when
its scientific provenance is known.
See the [fixture notes](tests/fixtures/README.md) and the
[GUNW example](examples/demo_gunw_local_s3_dswe.py) for fuller workflows.

## What SnowIn provides

- NISAR GUNW reading, phase-convention normalization, and product metadata
  handling. A GSLC adapter is not yet part of the stable implementation.
- Phase-based pairwise dSWE and legacy compatibility helpers for snow-depth/SWE
  experiments; the canonical public retrieval is `snowin.compute_dswe`.
- Explicit reference-phase methods, including manual and contributor-based
  aggregation policies.
- Directed temporal dSWE accumulation with explicit missing-support behavior.
- Named support and quality layers, support composition, summaries, and
  validation-ready metrics.
- COP30/local-DEM incidence geometry with CRS, grid, interpolation, and
  provenance checks.
- GUNW diagnostics, quick-look plotting, and a CLI where the optional
  dependencies are installed.

The older `gunw_to_dswe` workflow remains available for compatibility but is
legacy. New NISAR workflows should use `open_gunw`, `add_gunw_incidence`, and
`compute_dswe` explicitly; the two paths are not yet scientifically
interchangeable.

SnowIn does not silently convert missing support to zero, apply a universal
quality mask, or move Colorado study-specific station/date policy into the
general package.

## Scientific conventions and data model

The core contract is deliberately explicit:

- canonical phase is `phi_secondary - phi_reference`;
- temporal edges run from `reference_time` to `secondary_time`;
- phase and incidence angle use radians;
- wavelength is explicit in metres;
- local versus ellipsoid-referenced incidence is declared in metadata;
- dimensions, coordinates, attributes, CRS, support, missing values, and
  provenance are preserved where the operation permits;
- xarray/Dask-compatible arithmetic is used for reusable phase calculations.

Read the full [data model](docs/data_model.md) and [scientific conventions](docs/scientific_conventions.md)
before building a workflow. The [code provenance record](docs/code_provenance.md)
lists the scientific equations, external implementations reviewed, and known
uncertainties.

## Examples and documentation

- [Architecture and design status](docs/architecture.md)
- [Detailed architecture plan](docs/snowin_architecture_v1.md)
- [Development guide](docs/development.md)
- [API policy](docs/api_policy.md)
- [GUNW quick-look example](examples/plot_gunw_quickview.py)
- [Local/S3 GUNW example](examples/demo_gunw_local_s3_dswe.py)
- [Notebook training materials](notebooks/README.md)
- [External real-product fixture notes](tests/fixtures/README.md)

The repository currently provides source documentation and examples; hosted
documentation is not configured.

## Development and testing

After installing the development extra, run the same checks used by the
current GitHub Actions workflow:

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
current CI job runs on Ubuntu with Python 3.12 and performs pytest, Ruff, and
package-build checks; it does not yet publish coverage or documentation.

At the time of this update, the local baseline is **153 passed and 3 skipped**
with the optional external real-product geometry regression unavailable. The
skipped-test setup is documented in
[`tests/fixtures/README.md`](tests/fixtures/README.md); the number should be
re-measured rather than treated as a permanent quality guarantee.

## Contributing

Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening a pull request.
Contributions should include relevant tests, update public API docstrings and
documentation, preserve SnowIn's units/phase/temporal/support conventions, and
keep notebooks or exploratory material out of core package logic. Use the
[GitHub issue tracker](https://github.com/snowin-org/snowin/issues) for bugs and
feature discussion.

## Citation

SnowIn does not yet have a tagged release or DOI. Until those are available,
cite the repository and the commit used, and cite the primary scientific
publications listed in [`docs/code_provenance.md`](docs/code_provenance.md) for
the relevant retrieval methods. `CITATION.cff` provides machine-readable
software citation metadata for the pre-release package.

## License

SnowIn is distributed under the [Apache License 2.0](LICENSE).
