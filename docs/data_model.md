# SnowIn data model

SnowIn represents one interferometric pair as an xarray `Dataset` on one
science grid. `open_gunw()` reads phase and product metadata. The returned
Dataset has the state value `phase_normalized_product`; `add_gunw_incidence()`
adds an `incidence_angle` variable and changes the state to
`retrieval_ready_pair`. Temporal accumulation takes an ordered sequence of
pair Datasets. This format describes pairwise and cumulative change, not an
absolute SWE map.

## Required dimensions and coordinates

A pair Dataset uses the dimensions `y` and `x` for its science grid.
Science-grid variables use dimension order `("y", "x")` and share the same
coordinates and CRS.

| Name | Role | Requirement |
| --- | --- | --- |
| `y` | row/cell-center coordinate | One-dimensional, finite, strictly monotonic, regularly spaced, and in the CRS coordinate units. |
| `x` | column/cell-center coordinate | One-dimensional, finite, strictly monotonic, regularly spaced, and in the CRS coordinate units. |

SnowIn preserves coordinate order. Check coordinate values to see whether
`x` or `y` increases or decreases; SnowIn does not flip arrays.

The Dataset also contains a scalar `spatial_ref` coordinate or variable. It
holds a CF-style CRS description, such as `crs_wkt` and/or `epsg_code`.
Science-grid variables have `grid_mapping="spatial_ref"` in their attributes
and must share dimensions, coordinate values, shape, and grid mapping. The
NISAR adapter may also retain the named `hydro_tropo` and `wet_tropo`
correction fields on their native `radar_y`/`radar_x` grid, optionally with a
`radar_height` dimension. Those adapter-owned fields have separate coordinates
and are not phase-grid variables; scientific kernels must not combine them
with phase until a caller explicitly maps them to a common grid.

The `x` and `y` coordinates are cell centers. Their `units` attribute names
the linear units of the declared CRS. A projected metre-based grid normally
uses `units="m"`. SnowIn does not convert coordinate units.

## Required Dataset attributes

The following attributes are required and must be scalar, serializable values:

| Attribute | Meaning |
| --- | --- |
| `snowin_schema_version` | SnowIn Dataset layout version, currently `"0.1"`. |
| `snowin_data_state` | `phase_normalized_product` before incidence is available; `retrieval_ready_pair` after incidence is added. |
| `product_kind` | `"pairwise_interferogram"`. |
| `reference_time` | Reference acquisition start time as an ISO 8601 UTC string with `Z` or a UTC offset. |
| `secondary_time` | Secondary acquisition start time as an ISO 8601 UTC string with `Z` or a UTC offset. |
| `temporal_edge` | Fixed value `"reference_to_secondary"`; this is the directed edge orientation. |
| `phase_difference_definition` | Required value `"secondary_minus_reference"`; see [phase conventions](scientific_conventions.md). |
| `wavelength_m` | Resolved radar wavelength in metres, positive and explicit. |

`reference_time` and `secondary_time` identify the phase roles. A valid
temporal pair has `secondary_time` later than `reference_time`. Generic
SnowIn inputs require explicit timezone information; SnowIn stores times in
UTC.

Source metadata commonly includes `source_product_type`,
`source_granule_id`, `source_phase_difference_definition`, `phase_transform`,
and serialized source dataset paths or processing history. For any Dataset
read from an external product, `source_phase_difference_definition` is
required and must name a convention SnowIn supports. `phase_transform` records
the conversion to the SnowIn phase convention. If the source convention is
missing or unsupported, the adapter raises an error; it never guesses the sign
from phase values.

For the NISAR/ISCE3 source convention:

```text
source phase = phi_reference - phi_secondary
SnowIn phase = phi_secondary - phi_reference = -source phase
phase_transform = "multiply_by_-1"
```

Product paths and mission metadata are Dataset attributes, not science
variables. Dataset attributes must be serializable; encode nested values as
JSON strings when needed.

