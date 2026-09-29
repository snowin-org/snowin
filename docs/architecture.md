# SnowIn architecture

SnowIn owns the reusable snow-InSAR retrieval science. Its base install is
NumPy and xarray; optional features are limited to a NISAR GUNW adapter,
NISAR local-incidence geometry, and Dask support.

## Package boundary

The science API accepts labeled DataArray and Dataset inputs. A retrieval-ready
pair carries canonical phase direction, acquisition order, wavelength,
incidence angle and units, coordinates, CRS, support, and provenance. SnowIn
preserves those labels and missing-data behavior through dSWE retrieval,
reference operations, support composition, corrections, metrics, and directed
temporal accumulation.

SnowIn is not a general SAR processor, catalog, credential manager,
ancillary-data service, plotting package, GIS file utility, or study-validation
framework. It does not select stations, acquisition windows, AOIs, thresholds,
or validation policy.

## Data-source composition

Different products and ancillary sources meet at the normalized xarray
boundary:

    mission reader and caller-prepared data
                  |
                  v
    thin product adapter -> normalized xarray pair
                  |
                  v
    SnowIn retrieval science -> pairwise or accumulated dSWE
                  |
                  v
    study workflow adds reference data, support policy, validation, and output

The NISAR adapter reads local GUNW files through nisar-pytools and applies
SnowIn's documented phase normalization. The optional local-incidence
calculation reads GUNW LOS geometry and requires a prepared DEM. SnowIn does
not fetch DEMs, station observations, ASO, lidar, or other ancillary data.

Search and download wrappers were removed because they only forwarded calls
to nisar-pytools. S3 staging, vector-mask preparation, general raster export,
and specialized GUNW reports now belong in examples or companion workflows.
The repository keeps its study notebooks and workflow helpers; they are not
installed as SnowIn runtime modules.

## Dependency scope

The base package declares NumPy and xarray. Optional extras declare only
maintained library capabilities:

- nisar: nisar-pytools and HDF5 support for local GUNW reading;
- geometry: PyProj, Rasterio, and SciPy for the NISAR local-incidence path;
- dask: lazy, chunked array support.

Notebook, docs, and development requirements use dependency groups. The
repository's full Conda environment can include Matplotlib, GeoPandas, Shapely,
Earthaccess, fsspec, s3fs, and other tools needed by its study workflows; those
do not become SnowIn package runtime requirements.

Fewer optional runtime dependencies mean fewer transitive combinations the
package must document and validate. Pip explains that dependency resolution
explores transitive requirements and may backtrack when version choices
conflict. The maintenance benefit of dropping unneeded dependencies is an
inference from that resolver model, not a guarantee that every installation
will be faster. See the
[pip dependency-resolution guide](https://pip.pypa.io/en/stable/topics/dependency-resolution/).

For routine plots, xarray's DataArray.plot selects common plots from array
dimensions and coordinates. It uses Matplotlib, which belongs in the notebook
or workflow environment rather than SnowIn's base requirements. See the
[xarray plotting API](https://docs.xarray.dev/en/latest/generated/xarray.DataArray.plot.html)
and [xarray installation guide](https://docs.xarray.dev/en/stable/installing.html).
