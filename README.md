# SnowIn

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](#installation)

SnowIn is an open-source Python package for snow-focused SAR and InSAR analysis. It is designed to make phase-based snow workflows more intuitive, reproducible, and scalable, from product access and preprocessing to dSWE, SWE, and validation-ready outputs.

The package is being developed around a snow-first, NISAR-first workflow, with early emphasis on GSLC/GUNW inputs, phase-based retrieval methods, reference phase strategies, ancillary integration, and validation workflows.

## Project status and roadmap

This README is the working status summary for the current development line.

Completed:

- Stage 0: package structure, development checks, and documentation baseline.
- Stage 1: authoritative xarray Dataset contracts, dimensions, units, temporal
  direction, phase sign, provenance, and support semantics.
- Stage 2: the verified xarray-native `compute_dswe` kernel using the Leinss
  phase-to-dSWE relation. The canonical phase is
  `phi_secondary - phi_reference`; incidence is radians; wavelength is
  explicit and in metres.
- Stage 3: the NISAR GUNW adapter. `open_gunw()` resolves wavelength from
  `centerFrequency`, normalizes the NISAR source phase convention, preserves
  lazy phase data, and generates local incidence from GUNW LOS vectors and a
  COP30 DEM. COP30 tiles can be downloaded and cached automatically, or a
  local DEM can be supplied.
- Stage 4 geometry hardening, currently active: analytic geometry tests,
  explicit CRS/grid/interpolation validation, failure behavior, and a real
  GUNW/COP30 regression fixture have been added.
- Stage 5 reference-phase foundation: the public `snowin.reference_phase`
  xarray API supports manual offsets, one-station offsets, unweighted means of
  multiple contributors, robust medians of contributors, and the
  Colorado/Zhou coherence-weighted additive offset. Station selection, SNOTEL
  matching, and expected-phase construction remain explicit caller
  responsibilities.
- Stage 6 temporal accumulation: `snowin.accumulate_dswe()` validates directed,
  contiguous chronological paths and propagates missing pairwise support
  instead of substituting zero.
- Stage 7 support and metrics foundation: named xarray support layers,
  explicit support composition, support summaries, and reusable bias/MAE/RMSE/
  correlation metrics with provenance are implemented. No universal quality
  mask or study-specific evaluation threshold is applied.

Current known limitation:

- GUNW LOS heights use a WGS84 ellipsoidal height axis, while Copernicus
  GLO-30 elevation is documented in the EGM2008 orthometric datum. SnowIn
  records this distinction, accepts an explicit same-grid geoid-undulation
  correction, and can reject uncorrected geometry with
  `require_vertical_datum_match=True`. Results without correction remain
  provisional until a product-backed geoid workflow is validated.

Next planned work:

1. Complete Stage 4 by validating a product-backed geoid correction and
   benchmark whether eager geometry should become chunk-aware/Dask-based.
2. Complete Stage 5 by auditing and characterizing the Colorado SNOTEL input
   construction without migrating its study-specific station/date policy.
3. Complete Stage 6 by extending path characterization beyond the explicit
   sequence API where needed.
4. Complete Stage 7 by adding study-specific evaluation adapters only when
   their scientific contracts are separately reviewed.
5. Stage 8: integrate stable SnowIn capabilities into the Colorado first-look
   study without migrating study-specific configuration.
6. Prepare release and Conda packaging after the scientific workflow is
   stable, documented, and reproducible.

Recent implementation commits:

```text
028b65d Harden Stage 4 geometry validation
5616a61 Add NISAR GUNW adapter and COP30 incidence
03f0f5a Merge Stage 2 dSWE kernel
```

The current validation baseline is `133 passed, 1 skipped`. The skipped test
is the external real-product regression when its large GUNW and COP30 fixture
files are not configured. See
[`tests/fixtures/README.md`](tests/fixtures/README.md) for setup.

## Why SnowIn?

Snow-focused InSAR workflows are often spread across scripts, notebooks, and repo-specific utilities. SnowIn provides one coherent interface for the pieces that matter most for snow analysis:

- reading and standardizing key products such as NISAR GSLC and GUNW
- computing phase-based snow retrievals such as dSWE and SWE transforms
- applying reference phase methods and quality screening
- integrating ancillary datasets such as SNOTEL, meteorology, and basin boundaries
- scaling from exploratory notebooks to reproducible package workflows

## Installation

SnowIn currently targets Python 3.12 and newer.

For development:

```bash
git clone git@github.com:snowin-org/snowin.git
cd snowin
python -m pip install -e ".[dev]"
```

## Quick start

```python
import math
import xarray as xr
from snowin.snow import compute_dswe

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

The canonical kernel requires phase already normalized to
`secondary_minus_reference`, explicit radians metadata, and an explicit
wavelength. The older NumPy `phase_to_dswe` method selector remains only for
legacy characterization and compatibility.

For a NISAR GUNW, the adapter resolves wavelength from the product metadata
and automatically downloads/caches the public COP30 tiles needed for local
incidence when no DEM is supplied:

```python
from snowin.io import open_gunw

pair = open_gunw("product.h5")
```

Use `cop30_dem="/path/to/cop30.tif"` to provide a local DEM, or
`wavelength_m=0.238403545` only when an explicit override is scientifically
justified.

## GUNW quick-look diagnostics

Install the GUNW/plotting dependencies during development:

```bash
python -m pip install -e ".[dev]"
```

Create a compact quick-look figure plus a layer-summary CSV and metadata JSON:

```python
from snowin import plot_gunw

result = plot_gunw(
    "/path/to/NISAR_L2_PR_GUNW_....nc",
    out_dir="plots/gunw_quicklooks",
    crop_geojson="/path/to/basin.geojson",
    show=True,
    verbose=True,
)

print(result.figure_paths)
print(result.summary_csv_path)
print(result.metadata_json_path)
```

The equivalent CLI is:

```bash
snowin-plot-gunw /path/to/NISAR_L2_PR_GUNW_....nc \
  --out-dir plots/gunw_quicklooks \
  --crop-geojson /path/to/basin.geojson
```

### Local/S3 GUNW demo and dSWE scaffold

The example below stages a local or `s3://` GUNW product, writes a quick-look,
and runs an explicit raw phase-to-dSWE scaffold. This is intended to test
package plumbing and provenance. It is not a validated SWE retrieval workflow.

```bash
python examples/demo_gunw_local_s3_dswe.py \
  --gunw /path/to/NISAR_L2_PR_GUNW_....nc \
  --out-dir outputs/snowin_demo \
  --crop-geojson /path/to/basin.geojson
```

For S3 inputs, install the optional cloud dependencies and provide a cache
directory:

```bash
python -m pip install -e ".[cloud]"
python examples/demo_gunw_local_s3_dswe.py \
  --gunw s3://bucket/path/NISAR_L2_PR_GUNW_....nc \
  --out-dir outputs/snowin_demo_s3 \
  --cache-dir outputs/snowin_s3_cache
```

## Current scope

SnowIn is not intended to be a general all-purpose SAR package. It is focused on snow science workflows, especially dry-snow phase-based retrievals and the supporting data/model plumbing needed to make those workflows usable and reproducible.

Initial development is centered on:

- core dry-snow phase-to-dSWE/SWE methods
- reference phase strategies
- quality and masking utilities
- NISAR GSLC/GUNW reading and normalization
- snow-relevant ancillary and validation tools

## Repository layout

- `src/snowin/`: installable package code
- `tests/`: automated tests for scientific and software behavior
- `docs/`: architecture, roadmap, contributor workflow, and method notes
- `examples/`: small runnable example scripts
- `notebooks/`: exploratory and tutorial notebooks
- `.github/`: automation and issue templates

## Documentation

See `docs/architecture.md`, `docs/snowin_architecture_v1.md`, and the focused
guides for [development](docs/development.md),
[scientific conventions](docs/scientific_conventions.md),
[the data model](docs/data_model.md), and
[code provenance](docs/code_provenance.md).

## Development checks

After installing the development extra, run:

```bash
pytest -q
ruff check .
ruff format --check .
python -m build
git diff --check
```

The project uses a `src/` layout, so install SnowIn in editable mode before
running package code from a checkout.

## Contributing

Contributions are welcome. Please read `CONTRIBUTING.md` before opening a pull request.

## Citation

Add a `CITATION.cff` file before the first tagged release.

## License

SnowIn is licensed under the Apache License 2.0. See the `LICENSE` file for details.
