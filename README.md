# SnowIn

[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](#installation)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/snowin-org/snowin/blob/main/LICENSE)

SnowIn estimates pairwise changes in snow water equivalent (dSWE) from
interferometric phase. Its retrieval methods use Xarray `DataArray` and
`Dataset` objects. The package also provides phase referencing, support-mask
composition, incidence geometry, and temporal accumulation.

SnowIn uses these signs and edge direction:

```text
phase = phi_secondary - phi_reference
dSWE = SWE_secondary - SWE_reference
temporal edge = reference -> secondary
```

Available retrievals are Leinss, Guneriussen, and Oveisgharan. The optional
NISAR adapter reads Geocoded Unwrapped Interferogram (GUNW) products.

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

Incidence is in radians and wavelength is in metres.

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

`open_gunw()` converts the source phase to the SnowIn convention and reads
product metadata. Local incidence is a separate operation using a
caller-prepared DEM:

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

For NISAR terrain-local incidence, SnowIn recommends the official
[Modified Copernicus DEM for NISAR](https://nisar-docs.asf.alaska.edu/nisar-dem/)
with `dem_source="nisar_cop30"`. This is Copernicus GLO-30 modified for NISAR,
including vertical re-referencing from the EGM2008 geoid to the WGS84
ellipsoid. Ordinary public Copernicus GLO-30 is a different product and
normally contains orthometric heights; a generic Copernicus DEM file is not
automatically equivalent.

See notebooks [01](notebooks/01_core_snowin_workflow.ipynb),
[02](notebooks/02_real_nisar_gunw_workflow.ipynb), and
[03](notebooks/03_nisar_pytools_search_and_snowin.ipynb) for complete examples.

## Documentation and citation

Read the [scientific conventions](docs/scientific_conventions.md),
[data model](docs/data_model.md), and
[DEM vertical datum assumptions](docs/vertical_datums.md). Method references
and product source metadata are in [scientific sources](docs/scientific_sources.md).

Follow [CITATION.cff](CITATION.cff): cite the repository commit or release used
and the scientific publication for the retrieval method. SnowIn is licensed
under [Apache-2.0](LICENSE).
