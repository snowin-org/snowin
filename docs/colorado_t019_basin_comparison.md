# Colorado T019/F021 basin-matched comparison

This comparison applies the actual Colorado East River Basin (ERB) and Taylor
River polygons to the first real `T019_F021` GUNW edge before comparing SnowIn
native geometry with the retained Colorado incidence raster. Colorado's
GeoPackage layers were:

- `erb.gpkg`, layer `erb`;
- `taylor.gpkg`, layer `taylor_river_below_taylor_park_reservoir_nldi_basin`.

SnowIn used the NISAR-modified Copernicus DEM and GUNW LOS geometry. The
controlled comparison used the Colorado incidence raster, the same normalized
SnowIn phase, the same reference offset, and frozen wavelength
`0.238403545 m`. Native product comparisons used the GUNW-derived wavelength
`0.2419632429378531 m`.

## Incidence comparison

Metrics use pixels inside the basin where both incidence fields are finite and
within the valid `[0, 90°)` domain.

| Region | Pixels | Basin fraction | Common valid fraction | Pearson r | Bias [°] | MAE [°] | RMSE [°] | P95 abs. error [°] | Max abs. error [°] |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| East River | 116,983 | 0.006102 | 0.999778 | 0.999183 | 0.003115 | 0.388765 | 0.576661 | 1.182692 | 5.626328 |
| Taylor River | 102,843 | 0.005365 | 1.000000 | 0.999110 | -0.001447 | 0.347622 | 0.505080 | 1.013198 | 5.885560 |

The two geometry fields agree very closely inside both actual study areas. The
full-scene coverage difference was therefore primarily an analysis-footprint
difference, not a broad disagreement in incidence geometry.

## dSWE comparison

The following values compare SnowIn native dSWE against controlled Colorado
dSWE. Bias, MAE, RMSE, and P95 are in millimetres. The product-wavelength row
includes both the geometry and wavelength-policy difference. The frozen-
wavelength row isolates the geometry difference more closely.

| Region | Native wavelength | Native support | Controlled support | Bias [mm] | MAE [mm] | RMSE [mm] | P95 abs. error [mm] | Max abs. error [mm] |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| East River, product wavelength | 0.241963243 | 0.941863 | 0.941855 | -0.138299 | 0.249107 | 1.046675 | 0.347112 | 24.246307 |
| East River, frozen wavelength | 0.238403545 | 0.941863 | 0.941855 | 0.001824 | 0.090132 | 0.567979 | 0.147274 | 27.589081 |
| Taylor River, product wavelength | 0.241963243 | 1.000000 | 1.000000 | -0.133715 | 0.184349 | 0.294662 | 0.684479 | 2.857627 |
| Taylor River, frozen wavelength | 0.238403545 | 1.000000 | 1.000000 | -0.000587 | 0.056099 | 0.118520 | 0.235350 | 2.488892 |

The wavelength choice creates a consistent approximately `0.13 mm` mean shift
in this edge. With the frozen wavelength, the mean dSWE bias is effectively
zero in both basins; the remaining difference is the local-incidence geometry.
The large maxima are localized pixels and should be investigated with residual
maps and support/provenance layers rather than summarized by the mean alone.

The higher native product-wavelength residual is expected rather than evidence
that the GUNW metadata is incorrect. SnowIn resolves `0.241963243 m` from the
GUNW center-frequency metadata, while Colorado's historical reproduction uses
`0.238403545 m`. Because the dSWE kernel is linear in wavelength, the product
value scales dSWE by approximately `1.493%` relative to the frozen value. That
small per-edge scaling becomes more visible after 23 temporal edges have been
accumulated. The frozen-wavelength native run therefore isolates the geometry
difference, while the product-wavelength native run intentionally includes
both geometry and wavelength-policy differences. SnowIn should retain the
product-derived default and require an explicit wavelength override for
historical Colorado reproduction.

## Decision

These basin-matched results support SnowIn as the forward-looking framework:

- SnowIn's NISAR DEM incidence is numerically consistent with Colorado's
  incidence over both target basins.
- SnowIn provides substantially broader full-scene geometry coverage.
- Product-derived wavelength and frozen Colorado wavelength are both
  reproducible when selected explicitly.
- Basin masks should remain explicit analysis-region layers and should not be
  folded into phase normalization, station selection, or connected-component
  policy.

The next Colorado migration comparison should use these basin masks for all
regional metrics. `gunw_to_dswe()` should remain unchanged until Colorado
chooses its phase, wavelength, reference-offset, and geometry policies
explicitly.

## 23-edge basin-aware path

The full 23-edge path was then run with
`scripts/run_t019_basin_comparison.py`. Every edge used the same explicit
SnowIn phase normalization and the corresponding Colorado reference offset.
The controlled mode used the Colorado incidence raster and frozen wavelength;
the native mode used SnowIn's NISAR-modified Copernicus DEM and product-derived
wavelength; and the native-frozen mode used SnowIn geometry with the frozen
wavelength. The run took 274.9 seconds, or about 11.0 seconds per edge. Peak
memory was not instrumented in this run; processing was sequential and only
basin crops were retained for temporal accumulation.

The following are means over the 23 edges. They describe the general
agreement, not a request to standardize the small workflow differences yet.

| Region | Incidence r | Incidence MAE [°] | Incidence RMSE [°] | Native support | Controlled support | Product-wavelength dSWE MAE [mm] | Frozen-wavelength dSWE MAE [mm] |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| East River | 0.999183 | 0.388758 | 0.576673 | 0.997127 | 0.997126 | 0.352365 | 0.117802 |
| Taylor River | 0.999110 | 0.347653 | 0.505082 | 1.000000 | 1.000000 | 0.297513 | 0.090337 |

At the final cumulative endpoint, controlled SnowIn reproduces the downstream
Colorado cumulative raster to numerical precision after accounting for the
opposite sign convention: SnowIn plus Colorado equals the residual. Native
geometry and product wavelength retain the expected small differences:

| Region/mode | Final support of region | Residual MAE [mm] | Residual RMSE [mm] |
| --- | ---: | ---: | ---: |
| East River, controlled | 0.941855 | 0.000004 | 0.000005 |
| East River, native product wavelength | 0.941863 | 0.990665 | 1.831762 |
| East River, native frozen wavelength | 0.941863 | 0.336787 | 0.917488 |
| Taylor River, controlled | 1.000000 | 0.000003 | 0.000004 |
| Taylor River, native product wavelength | 1.000000 | 0.523624 | 0.817440 |
| Taylor River, native frozen wavelength | 1.000000 | 0.167989 | 0.362037 |

This is sufficient as a practical migration baseline: the canonical SnowIn
workflow reproduces Colorado's regional cumulative result when the controlled
inputs are held fixed, while the native path remains highly correlated and
shows the magnitude of the deliberate DEM/incidence and wavelength differences.
The machine-readable report is written to
`/private/tmp/snowin-colorado-comparison/t019_basin_full_comparison.json` for
the local product checkout.
