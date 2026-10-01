# SnowIn

[![CI](https://github.com/snowin-org/snowin/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/snowin-org/snowin/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](#installation)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

SnowIn is a small scientific Python package for estimating pairwise changes in
snow water equivalent (dSWE) from interferometric phase. It provides named
phase-to-dSWE methods, explicit phase referencing, named support composition,
chronological accumulation, and an optional NISAR GUNW adapter with local
incidence geometry. Its scientific interface uses ordinary xarray objects.

## What SnowIn does

- Computes pairwise dSWE with the Leinss, Guneriussen, and Oveisgharan models.
- Normalizes local NISAR GUNW phase and resolves wavelength from product
  center-frequency metadata.
- Computes local incidence from GUNW line-of-sight geometry and a prepared DEM.
- Provides auditable xarray reference operations, named support layers, and
  explicit directed-path accumulation.

## What SnowIn does not do

SnowIn does not discover or download products or ancillary data, apply phase
corrections, choose masks or reference contributors, read station data, plot,
or implement study validation policy. Those choices belong to the caller's
workflow.

## Installation

SnowIn 0.1 is not yet published to PyPI or conda-forge. Install from a checkout:

```bash
python -m pip install .
```

Optional integrations are installed with `.[nisar]`, `.[geometry]`, and
`.[dask]`. The base package requires NumPy and xarray.

## Quick start

The phase is `phi_secondary - phi_reference`; both phase and incidence use
radians. The wavelength is explicit in metres.

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

Use `compute_guneriussen_dswe` when snow density is supplied, or
`compute_oveisgharan_dswe` for its fitted incidence-angle relation. Each model
has its own named function and requires an explicit wavelength.

## NISAR GUNW workflow

`open_gunw()` returns a phase-normalized product. Incidence is calculated in a
separate step using a caller-prepared DEM; `add_gunw_incidence()` updates the
Dataset in place and returns it.

```python
from snowin import compute_leinss_dswe
from snowin.io import add_gunw_incidence, open_gunw

with open_gunw("product.h5") as pair:
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

The [NISAR product notebook](notebooks/02_real_nisar_gunw_workflow.ipynb) and
[product discovery handoff notebook](notebooks/03_nisar_pytools_search_and_snowin.ipynb)
show fuller caller-owned workflows.

## Scientific conventions

- Phase: `phi_secondary - phi_reference`, in radians.
- Temporal edge: `reference_time -> secondary_time`.
- Pairwise dSWE: `SWE_secondary - SWE_reference`, in metres water equivalent.
- Incidence: radians, explicitly identified as local or ellipsoid-referenced.
- Wavelength: metres, supplied explicitly or resolved from product metadata.
- Missing values remain missing; SnowIn does not create a universal quality mask.

See the [data model](docs/data_model.md), [scientific conventions](docs/scientific_conventions.md),
[architecture](docs/architecture.md), and [API policy](docs/api_policy.md).
Contributor setup and scientific validation guidance are in
[development](docs/development.md) and [testing](docs/testing.md).

## Citation

SnowIn has no tagged release or DOI yet. Cite the repository and commit used,
along with the relevant retrieval-method publications listed in
[code provenance](docs/code_provenance.md). See [CITATION.cff](CITATION.cff).

## License

SnowIn is distributed under the [Apache License 2.0](LICENSE).
