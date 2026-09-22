# SnowIn normalized data model

Status: Stage 1 contract. This document defines the smallest
retrieval-ready xarray representation needed before the NISAR adapter and new
scientific kernels are developed. It is deliberately narrower than a mission
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
pairwise dSWE contract become testable before Stage 6 chooses how a collection
of directed edges should be represented. A stack/edge-table contract is
deferred rather than guessed here.

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
offset or one universal mask.

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

The current `phase_to_dswe()` and `phase_raster_to_dswe()` functions are
prototype NumPy-oriented APIs. Stage 1 does not rewrite them or claim that
they already satisfy this xarray preservation contract. Stage 2 must resolve
that compatibility explicitly before using them as the normalized scientific
kernel.

No custom scene/stack/product class or xarray accessor is introduced by this
contract.

## xarray dependency decision for Stage 1

Two reasonable packaging choices were considered:

1. make xarray a base dependency immediately, guaranteeing that every SnowIn
   installation can construct normalized objects;
2. keep xarray in the GUNW/development extras until a stable normalized xarray
   API is implemented, preserving the current lightweight base installation.

Stage 1 adopts option 2 provisionally. The contract tests run in the
development environment, where xarray is already installed. No new runtime
dependency is added while the current public scientific API remains
NumPy-oriented. Before a normalized xarray Dataset API is released, this
decision must be revisited; at that point xarray will likely become a base
dependency unless the API is explicitly isolated behind an extra.

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
