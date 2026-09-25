# SnowIn notebooks

These two notebooks demonstrate SnowIn's generic scientific contract and its
NISAR GUNW adapter. They are examples in the repository; the installable Python
package is discovered only under `src/snowin`.

## Core workflow

[`01_core_snowin_workflow.ipynb`](01_core_snowin_workflow.ipynb) is data-free.
It uses synthetic xarray arrays to demonstrate normalized phase, dSWE,
reference phase, corrections, support, temporal accumulation, metrics, and
plots.

## Real NISAR GUNW workflow

[`02_real_nisar_gunw_workflow.ipynb`](02_real_nisar_gunw_workflow.ipynb)
accepts a local GUNW product through `SNOWIN_GUNW`. It first inspects product
metadata and normalized phase, then explicitly adds local-incidence geometry
and computes pairwise dSWE. Set `SNOWIN_NISAR_DEM` to a local NISAR-modified
Copernicus DEM to avoid staging it through the configured cache.

Create the scientific environment and install SnowIn from the checkout with:

```bash
conda env create -f environment.yml
conda activate snowin
conda env update -n snowin -f environment-notebooks.yml
python -m pip install -e .
```

Notebook 01 requires no external files. Notebook 02 requires a caller-supplied
GUNW; no product, credential, or generated raster is stored in the repository.
