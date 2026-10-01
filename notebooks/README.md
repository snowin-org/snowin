# SnowIn notebooks

1. [`01_core_snowin_workflow.ipynb`](01_core_snowin_workflow.ipynb) introduces the synthetic xarray science using the base NumPy/xarray dependencies.
2. [`02_real_nisar_gunw_workflow.ipynb`](02_real_nisar_gunw_workflow.ipynb) opens the bundled cropped GUNW sample for an out-of-the-box adapter demonstration using product ellipsoid incidence. For NISAR snow science, set `SNOWIN_GUNW` and `SNOWIN_NISAR_DEM` to a real product and matching NISAR-modified Copernicus DEM for terrain-local incidence; install the `nisar`, `geometry`, and `dask` extras.
3. [`03_nisar_pytools_search_and_snowin.ipynb`](03_nisar_pytools_search_and_snowin.ipynb) optionally searches/acquires a GUNW through `nisar-pytools`; network access and configured Earthdata credentials may be required.

Install Jupyter and notebook display tools with the `notebooks` dependency group:

```bash
python -m pip install -e ".[nisar,geometry,dask]" --group notebooks
```

The bundled GUNW crop is an official ASF sample for format and adapter
demonstration. It is not a production snow-science scene, so its dSWE output is
not a scientific result. Source metadata and crop details are in
[`data/README.md`](data/README.md).
