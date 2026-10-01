# SnowIn: InSAR tools for snow

[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](#installation)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/snowin-org/snowin/blob/main/LICENSE)

**SnowIn** is an open-source Python package for estimating pairwise changes in snow water equivalent (ΔSWE) from interferometric synthetic aperture radar (InSAR) phase. SnowIn provides the scientific core for developing, testing, and comparing InSAR-based SWE retrieval algorithms in a consistent xarray-native framework, allowing researchers to focus on retrieval science rather than rebuilding data handling, geometry, referencing, support, and time-series logic for each study.

Built on [xarray](https://xarray.dev/), SnowIn uses labeled `DataArray` and `Dataset` objects or explict metadata handling, package implements published phase-to-ΔSWE retrieval methods, including the Guneriussen, Leinss, and Oveisgharan formulations, together with tools for phase referencing, support-mask composition, local-incidence-angle calculation, and chronological ΔSWE accumulation.

**SnowIn** currently supports NASA–ISRO SAR ([NISAR](https://nisar-docs.asf.alaska.edu/nisar-intro/)) Geocoded Unwrapped Interferogram ([GUNW](https://nisar-docs.asf.alaska.edu/gunw/)) products by preserving phase convention, wavelength, geometry, grid, and source metadata. The underlying scientific operations remain product-independent, with the goal of supporting additional InSAR missions and product types as the package develops.

**SnowIn** intentionally does not choose or download remote-sensing products, apply phase corrections, select masks or reference contributors, read station data, or define study-specific validation. Those decisions remain in the user's workflow. 

## Installation

SnowIn 0.1.0 is not published yet. For now, install this checkout:

```bash
python -m pip install .
```

The base install requires NumPy and xarray. Install optional GUNW and geometry
support with:

```bash
python -m pip install ".[nisar,geometry]"
```

To create a Conda development environment from the repository root, run:

```bash
conda env create -f environment.yml
conda activate snowin
python -m pip install -e ".[nisar,geometry,dask]" --group dev --group docs --group notebooks
jupyter lab notebooks/01_core_snowin_workflow.ipynb
```

After publication, the same commands work with `snowin` in place of `.`.

## Quick start

Phase is `phi_secondary - phi_reference`; phase and incidence are in radians,
and wavelength is in metres.

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
    math.radians(35),
    attrs={"units": "rad", "incidence_angle_reference": "local"},
)

dswe = compute_leinss_dswe(phase, incidence, wavelength_m=0.2384)
print(f"Pairwise dSWE: {dswe.item():.3f} m")
```

Use `compute_guneriussen_dswe()` for the density-dependent method or
`compute_oveisgharan_dswe()` for the fitted incidence-angle method.

## NISAR GUNW

`open_gunw()` normalizes phase and product metadata. Local incidence is a
separate operation using a caller-prepared DEM:

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
    pair["dswe"] = compute_leinss_dswe(
        pair.phase,
        pair.incidence_angle,
        wavelength_m=pair.attrs["wavelength_m"],
    )
```

See notebooks [01](notebooks/01_core_snowin_workflow.ipynb),
[02](notebooks/02_real_nisar_gunw_workflow.ipynb), and
[03](notebooks/03_nisar_pytools_search_and_snowin.ipynb) for complete examples.

## Scientific contract and citation

Read the [scientific conventions](docs/scientific_conventions.md),
[normalized data model](docs/data_model.md), and
[DEM vertical datum assumptions](docs/vertical_datums.md). Method references
and product provenance are in [code and scientific provenance](docs/code_provenance.md).

Follow [CITATION.cff](CITATION.cff): cite the repository commit or release used
and the scientific publication for the retrieval method. SnowIn is licensed
under [Apache-2.0](LICENSE).
