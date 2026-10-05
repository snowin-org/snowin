# SnowIn

[![CI](https://github.com/snowin-org/snowin/actions/workflows/ci.yml/badge.svg)](https://github.com/snowin-org/snowin/actions/workflows/ci.yml)
[![Documentation](https://github.com/snowin-org/snowin/actions/workflows/docs.yml/badge.svg)](https://github.com/snowin-org/snowin/actions/workflows/docs.yml)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](#installation)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

**Snow-focused, xarray-native tools for InSAR snow analysis.**

> :warning: **NOTICE**: SnowIn is in early development. Its features and scope are subject to change. Please check the [`CHANGELOG.md`](CHANGELOG.md) for a summary of updates.

SnowIn is a Python package for estimating pairwise changes in snow water equivalent
(**ΔSWE**) from repeat-pass interferometric SAR phase. It is built around
[xarray](https://xarray.dev/) `DataArray` and `Dataset` objects so that snow-specific
operations remain interoperable with the broader scientific Python ecosystem.

SnowIn implements published dry-snow phase-to-ΔSWE retrievals and the supporting
operations needed to use them reproducibly: phase normalization and referencing,
named support-mask composition, incidence geometry, and strict temporal accumulation.
The package currently includes retrievals based on
[Leinss et al. (2015)](https://doi.org/10.1109/JSTARS.2015.2432031),
[Guneriussen et al. (2001)](https://doi.org/10.1109/36.957273), and
[Oveisgharan et al. (2024)](https://doi.org/10.5194/tc-18-559-2024), together with an
optional adapter for NASA-ISRO SAR
[Geocoded Unwrapped Interferogram (GUNW)](https://nisar-docs.asf.alaska.edu/gunw/)
products.

## What SnowIn does

SnowIn provides an explicit scientific layer for snow InSAR workflows:

- **Phase-to-ΔSWE retrievals** using published methods with clear documentation and testing.
- **xarray-native inputs and outputs** that preserve labeled dimensions, coordinates, metadata, and Dask-backed arrays where supported.
- **NISAR GUNW ingestion** that reads and standardizes snow-relevant InSAR layers, including unwrapped phase, coherence, connected components, ionospheric and tropospheric correction layers, correction uncertainty, coordinates, radar wavelength, and source metadata.
- **80 m local incidence generation** for NISAR GUNW products using a user-supplied DEM.
- **Chronological ΔSWE accumulation** along an explicit sequence of reference-to-secondary interferometric pairs.

SnowIn provides the software layer for conducting InSAR snow science in a reproducible, transparent, and robust way. It brings the scientific conventions, published ΔSWE retrieval methods, NISAR product interpretation, phase referencing, incidence geometry, quality information, correction layers, and temporal accumulation needed for snow applications into a consistent xarray-based framework. This reduces the amount of study-specific processing code required for each analysis and makes the assumptions, units, phase conventions, metadata, and processing history easier to inspect and reproduce.

SnowIn is designed to work within the broader Earth-science software ecosystem rather than replace it. Users can obtain NISAR products with tools such as `nisar-pytools`, `asf_search`, or NASA Earthdata Search, then use SnowIn to translate those products into analysis-ready inputs for InSAR snow retrieval. Correction layers remain explicit so that users can evaluate and apply the appropriate corrections for their specific application.

## Installation

SnowIn `0.1.0` is not yet published. From a local checkout, install the base package
with:

```bash
python -m pip install .
```

The base install requires Python 3.12+, NumPy, and xarray.

Install optional NISAR product support and terrain geometry with:

```bash
python -m pip install ".[nisar,geometry]"
```

Add Dask-backed array support when needed:

```bash
python -m pip install ".[dask]"
```

For a full local development environment, see
[`CONTRIBUTING.md`](CONTRIBUTING.md).

## Quick start

SnowIn uses the convention

```text
phase = φ_secondary - φ_reference
ΔSWE = SWE_secondary - SWE_reference
```

Phase and incidence angle are in radians, and wavelength is in metres.

```python
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
    math.radians(35),
    attrs={
        "units": "rad",
        "incidence_angle_reference": "local",
    },
)

delta_swe = compute_leinss_dswe(
    phase,
    incidence,
    wavelength_m=0.2384,
)

print(f"Pairwise ΔSWE: {delta_swe.item():.3f} m")
```

The same xarray-based pattern applies to the other retrieval methods.

## Retrieval methods

All current retrievals estimate **pairwise dry-snow ΔSWE**, not absolute SWE.

| Retrieval | SnowIn API | Scientific basis |
| --- | --- | --- |
| **Leinss** | `compute_leinss_dswe()` | Dry-snow phase-to-ΔSWE approximation from [Leinss et al. (2015)](https://doi.org/10.1109/JSTARS.2015.2432031) |
| **Guneriussen** | `compute_guneriussen_dswe()` | Density-dependent dry-snow refraction formulation from [Guneriussen et al. (2001)](https://doi.org/10.1109/36.957273) |
| **Oveisgharan** | `compute_oveisgharan_dswe()` | Fitted incidence-angle formulation from [Oveisgharan et al. (2024)](https://doi.org/10.5194/tc-18-559-2024) |

See [`docs/scientific_sources.md`](docs/scientific_sources.md) for the implemented
equations, density/permittivity options, assumptions, and additional references.

## NISAR GUNW workflow

`open_gunw()` reads [NISAR Level-2 GUNW](https://nisar-docs.asf.alaska.edu/gunw/) products and metadata such
as radar wavelength. Terrain-local incidence is a separate, explicit operation using
a caller-prepared DEM.

```python
from snowin import compute_leinss_dswe
from snowin.io import add_gunw_incidence, open_gunw

with open_gunw("product.h5", chunks=None) as pair:
    add_gunw_incidence(
        pair,
        "product.h5",
        dem="prepared_dem.tif",
        dem_source="nisar_cop30",
    )

    delta_swe = compute_leinss_dswe(
        pair.phase,
        pair.incidence_angle,
        wavelength_m=pair.attrs["wavelength_m"],
    )
```

For a complete worked example, see
[Notebook 02: real NISAR GUNW workflow](notebooks/02_real_nisar_gunw_workflow.ipynb).
The notebook runs with the bundled ASF sample crop by default and can also use a local
GUNW and matching NISAR DEM.

## Getting NISAR data

SnowIn does **not** provide mission-product discovery or download as part of its core
API. Acquire a GUNW product with the tool that best fits your workflow, then pass the
local product to SnowIn.

Recommended sources and tools:

- [`nisar-pytools`](https://github.com/ZachHoppinen/nisar_pytools) — Python tools for
  searching, downloading, opening, and processing NISAR products.
- [`asf_search`](https://docs.asf.alaska.edu/asf_search/basics/) — Alaska Satellite
  Facility's Python package for programmatic catalog search and download.
- [NASA Earthdata Search](https://search.earthdata.nasa.gov/) — browser-based NASA
  data discovery and download; search for `NISAR_L2_GUNW`.
- [NISAR GUNW Data User Guide](https://nisar-docs.asf.alaska.edu/gunw/) — product
  specification, layers, and links to available data.

Downloading NISAR products requires a
[NASA Earthdata Login](https://urs.earthdata.nasa.gov/).

After acquiring a product, use
[Notebook 02](notebooks/02_real_nisar_gunw_workflow.ipynb) for the handoff from a
local GUNW into SnowIn.

### DEM for terrain-local incidence

For NISAR terrain-local incidence, SnowIn recommends the official
[Modified Copernicus DEM for NISAR](https://nisar-docs.asf.alaska.edu/nisar-dem/)
with:

```python
dem_source="nisar_cop30"
```

The NISAR DEM is derived from Copernicus GLO-30 and vertically re-referenced from the
EGM2008 geoid to the WGS84 ellipsoid for SAR processing. Ordinary public Copernicus
GLO-30 is a different product and is not automatically equivalent.

Download the official NISAR DEM from the
[`NISAR_DEM` collection in NASA Earthdata Search](https://search.earthdata.nasa.gov/search?q=NISAR_DEM).
The NISAR Data User Guide also documents direct S3 access and the available WGS84 and
polar stereographic datasets.

See [`docs/vertical_datums.md`](docs/vertical_datums.md) before using a different DEM
or applying a vertical-datum correction.

## Scientific conventions

Read the full
[scientific conventions](docs/scientific_conventions.md) and
[data model](docs/data_model.md) before building production workflows.

## Examples and documentation

Start with:

1. [Notebook 01: core SnowIn workflow](notebooks/01_core_snowin_workflow.ipynb) —
   synthetic xarray workflow covering the core package.
2. [Notebook 02: real NISAR GUNW workflow](notebooks/02_real_nisar_gunw_workflow.ipynb) —
   NISAR product ingestion, geometry, and ΔSWE retrieval.
3. [Notebook guide](notebooks/README.md) — complete notebook inventory and optional
   dependencies.

Reference documentation:

- [Scientific conventions](docs/scientific_conventions.md)
- [Data model](docs/data_model.md)
- [Scientific sources and equations](docs/scientific_sources.md)
- [DEM vertical datums](docs/vertical_datums.md)
- [Changelog](CHANGELOG.md)

## Citation

If you use SnowIn, follow [`CITATION.cff`](CITATION.cff): cite the repository commit
or release used and the primary scientific publication for the retrieval method.

## Contributing

Contributions are welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for development
and testing guidance.

## License

SnowIn is licensed under the [Apache License 2.0](LICENSE).
