# SnowIn normalized data model

Status: Stage 3 contract. This document defines the smallest
retrieval-ready xarray representation used by the NISAR adapter and the
canonical scientific kernels. It is deliberately narrower than a mission
product schema.

## Boundary and scope

The normalized object at the SnowIn science boundary is an
`xarray.Dataset`. It represents one directed interferometric pair on one
analysis grid:

```text
source product / adapter
    -> one SnowIn pair Dataset
    -> scientific function over xarray objects
```

The pair Dataset is not:

- a raw NISAR HDF5 hierarchy;
- a stack or temporal graph;
- an absolute SWE product;
- a custom `SnowScene`, `SnowStack`, or `SnowProduct` object.

The pair-first boundary is intentional. It lets the NISAR adapter and the
pairwise dSWE contract remain testable while Stage 6 consumes an explicit
sequence of directed pair Datasets for accumulation. A general stack/edge-table
contract remains deferred rather than guessed here.

## Required dimensions and coordinates

A retrieval-ready pair Dataset has exactly two spatial dimensions:

| Name | Role | Contract |
| --- | --- | --- |
| `y` | row/cell-center coordinate | One-dimensional, finite, strictly monotonic, regularly spaced, and in the CRS coordinate units. |
| `x` | column/cell-center coordinate | One-dimensional, finite, strictly monotonic, regularly spaced, and in the CRS coordinate units. |

Spatial variables use dimension order `("y", "x")`. The coordinate order is
preserved from the source; consumers must not assume that `y` increases or
decreases without checking it. SnowIn does not silently flip arrays.

The Dataset also contains a scalar `spatial_ref` coordinate or variable. It
holds a CF-style CRS description, such as `crs_wkt` and/or `epsg_code`.
Every spatial data variable has `grid_mapping="spatial_ref"` in its
attributes. A normalized Dataset has one grid only: spatial variables must
have the same dimensions, coordinate values, shape, and grid mapping.

The `x` and `y` coordinates are cell centers. Their `units` attribute names
the linear units of the declared CRS. A projected metre-based grid normally
uses `units="m"`; the contract does not silently convert another CRS unit.

## Required Dataset attributes

The following attributes are required and must be scalar, serializable values:

| Attribute | Meaning |
| --- | --- |
| `snowin_schema_version` | Version of this normalized contract, initially a draft `0.1-draft` value. |
| `product_kind` | `"pairwise_interferogram"` for this contract. |
| `reference_time` | Reference acquisition start time as an ISO 8601 UTC string. |
| `secondary_time` | Secondary acquisition start time as an ISO 8601 UTC string. |
| `temporal_edge` | Fixed value `"reference_to_secondary"`; this is the directed edge orientation. |
| `phase_difference_definition` | Fixed canonical value `"secondary_minus_reference"`; see [phase conventions](scientific_conventions.md). |
| `wavelength_m` | Resolved radar wavelength in metres, positive and explicit. |

`reference_time` and `secondary_time` identify product roles. The name
`reference` does not by itself mean “earlier in time”. A downstream temporal
accumulator must inspect the two timestamps and reject or explicitly handle a
non-chronological edge.

Recommended provenance attributes include `source_product_type`,
`source_granule_id`, `source_phase_difference_definition`,
`phase_transform`, and serialized source dataset paths or processing history.
For any Dataset adapted from an external product,
`source_phase_difference_definition` is required and must be a recognized
source convention. `phase_transform` is required and must explicitly state
the conversion to the canonical phase. Missing or unknown source conventions
are errors; an adapter must never guess them from phase values.

For the NISAR/ISCE3 source convention used by this contract:

```text
source phase = phi_reference - phi_secondary
SnowIn phase = -source phase
phase_transform = "multiply_by_-1"
```

Product-specific paths and mission metadata remain adapter provenance, not
scientific variable names.
Attributes must remain serializable; nested Python objects should be encoded
as JSON strings when persistence requires it.

The Stage 3 NISAR adapter defaults to a local terrain-surface incidence angle
generated from a cached or automatically downloaded NISAR-modified Copernicus
DEM and the GUNW radar-grid look vectors. A caller may also provide a local
DEM explicitly. The product's
native ellipsoid-normal `incidenceAngle` is retained as an explicit opt-in
compatibility mode, not silently substituted for the local retrieval angle.
The DEM acquisition/cache path, DEM reprojection, LOS interpolation, selected
radar-grid height, coordinate orientation, and source paths are recorded in
Dataset provenance. The adapter also records the GUNW ellipsoidal height
reference and DEM vertical datum. The default NISAR-modified Copernicus DEM is
ellipsoidal; the original orthometric COP30 compatibility source requires a
same-grid geoid-undulation correction or strict rejection of uncorrected
geometry.

## Required and optional variables

The minimum pairwise retrieval Dataset contains these two physical variables:

| Variable | Dimensions | Units | Meaning |
| --- | --- | --- | --- |
| `phase` | `("y", "x")` | `rad` | Unwrapped interferometric phase for the directed pair, with its sign defined by `phase_difference_definition`. |
| `incidence_angle` | `("y", "x")` | `rad` | Incidence angle used by the retrieval. It also has required `incidence_angle_reference`, either `"ellipsoid"` or `"local"`. |

`wavelength_m` is a Dataset attribute because it is a scalar property of this
pair. An adapter must resolve it from authoritative metadata or an explicit
caller value before a scientific kernel runs. The normalized contract does
not permit a silent approximate mission fallback.

