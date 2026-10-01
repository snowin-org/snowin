# Real-product geometry fixture

The JSON manifest in this directory records the expected local-incidence
statistics for a real NISAR GUNW and a public Copernicus GLO-30 tile. The
large HDF5 and GeoTIFF inputs are intentionally not committed to SnowIn.

Set these variables to run the regression test:

```bash
export SNOWIN_GEOMETRY_GUNW=/path/to/NISAR_L2_PR_GUNW_006_019_A_020_008_4000_SH_20251123T121042_20251123T121117_20251217T121043_20251217T121118_X05010_N_F_J_001.h5
export SNOWIN_GEOMETRY_COP30_DEM=/path/to/Copernicus_DSM_COG_10_N36_00_W106_00_DEM.tif
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

`colorado_phase_lineage.json` is a small data-free characterization fixture.
It records the raw-versus-canonical phase definitions and the frozen
downstream `phase_sign=+1` branch so the sign-lineage regression does not
depend on a private Colorado checkout or a large product.

## Optional real NISAR product checks

The real-product tests are opt-in and never download data or require credentials
for the normal test suite. Supply your own ASF-distributed NISAR L2 GUNW product
and matching DEM when running the checks. The product collection is documented
at [ASF DAAC NISAR L2 GUNW](https://doi.org/10.5067/NIL2GUNW-P1). The phase-lineage
check reads the HH, frequencyA `unwrappedPhase` dataset and expects phase units
of radians and a WGS84 description on the radar-grid height coordinate. The
vertical-datum check expects a local DEM covering the GUNW scene; it verifies
that strict geometry processing asks for an explicit vertical correction when
the Copernicus DEM height reference is not declared as ellipsoidal. The test
does not assert a mission-wide numerical SWE result.

```bash
export SNOWIN_REAL_GUNW=/path/to/ASF_NISAR_L2_GUNW.h5
export SNOWIN_REAL_COP30_DEM=/path/to/copernicus_dem_covering_scene.tif
pytest -m integration -q tests/test_real_product_validation.py
```

The separate `SNOWIN_GEOMETRY_GUNW` and `SNOWIN_GEOMETRY_COP30_DEM` variables
run the exact scene geometry regression described above. Its expected
statistics and input granule name are frozen in `real_product_geometry.json`;
the public DEM tile URL and independent Colorado implementation commit used to
establish those values are recorded in this guide. These values are a
characterization/regression reference, not an independent SWE validation.
