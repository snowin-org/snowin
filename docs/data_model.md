# SnowIn normalized data model

A normalized product is an xarray Dataset for one directed pair on a science
grid. `open_gunw()` returns normalized phase; incidence geometry is added in a
separate operation to produce a retrieval-ready pair. Temporal accumulation
accepts an explicit sequence of directed pair Datasets; this contract does not
describe a stack or absolute SWE product.

## Required dimensions and coordinates

A phase-normalized product and retrieval-ready pair share the same x/y science
grid, CRS, temporal direction, normalized phase, wavelength, and source metadata.
The `snowin_data_state` attribute is `phase_normalized_product` before
incidence is calculated and `retrieval_ready_pair` afterward. The normalized
science grid has exactly two dimensions:

| Name | Role | Contract |
| --- | --- | --- |
| `y` | row/cell-center coordinate | One-dimensional, finite, strictly monotonic, regularly spaced, and in the CRS coordinate units. |
| `x` | column/cell-center coordinate | One-dimensional, finite, strictly monotonic, regularly spaced, and in the CRS coordinate units. |

Science-grid variables use dimension order `("y", "x")`. The coordinate
order is preserved from the source; consumers must not assume that `y`
increases or decreases without checking it. SnowIn does not silently flip
arrays.

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
uses `units="m"`; the contract does not silently convert another CRS unit.

## Required Dataset attributes

The following attributes are required and must be scalar, serializable values:

| Attribute | Meaning |
| --- | --- |
| `snowin_schema_version` | Frozen normalized contract version `"0.1"`. |
| `snowin_data_state` | `phase_normalized_product` before incidence is available; `retrieval_ready_pair` after incidence is added. |
| `product_kind` | `"pairwise_interferogram"` for this contract. |
| `reference_time` | Reference acquisition start time as an ISO 8601 UTC string with `Z` or a UTC offset. |
| `secondary_time` | Secondary acquisition start time as an ISO 8601 UTC string with `Z` or a UTC offset. |
| `temporal_edge` | Fixed value `"reference_to_secondary"`; this is the directed edge orientation. |
| `phase_difference_definition` | Required value `"secondary_minus_reference"`; see [phase conventions](scientific_conventions.md). |
| `wavelength_m` | Resolved radar wavelength in metres, positive and explicit. |

`reference_time` and `secondary_time` identify product roles. The name
`reference` does not by itself mean “earlier in time”. SnowIn requires explicit
timezone information, normalizes times to UTC, and rejects a pair whose
secondary acquisition is not later than its reference acquisition.

Recommended source metadata attributes include `source_product_type`,
`source_granule_id`, `source_phase_difference_definition`,
`phase_transform`, and serialized source dataset paths or processing history.
For any Dataset adapted from an external product,
`source_phase_difference_definition` is required and must be a recognized
source convention. `phase_transform` is required and must explicitly state
the conversion to the SnowIn phase convention. Missing or unknown source conventions
are errors; an adapter must never guess them from phase values.

For the NISAR/ISCE3 source convention used by this contract:

```text
source phase = phi_reference - phi_secondary
SnowIn phase = -source phase
phase_transform = "multiply_by_-1"
```

Product-specific paths and mission metadata remain adapter source metadata, not
scientific variable names.
Attributes must remain serializable; nested Python objects should be encoded
as JSON strings when persistence requires it.

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
incidence on the exact phase grid. These are documented adapter operations;
scientific functions do not align or resample their inputs. The adapter records
DEM source, actual vertical datum, coordinate orientation, and source paths in
Dataset metadata. It also records the GUNW ellipsoidal height reference. An
already aligned DataArray is not described as resampled. With
`require_vertical_datum_match=True`, a DEM with unmatched heights requires an
explicit geoid-undulation correction.

## Required and optional variables

The phase-normalized product requires `phase`. The retrieval-ready pair also
requires `incidence_angle` with explicit radians and an
`incidence_angle_reference` value of `local` or `ellipsoid`:

| Variable | Dimensions | Units | Meaning |
| --- | --- | --- | --- |
| `phase` | `("y", "x")` | `rad` | Unwrapped interferometric phase for the directed pair, with its sign defined by `phase_difference_definition`. |
| `incidence_angle` | `("y", "x")` | `rad` | Required only for retrieval-ready pairs; its `incidence_angle_reference` is `"ellipsoid"` or `"local"`. |

`wavelength_m` is a Dataset attribute because it is a scalar property of this
pair. An adapter must resolve it from authoritative metadata or an explicit
caller value before a scientific kernel runs. The normalized contract does
not permit a silent approximate mission fallback.

The NISAR GUNW adapter retains correction screens on their source grids. The
ionosphere fields share the unwrapped-phase `y`/`x` grid. Hydrostatic and wet
tropospheric screens use separate `radar_height`/`radar_y`/`radar_x`
dimensions because their native radar grid may have a different resolution.
The adapter exposes these fields for inspection but does not apply them. A
general correction function is outside the current package contract because
correction units, signs, and native-grid alignment require explicit scientific
decisions.

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
| `coherence_valid` | boolean | A separately declared coherence-support policy, when one is needed. |
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

SnowIn distinguishes two cases that must not be conflated:

1. **Absent product layer:** the variable is not present in the Dataset. No
   all-NaN placeholder is created, and downstream code must treat support for
   that layer as unknown.
2. **Invalid or missing sample:** the variable is present, but a sample is
   missing or invalid. Floating-point physical variables use `NaN` in memory;
   integer labels use an explicit missing-value convention plus a separate
   support variable where needed. A known invalid sample must never be changed
   to zero.

If a product provides a fill value, the adapter may decode it to the
in-memory missing representation while preserving the source encoding in
metadata. `_FillValue` is an I/O encoding detail, not a scientific value.

No support variable is implicitly created with all `True` values. Absence of
support evidence means unknown support.

Support helpers preserve these variables as named xarray layers. A
derived conjunction is allowed only when the caller explicitly names its
components; it is recorded as a policy and is not stored as a universal
`quality_mask`. Support summaries distinguish supported samples from known
samples so unknown evidence is not silently counted as false or true.

## CRS and grid validation rules

Before a scientific operation uses multiple spatial variables, validation must
confirm:

1. science-grid `y` and `x` are one-dimensional, finite, monotonic, and regularly spaced;
2. every variable entering the same science operation uses the same declared grid;
3. coordinate values and shapes are aligned, rather than merely having equal
   array shapes;
4. all spatial variables reference the same `spatial_ref` mapping;
5. CRS information is present and parseable through a standard representation;
6. no reprojection, resampling, or shape-based broadcasting is performed
   implicitly.

Grid incompatibility is an error. A caller must explicitly resample or
reproject before constructing a normalized Dataset for a multi-layer science
operation, and that operation must record the choice in metadata. The
documented incidence-geometry adapter is the exception: it performs and
records its named grid conversion before returning an exactly aligned result.

## Source metadata and support boundary

Support answers “where is an operation supported?” Source metadata answers
“how was this value or support decision produced?” They are related but not
interchangeable.

At minimum, a later reference-phase result must retain the reference method,
offset and units, contributors, observations, weights, exclusions, support,
and status. A later temporal result must retain the edge/path policy and
whether support was complete. These details must not be reduced to a scalar
offset or one universal mask. Temporal accumulation must additionally retain
the edge order, path interval, support policy, and whether support is complete
at each endpoint.
