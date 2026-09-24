# Vector-defined analysis regions

SnowIn treats vector-defined study areas as explicit analysis-region masks.
They are separate from phase validity, incidence geometry support, connected
components, and temporal support.

```python
from snowin.spatial import rasterize_vector_mask

pair["analysis_region"] = rasterize_vector_mask(
    "data/vectors/erb.gpkg",
    target=pair,
    layer="erb",
)
```

`rasterize_vector_mask` accepts GeoPackages, Shapefiles, GeoJSON, GeoDataFrames,
Shapely geometries, and geometry iterables. File-backed vector inputs require
the optional `vectors` dependencies (`python -m pip install -e ".[vectors]"`).
The function reprojects geometries into
the target grid CRS and returns an aligned boolean `xarray.DataArray`.

The default `all_touched=False` policy uses pixel-center inclusion. Set
`all_touched=True` only when the study explicitly requires boundary-touching
pixels. The output records source path, layer, feature count, source/target
CRS, and rasterization settings in its attributes.

## Mask roles

Keep these layers separate:

- `analysis_region`: whether the pixel is inside the study polygon;
- `geometry_support`: whether incidence is finite and in the valid domain;
- `retrieval_support`: phase, geometry, and declared quality support;
- connected-component and provenance layers.

Compose them explicitly for a regional retrieval or metric. The vector mask
does not change phase normalization, reference-offset estimation, station
selection, or missing-value semantics. It should be applied to regional dSWE
products, support summaries, plots, metrics, and optional final maps.
