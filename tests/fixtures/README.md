# Stage 4 real-product geometry fixture

The JSON manifest in this directory records the expected local-incidence
statistics for a real NISAR GUNW and a public Copernicus GLO-30 tile. The
large HDF5 and GeoTIFF inputs are intentionally not committed to SnowIn.

Set these variables to run the regression test:

```bash
export SNOWIN_STAGE4_GUNW=/path/to/NISAR_L2_PR_GUNW_006_019_A_020_008_4000_SH_20251123T121042_20251123T121117_20251217T121043_20251217T121118_X05010_N_F_J_001.h5
export SNOWIN_STAGE4_COP30_DEM=/path/to/Copernicus_DSM_COG_10_N36_00_W106_00_DEM.tif
pytest -q tests/test_geometry.py::test_real_product_geometry_regression
```

The COP30 input is the public AWS tile:

```text
https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N36_00_W106_00_DEM/Copernicus_DSM_COG_10_N36_00_W106_00_DEM.tif
```

See the [Copernicus DEM Product Handbook](https://dataspace.copernicus.eu/sites/default/files/media/files/2024-06/geo1988-copernicusdem-spe-002_producthandbook_i5.0.pdf)
for product reference-system and grid semantics. The expected values were
generated independently with the verified Colorado implementation at commit
`f5c17ef`; no ASO data was used for tuning.
