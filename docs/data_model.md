# Provisional data model

SnowIn uses xarray as the primary scientific data model for normalized product
and retrieval objects. Scientific functions should generally accept and return
`xarray.DataArray` or `xarray.Dataset` while preserving dimensions,
coordinates, relevant attributes, CRS information, missing-data semantics,
and lazy-array behavior when supported by the input.

The current prototype is not yet a complete normalized schema:

- the GUNW reader returns a `GunwLayers` dataclass containing named
  `xarray.DataArray` layers and metadata;
- the raster dSWE workflow currently returns NumPy arrays plus diagnostics;
- missing product layers are represented explicitly as `None`;
- valid samples, geometry support, connected components, reference support,
  temporal support, and evaluation support are not yet one unified mask.

This is intentional. Stage 1 will define the retrieval-ready dimensions,
coordinate names, required variables, units, nodata behavior, CRS rules, and
metadata/provenance fields. No `SnowScene`, `SnowStack`, or `SnowProduct`
hierarchy is introduced until xarray objects demonstrably cannot express a
required behavior cleanly.
