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