The following variables are optional and retain distinct scientific roles:

| Variable | Units/type | Role |
| --- | --- | --- |
| `coherence` | dimensionless float | Coherence diagnostic; it is not itself a universal validity mask. |
| `connected_component` | integer label | Product connected-component identity; label values must not be collapsed into a dominant-component assumption. |
| `product_valid` | boolean | Whether product support/validity is known for the sample. Absence means unknown, not valid. |
| `geometry_valid` | boolean | Whether the geometry required by the operation is supported. |
| `reference_supported` | boolean | Whether the sample has support for a declared reference operation. |
| `temporal_path_supported` | boolean | Whether a cumulative result has a complete supported path. |
| `evaluation_supported` | boolean | Whether independent evaluation data support the sample. |
| `snow_state_supported` | boolean | Whether declared snow-state evidence supports the sample. |
| `coherence_valid` | boolean | A separately declared coherence-support policy, when one is needed. |
| `pairwise_supported` | boolean | Explicit support for the pairwise dSWE edge at each sample; temporal accumulation combines this with finite dSWE and never treats unsupported samples as zero. |

Reference-phase outputs are optional and are not implicit quality masks:

| Variable | Dimensions | Meaning |
| --- | --- | --- |
| `phase_referenced` | `("y", "x")` | Canonical phase after subtraction of the explicitly estimated reference offset, in radians. It remains missing when reference estimation is unsupported. |
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
provenance. `_FillValue` is an I/O encoding detail, not a scientific value.

No support variable is implicitly created with all `True` values. Absence of
support evidence means unknown support.

Stage 7 support helpers preserve these variables as named xarray layers. A
derived conjunction is allowed only when the caller explicitly names its
components; it is recorded as a policy and is not stored as a universal
`quality_mask`. Support summaries distinguish supported samples from known
samples so unknown evidence is not silently counted as false or true.

## CRS and grid validation rules

Before a scientific operation uses multiple spatial variables, validation must
confirm:

1. `y` and `x` are one-dimensional, finite, monotonic, and regularly spaced;
2. every spatial variable uses the same `("y", "x")` dimensions;
3. coordinate values and shapes are aligned, rather than merely having equal
   array shapes;
4. all spatial variables reference the same `spatial_ref` mapping;
5. CRS information is present and parseable through a standard representation;
6. no reprojection, resampling, or shape-based broadcasting is performed
   implicitly.

Grid incompatibility is an error. A caller must explicitly resample or
reproject before constructing a normalized Dataset for a multi-layer science
operation, and that operation must record the choice in provenance.

## Provenance and support boundary

Support answers “where is an operation supported?” Provenance answers “how was
this value or support decision produced?” They are related but not
interchangeable.

At minimum, a later reference-phase result must retain the reference method,
offset and units, contributors, observations, weights, exclusions, support,
and status. A later temporal result must retain the edge/path policy and
whether support was complete. These details must not be reduced to a scalar
offset or one universal mask. Temporal accumulation must additionally retain
the edge order, path interval, support policy, and whether support is complete
at each endpoint.

## Public and private API boundary

The intended public boundary is a small set of functions that accept and
return `xarray.DataArray` or `xarray.Dataset` objects. Functions must preserve
promised dimensions, coordinates, CRS/grid metadata, scientific attributes,
missing-data semantics, and lazy array behavior where supported.

The following remain private implementation details:

- NISAR HDF5 group paths and mission-specific variable names;
- conversion of product layers to NumPy arrays for legacy prototype code;
- product-reader dataclasses such as the current `GunwLayers`;
- source-specific fill values and metadata traversal.

The legacy `phase_to_dswe()` and `phase_raster_to_dswe()` functions remain
compatibility APIs. The stable scientific boundary is the set of named,
xarray-native retrievals `snowin.compute_leinss_dswe()`,
`snowin.compute_guneriussen_dswe()`, and `snowin.compute_oveisgharan_dswe()`;
adapters must provide normalized xarray objects to these scientific kernels.
`snowin.compute_dswe()` remains a backwards-compatible alias for the Leinss
method and does not dispatch among retrieval models. The methods keep their
model-specific parameters separate: Leinss uses `alpha`, Guneriussen requires
snow density and selects a density-to-permittivity model, and Oveisgharan uses
its fixed published incidence polynomial. Wavelength must be explicit or
resolved through a named stock sensor/band value; no sensor is assumed.

No custom scene/stack/product class or xarray accessor is introduced by this
contract.

## xarray runtime dependency

xarray is a core SnowIn runtime dependency. The normalized Dataset contract
and stable scientific APIs are xarray-native, so a normal SnowIn installation
must be able to construct and process these objects. Dask remains optional;
when Dask-backed arrays are supplied, SnowIn preserves their lazy backing
without making Dask a required dependency.

## Canonical phase contract

SnowIn uses one normalized phase orientation:

```text
phase = phi_secondary - phi_reference
```

This is aligned with the directed edge
`reference_time -> secondary_time` and with
`dSWE = SWE_secondary - SWE_reference`. Positive normalized phase is positive
forward phase change. Pairwise dSWE follows the same direction and is not an
absolute SWE value.

The source-to-canonical transformation is an adapter responsibility. The
Stage 1 contract defines and tests the required provenance, but does not
implement the GUNW reader transformation.
