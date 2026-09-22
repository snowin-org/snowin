# DEM vertical datums

NISAR GUNW radar-grid `heightAboveEllipsoid` values are WGS84 ellipsoidal
heights. The original public Copernicus DEM tiles exposed by SnowIn's
compatibility AWS download path are EGM2008 orthometric heights. Horizontal
reprojection does not change that vertical reference.

The default SnowIn source is the modified Copernicus DEM distributed for NISAR.
It is derived from Copernicus GLO-30, re-referenced from EGM2008 to the WGS84
ellipsoid, and is therefore the preferred source for GUNW geometry.

There are two supported scientific routes for the default path:

1. Let `add_gunw_incidence()` download and cache the NISAR DEM with
   `dem_source="nisar_cop30"` (the default), or provide a local raster with
   `nisar_cop30_dem=...`. `open_gunw()` itself only opens the product for
   inspection.
2. Select raw `dem_source="cop30"` and provide an EGM2008 geoid undulation
   raster or same-grid xarray DataArray through
   `dem_vertical_correction_m`. SnowIn applies `h = H + N` before LOS
   interpolation and records the correction source in the output metadata.

TanDEM-X 30 m (or 90 m) is a possible independent ellipsoidal-height
cross-check. Select a local TanDEM-X 30 m raster with
`dem_source="tandem30"` and `tandem30_dem=...`. SRTM 30 m can likewise be
selected with `dem_source="srtm30"` and `srtm30_dem=...`, but it is treated as
orthometric (normally EGM96) and therefore needs an appropriate geoid
correction for strict matching. Neither source is silently substituted for the
Colorado COP30 workflow.

These alternatives are intentionally not part of the current default. They
remain future extension points after the NISAR DEM path is validated on the
Colorado workflow.

When a correction or ellipsoidal export is unavailable, set
`require_vertical_datum_match=True` so the workflow fails instead of presenting
provisional geometry as datum-matched geometry.

References:

- [Copernicus DEM processing documentation](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/DEM.html)
- [NISAR modified Copernicus DEM documentation](https://hyp3-docs.asf.alaska.edu/nisar-docs/nisar-dem/)
- [TanDEM-X DEM product specification](https://tandemx-science.dlr.de/pdfs/TD-GS-PS-0021_DEM-Product-Specification_v3.1.pdf)