The optional NISAR geometry adapter computes a local terrain-surface incidence
angle from a caller-prepared DEM and the GUNW radar-grid look vectors. SnowIn
recommends the [NISAR-modified Copernicus DEM](vertical_datums.md) for actual
NISAR local-incidence analysis. SnowIn does not acquire or cache DEMs. The
product's native ellipsoid-normal `incidenceAngle` is a distinct opt-in
geometry calculation and is not equivalent to terrain-local incidence. Local
geometry reprojects raster DEM input to the phase grid when needed and linearly
interpolates the LOS lookup; it records whether the DEM was already aligned or
reprojected. Product ellipsoid incidence reads only `incidenceAngle`,
`xCoordinates`, and `yCoordinates`, then records whether it was aligned or
resampled to the phase grid and the selected `radar_cube_index`. Both return
incidence on the exact phase grid. These are adapter operations; scientific
functions do not align or resample their inputs. The adapter records
DEM source, actual vertical datum, coordinate orientation, and source paths in
Dataset metadata. It also records the GUNW ellipsoidal height reference. An
already aligned DataArray is not described as resampled. With
`require_vertical_datum_match=True`, a DEM with unmatched heights requires an
explicit geoid-undulation correction.

## Required and optional variables

The pair Dataset requires `phase`. A retrieval-ready pair also requires
`incidence_angle` with explicit radians and an
`incidence_angle_reference` value of `local` or `ellipsoid`:

| Variable | Dimensions | Units | Meaning |
| --- | --- | --- | --- |
| `phase` | `("y", "x")` | `rad` | Unwrapped interferometric phase for the directed pair, with its sign defined by `phase_difference_definition`. |
| `incidence_angle` | `("y", "x")` | `rad` | Required only for retrieval-ready pairs; its `incidence_angle_reference` is `"ellipsoid"` or `"local"`. |

`wavelength_m` is a Dataset attribute because it is a scalar property of this
pair. An adapter must read it from authoritative metadata or an explicit
caller value before a scientific function runs. SnowIn does not use an
approximate mission fallback.

The NISAR GUNW adapter retains correction screens on their source grids. The
ionosphere fields share the unwrapped-phase `y`/`x` grid. Hydrostatic and wet
tropospheric screens use separate `radar_height`/`radar_y`/`radar_x`
dimensions because their native radar grid may have a different resolution.
The adapter exposes these fields for inspection but does not apply them.
Callers who apply a correction screen must handle its units and sign and
explicitly align it with the phase grid.

The following variables are optional and retain distinct scientific roles:

| Variable | Units/type | Role |
| --- | --- | --- |
| `coherence` | dimensionless float | Coherence diagnostic; it is not itself a universal validity mask. |
| `connected_component` | integer label | Product connected-component identity; label values must not be collapsed into a dominant-component assumption. |
| `ionosphere` | `("y", "x")`, radians | GUNW ionospheric phase screen on the unwrapped-interferogram grid; exposed as a correction input and never applied automatically. |
| `ionosphere_unc` | `("y", "x")`, radians | Uncertainty reported for the ionospheric phase screen. |
| `hydro_tropo` | `("radar_y", "radar_x")` or `("radar_height", "radar_y", "radar_x")`, radians | Hydrostatic tropospheric phase screen on the native radar grid. |
| `wet_tropo` | `("radar_y", "radar_x")` or `("radar_height", "radar_y", "radar_x")`, radians | Wet tropospheric phase screen on the native radar grid. |
| `product_valid` | boolean | Whether product support/validity is known for the sample. Absence means unknown, not valid. |
| `geometry_valid` | boolean | Whether the selected incidence angle is finite and in `[0, pi/2)`; false samples have missing incidence and are excluded from dSWE. |
| `reference_supported` | boolean | Whether the sample has support for a declared reference operation. |
| `temporal_path_supported` | boolean | Whether a cumulative result has a complete supported path. |
| `evaluation_supported` | boolean | Whether independent evaluation data support the sample. |
| `snow_state_supported` | boolean | Whether declared snow-state evidence supports the sample. |
| `coherence_valid` | boolean | A separately defined coherence criterion, when one is needed. |
| `pairwise_supported` | boolean | Explicit support for the pairwise dSWE edge at each sample; temporal accumulation combines this with finite dSWE and never treats unsupported samples as zero. |

