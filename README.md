# SnowIn

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](#installation)

SnowIn is an open-source Python package for snow-focused SAR and InSAR analysis. It is designed to make phase-based snow workflows more intuitive, reproducible, and scalable, from product access and preprocessing to dSWE, SWE, and validation-ready outputs.

The package is being developed around a snow-first, NISAR-first workflow, with early emphasis on GSLC/GUNW inputs, phase-based retrieval methods, reference phase strategies, ancillary integration, and validation workflows.

## Why SnowIn?

Snow-focused InSAR workflows are often spread across scripts, notebooks, and repo-specific utilities. SnowIn provides one coherent interface for the pieces that matter most for snow analysis:

- reading and standardizing key products such as NISAR GSLC and GUNW
- computing phase-based snow retrievals such as dSWE and SWE transforms
- applying reference phase methods and quality screening
- integrating ancillary datasets such as SNOTEL, meteorology, and basin boundaries
- scaling from exploratory notebooks to reproducible package workflows

## Installation

For development:

```bash
git clone git@github.com:snowin-org/snowin.git
cd snowin
python -m pip install -e ".[dev]"
```

## Quick start

```python
import math
from snowin.snow import phase_to_dswe

dswe_m = phase_to_dswe(
    phase_rad=-1.2,
    method="oveisgharan",
    incidence_angle_rad=math.radians(35.0),
    sensor="nisar",
    band="L",
)
print(f"dSWE: {dswe_m:.3f} m")
```


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

See `docs/architecture.md` and `docs/team_workflow.md` for the current development model and team workflow.

## Contributing

Contributions are welcome. Please read `CONTRIBUTING.md` before opening a pull request.

## Citation

Add a `CITATION.cff` file before the first tagged release.

## License

SnowIn is licensed under the Apache License 2.0. See the `LICENSE` file for details.
