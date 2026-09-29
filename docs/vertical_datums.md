# DEM vertical datums

NISAR GUNW radar-grid heightAboveEllipsoid values use WGS84 ellipsoidal
heights. The NISAR-modified Copernicus DEM is re-referenced to the WGS84
ellipsoid. Public Copernicus GLO-30 values are EGM2008 orthometric heights.
Horizontal reprojection does not change a DEM's vertical reference.

SnowIn computes local incidence from the GUNW LOS vectors and a caller-supplied
prepared DEM. It does not discover, download, mosaic, or cache DEM tiles. The
dem_source argument declares the prepared product and its expected vertical
datum:

- nisar_cop30: NISAR-modified Copernicus DEM, ellipsoidal;
- cop30: Copernicus GLO-30, orthometric;
- tandem30: TanDEM-X 30 m, WGS84-G1150 ellipsoidal;
- srtm30: SRTM 30 m, normally EGM96 orthometric.

Pass the prepared file or same-grid DataArray through dem. For example:

    add_gunw_incidence(
        pair,
        gunw_path,
        dem="/data/nisar_modified_cop30.tif",
        dem_source="nisar_cop30",
        require_vertical_datum_match=True,
    )

For orthometric input, provide an appropriate vertical correction through
dem_vertical_correction_m. SnowIn applies h = H + N before LOS interpolation
and records the correction source in output metadata. Set
require_vertical_datum_match=True to fail rather than proceed with unmatched
vertical datums.

The source label is part of the scientific input contract; it does not verify
external DEM provenance. The workflow must record where its prepared file came
from, its coverage, CRS, resolution, no-data handling, and vertical datum.

References:

- [Copernicus DEM processing documentation](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/DEM.html)
- [NISAR modified Copernicus DEM documentation](https://hyp3-docs.asf.alaska.edu/nisar-docs/nisar-dem/)
- [TanDEM-X DEM product specification](https://tandemx-science.dlr.de/pdfs/TD-GS-PS-0021_DEM-Product-Specification_v3.1.pdf)
