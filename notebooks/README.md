# SnowIn notebooks

1. [`01_core_snowin_workflow.ipynb`](01_core_snowin_workflow.ipynb) introduces the synthetic xarray science using the base NumPy/xarray dependencies.
2. [`02_real_nisar_gunw_workflow.ipynb`](02_real_nisar_gunw_workflow.ipynb) applies SnowIn to a local GUNW and prepared DEM; install the `nisar`, `geometry`, and `dask` extras.
3. [`03_nisar_pytools_search_and_snowin.ipynb`](03_nisar_pytools_search_and_snowin.ipynb) optionally searches/acquires a GUNW through `nisar-pytools`; network access and configured Earthdata credentials may be required.

Install Jupyter and notebook display tools with the `notebooks` dependency group:

```bash
python -m pip install -e ".[nisar,geometry,dask]" --group notebooks
```

The former SNOTEL workflow is preserved outside this sequence in `../research/` as downstream, unmaintained research material.
