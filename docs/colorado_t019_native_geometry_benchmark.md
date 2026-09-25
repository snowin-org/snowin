# Colorado T019/F021 native NISAR DEM benchmark

This benchmark characterizes the full 23-edge Colorado path using SnowIn's
native geometry workflow:

```text
open_gunw(product)
    -> add_gunw_incidence(product, nisar_cop30_dem=...)
    -> reference_phase(..., method="manual_offset")
    -> compute_dswe(..., wavelength_m=product.attrs["wavelength_m"])
```

The benchmark was run with eager NumPy arrays (`chunks=None`) because geometry
currently materializes the DEM, LOS vectors, terrain normals, and incidence
grid. Peak memory is the process maximum RSS, so it is a conservative measure
that grows as the long-lived process reaches a new high-water mark.

## Results

| Metric | Result across 23 edges |
| --- | ---: |
| Geometry runtime | `9.49–10.37 s` per edge; mean `9.67 s` |
| Process high-water RSS | `7.2–13.5 GiB` high-water mark |
| Finite geometry fraction | `0.999203` |
| Valid `0–90°` geometry fraction | `0.998975` |
| dSWE support fraction | `0.415307–0.515655` |
| DEM source | `nisar_cop30` / Modified Copernicus DEM for NISAR |
| Wavelength | `0.2419632429378531 m` for every product |
| Wavelength source | GUNW `centerFrequency` metadata via `c/f` |

The run completed all 23 edges without changing the canonical phase lineage or
silently substituting a different DEM. The memory result supports keeping
geometry eager for now while treating chunk-aware/Dask geometry as a later
optimization target if larger products or multiple simultaneous edges require
it.

The per-edge measurements are preserved in
[`colorado_t019_native_geometry_benchmark.csv`](colorado_t019_native_geometry_benchmark.csv).

## Wavelength policy

SnowIn's native default is product-derived wavelength. Colorado reproduction is
different: it must pass the frozen study value explicitly:

```python
pair = open_gunw(product, wavelength_m=0.238403545)
```

No conversion between the product-derived and Colorado-frozen values is
performed implicitly. The controlled 23-edge comparison uses the explicit
Colorado value and downstream incidence; this native benchmark uses the
product-derived value and NISAR DEM geometry. Those are intentionally separate
scientific comparisons.
