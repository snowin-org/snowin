# SnowIn notebooks

1. [`01_core_snowin_workflow.ipynb`](01_core_snowin_workflow.ipynb) demonstrates
   the synthetic Xarray workflow with NumPy and Xarray.
2. [`02_real_nisar_gunw_workflow.ipynb`](02_real_nisar_gunw_workflow.ipynb)
   reads the bundled GUNW crop and uses its ellipsoid incidence. For
   terrain-local incidence, set `SNOWIN_GUNW` and `SNOWIN_NISAR_DEM` to a
   matching product and NISAR-modified Copernicus DEM, and install the
   `nisar`, `geometry`, and `dask` extras.
3. [`03_nisar_pytools_search_and_snowin.ipynb`](03_nisar_pytools_search_and_snowin.ipynb)
   shows an optional GUNW search and download through `nisar-pytools`; it may
   need network access and Earthdata credentials.

Install Jupyter and notebook display tools with the `notebooks` dependency group:

```bash
python -m pip install -e ".[nisar,geometry,dask]" --group notebooks
```

The bundled GUNW crop is an official ASF sample for format and adapter
demonstration. It is not a production snow-science scene, so its dSWE output is
not a scientific result. Source metadata and crop details are in
[`data/README.md`](data/README.md).
