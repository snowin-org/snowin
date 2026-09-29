# SnowIn

[![CI](https://github.com/snowin-org/snowin/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/snowin-org/snowin/actions/workflows/ci.yml)
[![Lint and format with Ruff](https://img.shields.io/badge/lint%20%26%20format-Ruff-D7FF64?logo=ruff&logoColor=black)](https://docs.astral.sh/ruff/)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](#installation)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

`SnowIn` is a Python package for estimating changes in snow water equivalent
(dSWE) from interferometric phase. The initial 0.1 release focuses on NISAR
geocoded unwrapped interferogram (GUNW) products: it reads and normalizes
product phase, derives local incidence angles from radar geometry and
elevation data, and provides named Leinss, Guneriussen, and Oveisgharan
methods for converting phase to pairwise dSWE. It also provides reusable
operations for reference-phase handling, phase corrections, support and
quality layers, and accumulating dSWE across directed time intervals.

SnowIn works with labeled [`xarray`](https://xarray.dev/) `DataArray` and
`Dataset` objects. Operations retain coordinates and relevant units, masks,
and processing details. Phase direction, angle units, wavelength, and geometry
assumptions are explicit so users can inspect the inputs and results of a
retrieval.

SnowIn is NISAR-first. Other sensor adapters, including Sentinel-1 and ROSE-L,
are future work. SnowIn provides snow-specific analysis around mission
processing tools; it does not replace general InSAR processors such as ISCE or
Dolphin.

**Project links:** [repository](https://github.com/snowin-org/snowin) ·
[roadmap](ROADMAP.md) ·
[scientific conventions](docs/scientific_conventions.md) ·
[data model](docs/data_model.md) ·
[architecture](docs/architecture.md) ·
[contributing](CONTRIBUTING.md) ·
[issues](https://github.com/snowin-org/snowin/issues)

## Status

SnowIn 0.1.0 is an alpha scientific package for named xarray dSWE retrievals,
reference and correction operations, support composition, directed temporal
accumulation, and a narrow optional NISAR GUNW adapter. Local-incidence
geometry is also optional and requires a prepared DEM supplied by the caller.

Important limits remain:

- The canonical retrieval produces pairwise or accumulated dSWE. It is not an
  absolute SWE product or a universal validation workflow.
- Local incidence uses NISAR LOS geometry and an explicitly declared prepared
  DEM source. Cells without valid terrain or LOS support, including
  back-facing terrain, have missing incidence and are marked invalid in
  geometry_valid.
- Product search, downloads, S3 staging, DEM acquisition, GIS utilities,
  plotting, and study policy are caller-owned workflow operations.
- SnowIn has no published PyPI or conda-forge release. Install from a checkout
  while the public API is still evolving.

Read the API policy for supported imports and the package boundary. Scientific
contracts and limitations are documented in the data model, scientific
conventions, DEM vertical-datum notes, and architecture guide.

## Installation

There is not yet a published PyPI or conda-forge release. Install the SnowIn
scientific core from a checkout with:

    python -m pip install -e .

The base install requires NumPy and xarray. The maintained runtime extras are:

- nisar for local NISAR GUNW reading and HDF5 support;
- geometry for NISAR local-incidence calculation from a prepared DEM;
- dask for Dask-backed arrays.

For repository notebooks and contributor tools, use pip 25.1 or newer and the
internal dependency groups. The notebook group includes Matplotlib, GIS,
Earthdata, and cloud libraries used by examples and study workflows; these are
not SnowIn runtime requirements.

    python -m pip install --upgrade pip
    python -m pip install -e ".[nisar,geometry,dask]" --group dev --group notebooks

The full-workflow Conda environment is convenient for repository examples but
does not define SnowIn's package dependencies. See the development guide for
the Conda and notebook setup.

## Find and open NISAR products

SnowIn does not wrap product search or downloads. Use nisar-pytools directly
for ASF product discovery and validated downloads. Search results are URL
strings and downloads return local paths. Search supports GSLC and other NISAR
product types, while SnowIn's current normalized adapter reads GUNW products.

    from pathlib import Path
    from nisar_pytools import download_urls, find_nisar
    from snowin.io import open_gunw

    gunw_urls = find_nisar(
        aoi=[-115, 43, -114, 44],
        start_date="2025-08-01",
        end_date="2025-12-01",
        product_type="GUNW",
        path_number=77,
        direction="ASCENDING",
    )
    if not gunw_urls:
        raise RuntimeError("No matching GUNW products were found")

    out_dir = Path.home() / ".cache" / "snowin" / "gunw"
    files = download_urls(gunw_urls[:1], out_dir, validate=True)
    if not files:
        raise RuntimeError("No GUNW product was downloaded and validated")

    with open_gunw(files[0]) as pair:
        print(pair.attrs["reference_time"], "→", pair.attrs["secondary_time"])

The search-to-SnowIn notebook demonstrates direct nisar-pytools discovery,
local GUNW reading, prepared-DEM geometry, and pairwise dSWE. SnowIn does not
read GSLC products or fetch ancillary datasets.

## Quick start

The named retrievals accept normalized phase and incidence-angle DataArrays.
Both angles use radians and the phase must be `secondary - reference`. Supply
the wavelength in metres or explicitly select a stock sensor/band:

```python snowin-quickstart
import math

import xarray as xr

from snowin import compute_leinss_dswe

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

dswe = compute_leinss_dswe(phase, incidence, wavelength_m=0.238403545)
print(f"dSWE: {dswe.item():.3f} m")
```

## Named dSWE retrieval methods

SnowIn exposes one xarray-native function per phase-to-dSWE model. All require
canonical `secondary - reference` phase and aligned incidence angles in
radians. Pass the product wavelength explicitly when known, or select a stock
mission value with `sensor` and, for multi-band missions, `band`. SnowIn does
not guess a sensor or wavelength. Product metadata is preferred to registry
values.

| Function | Model | Method-specific inputs and stock settings |
| --- | --- | --- |
| `compute_leinss_dswe` | Leinss et al. (2015) approximation | `alpha=1.0` and snow-path constant `1.59` are the stock values; `alpha` may be calibrated. |
| `compute_guneriussen_dswe` (`compute_gun_dswe`) | Density-dependent Guneriussen relation | Requires `snow_density_kg_m3`; `permittivity_model="guneriussen2001"` is the stock model. Also supports `"webb2021"` and `"maetzler"`. |
| `compute_oveisgharan_dswe` (`compute_ove_dswe`) | Oveisgharan et al. (2024) fitted relation | Uses the published incidence-angle polynomial; it has no density or `alpha` input. |

The common wavelength registry includes UAVSAR L-band (`0.2384035457` m),
NISAR L/S-band (`0.24`/`0.10` m), and other supported missions. For NISAR GUNW
products, `open_gunw` obtains the wavelength from product metadata. The
Guneriussen dSWE method requires snow density even though some source inversion
code defaults permittivity for snow-depth retrieval: converting snow-depth
change to SWE also needs the snow-to-water density ratio. No stock snow density
is assumed. Density may be a scalar in kg m-3 or a same-grid DataArray declaring
`units="kg m-3"`.

The Guneriussen and Webb density-permittivity alternatives are also represented
in [SnowEx/uavsar_snow](https://github.com/SnowEx/uavsar_snow), which documents
the UAVSAR L-band wavelength as a stock value.

```python
from snowin import compute_gun_dswe, compute_leinss_dswe, compute_ove_dswe

dswe_leinss = compute_leinss_dswe(
    phase, incidence, sensor="uavsar"
)
dswe_oveisgharan = compute_ove_dswe(
    phase, incidence, sensor="uavsar"
)
dswe_guneriussen = compute_gun_dswe(
    phase,
    incidence,
    sensor="uavsar",
    snow_density_kg_m3=300.0,  # illustrative; use a scene-specific value
)
```

`compute_dswe` remains as a backwards-compatible spelling of
`compute_leinss_dswe`; it still requires `wavelength_m` explicitly.

For a NISAR GUNW,  from product metadata and
opens normalized phase without waiting for geometry. Local incidence is a
separate calculation. Pass a prepared DEM explicitly:

    from snowin.io import add_gunw_incidence, open_gunw

    pair = open_gunw("product.h5")
    add_gunw_incidence(
        pair,
        "product.h5",
        dem="/path/to/nisar_dem.tif",
        dem_source="nisar_cop30",
        require_vertical_datum_match=True,
    )

The geometry calculation uses the GUNW LOS vectors and caller-supplied DEM,
then appends incidence, a geometry-valid support mask, and provenance.
Unsupported and back-facing terrain cells receive missing incidence values.
The explicit GUNW path prevents geometry from being inferred from another
product. Use chunks=None for eager loading when Dask is not installed.

For other prepared DEMs, set dem_source to cop30, tandem30, or srtm30 and pass
the same dem argument. SnowIn does not download or cache DEMs. The source name
declares the vertical-datum contract; orthometric sources may need a prepared
vertical correction through dem_vertical_correction_m. Set
require_vertical_datum_match=True to reject unmatched geometry. Use the
fixture notes and GUNW example for fuller workflows.

See the [fixture notes](tests/fixtures/README.md) and the
[GUNW example](examples/demo_gunw_local_s3_dswe.py) for fuller workflows.

## What SnowIn provides

- Optional NISAR GUNW reading and source-phase normalization through the
  nisar-pytools adapter.
- Named xarray-native Leinss, Guneriussen, and Oveisgharan pairwise dSWE
  retrievals.
- Explicit reference-phase methods and phase-correction operations.
- Directed temporal dSWE accumulation with explicit missing-support behavior.
- Named support layers, support composition, summaries, and validation metrics.
- Optional NISAR local-incidence geometry from a prepared DEM.

Product discovery, downloads, cloud staging, ancillary-data preparation,
vector loading, file export, and plotting belong to the calling workflow.
New NISAR workflows compose open_gunw, add_gunw_incidence, and the named dSWE
function matching the selected physical model. compute_dswe is the Leinss
retrieval, not a method dispatcher. For routine plots, use xarray's .plot
methods in an environment with Matplotlib.

SnowIn does not silently convert missing support to zero, apply a universal
quality mask, or move Colorado station/date policy into the general package.

## Scientific conventions and data model

The core contract is deliberately explicit:

- canonical phase is `phi_secondary - phi_reference`;
- temporal edges run from `reference_time` to `secondary_time`;
- phase and incidence angle use radians;
- wavelength is explicit in metres or resolved from an explicitly named stock
  sensor/band;
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
- [NISAR search and SnowIn notebook](notebooks/06_nisar_pytools_search_and_snowin.ipynb)
- [Notebook training materials](notebooks/README.md)
- [External real-product fixture notes](tests/fixtures/README.md)

The documentation source is built in CI with MkDocs. The documentation
workflow publishes it from `main` when GitHub Pages is enabled for the
repository.

## Development and testing

After installing the development and notebook groups, run the same checks used by the
current GitHub Actions workflow:

```bash
pytest -q
pytest --cov=snowin --cov-report=term-missing --cov-report=xml
ruff check .
ruff format --check .
python -m build
git diff --check
```

The test suite covers scientific contracts and dSWE/SWE kernels, geometry,
NISAR/GUNW adapters, reference phase, temporal accumulation, support and
metrics, diagnostics, cloud/raster I/O, and workflow/fixture behavior. CI tests
Python 3.12–3.14 and a minimum scientific-dependency set, checks coverage,
Ruff, and the command-line entry point, and installs a built wheel in a clean
environment. A separate workflow builds the documentation strictly and
publishes it from `main` when Pages is enabled.

Tests that need external real-product data are optional; their inputs and
provenance are documented in [`tests/fixtures/README.md`](tests/fixtures/README.md).

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