Reference-phase outputs are optional and are not implicit quality masks:

| Variable | Dimensions | Meaning |
| --- | --- | --- |
| `phase_referenced` | `("y", "x")` | Phase using the SnowIn convention after subtraction of the explicitly estimated reference offset, in radians. It remains missing when reference estimation is unsupported. |
| `reference_estimate_supported` | scalar | Whether the global reference estimate is supported for the pair. Its `scope` attribute identifies it as a reference-estimate status, not a pixelwise validity mask. The separate optional `reference_supported` variable remains available for spatial support. |

An auditable reference estimate may also carry a
`reference_contributor` dimension containing observed phase, expected phase,
weight, residual, weighted contribution, eligibility, exclusion reason, and
contributor ID. These variables preserve how the scalar offset was estimated;
they must not be collapsed into one undocumented scalar or universal mask.

Support variables are optional because an upstream product may not provide
that kind of evidence. When present, they have dimensions `("y", "x")` and
must not be silently combined into a variable named `quality_mask`.

Optional phase-screen or ancillary variables use their own documented names
and units. For example, an ionospheric phase screen is a phase quantity in
radians; it is not automatically applied merely because it is present.

## Missing data and absent layers

Keep these cases distinct:

1. **Missing information:** a variable is absent, or a sample has no value.
   SnowIn does not create an all-NaN placeholder for an absent variable.
   Floating-point physical variables use `NaN` for missing samples.
2. **Invalid value:** a supplied value violates a requirement, such as valid
   angle range or units. Validation raises an error or, for geometry samples
   without usable support, returns `NaN` with a false support variable.
3. **Unsupported value or operation:** the input may be valid, but SnowIn does
   not implement that convention or calculation. SnowIn reports the limitation
   instead of guessing how to handle it.

If a product provides a fill value, the adapter may decode it to the
in-memory missing representation while preserving the source encoding in
metadata. `_FillValue` is an I/O encoding detail, not a scientific value.

No support variable is implicitly created with all `True` values. If support
evidence is absent, support is unknown. A false support value means the sample
is known to be unsupported.

Support helpers preserve these variables as named xarray layers. Combine
support variables only when the caller names them. Give the resulting mask
its own name; SnowIn does not create a universal `quality_mask`.
Support summaries distinguish supported samples from known samples so unknown
evidence is not silently counted as false or true.

## Dask-backed arrays

Use `open_gunw(chunks=...)` to keep GUNW variables Dask-backed. Phase-to-dSWE
retrievals, support composition, and temporal accumulation preserve Dask
arrays and remain lazy. Call `.compute()` when you need their values in
memory. A reference estimate computes the contributor reduction needed for
its scalar offset; the referenced phase raster can remain lazy. Local
incidence is eager by default; `geometry_chunks` requests the optional
chunked calculation when Dask is installed.

## CRS and grid checks

Before a scientific operation uses multiple spatial variables, check that:

1. science-grid `y` and `x` are one-dimensional, finite, monotonic, and regularly spaced;
2. every variable entering the same science operation uses the same declared grid;
3. coordinate values and shapes are aligned, rather than merely having equal
   array shapes;
4. all spatial variables reference the same `spatial_ref` mapping;
5. CRS information is present and parseable through a standard representation;
6. no reprojection, resampling, or shape-based broadcasting is performed
   implicitly.

Grid incompatibility is an error. Reproject or resample explicitly before
combining science variables, and record that operation in Dataset metadata.
The incidence adapter may perform a named grid conversion and records what it
did before returning incidence on the phase grid.

## Reference and temporal output metadata

A reference-phase result retains the method, offset and units, contributors,
observations, weights, exclusions, support, and status. A temporal result
retains the input edge order, path interval, missing-support handling, and
support at each endpoint. These values remain available in the returned
xarray object. The `phase_reference_estimate_details` attribute records the
reference method, offset, status, and number of eligible contributors.
