# Preparing analysis-region masks in workflows

SnowIn's retrieval functions consume aligned xarray masks and arrays. They do
not read vectors or choose a study region. Load and rasterize GeoPackages,
Shapefiles, or GeoJSON in the study workflow, then pass the resulting boolean
DataArray into support composition.

The Colorado comparison script uses a repository-owned helper:

    from scripts.study_utils.spatial import rasterize_vector_mask

    pair["analysis_region"] = rasterize_vector_mask(
        "regions.gpkg",
        target=pair,
        layer="basin",
        name="analysis_region",
    )

That helper is study-workflow code and is not installed as part of SnowIn.
Other projects can use their established GIS stack, such as GeoPandas and
Rasterio, to create a mask on the target coordinates. The mask should have the
same dimensions and coordinates as the retrieval arrays and should carry an
explicit CRS. SnowIn will not reproject or silently align it inside the
scientific kernel.

The analysis-region mask is an input to caller-defined support, not a
universal SnowIn quality policy. Coherence thresholds, connected-component
selection, basin boundaries, and other study rules remain explicit in the
workflow.
