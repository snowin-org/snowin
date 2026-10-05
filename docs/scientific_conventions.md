# Scientific conventions

This page states SnowIn's phase and dSWE signs, required units, grid behavior,
and temporal direction. SnowIn raises an error when a required scientific
convention is missing or unsupported.

## Numerical precision

SnowIn uses Float32 (`np.float32`) for floating-point scientific arrays and
numerical science outputs, including phase, correction screens, incidence
rasters, reference contributors and offsets, density arrays, and pairwise and
cumulative dSWE. Scientific boundaries convert caller-supplied Float64 science
arrays to Float32 while preserving dimensions, coordinates, attributes,
missing values, and Dask laziness. Reference estimation still computes its
documented scalar reduction.

This matches common SAR product storage and gives a consistent numerical
contract. Conversion rounds numerical representations; it does not create or
remove physical measurement information. Coordinates and indexing, CRS and
affine transforms, datetimes, integer labels and masks, boolean support, and
metadata identifiers retain their appropriate native types. Scalar metadata
may remain Python scalars. Geospatial libraries may use higher precision
internally for coordinate transformations, DEM reprojection, and LOS geometry;
returned floating science rasters follow the Float32 contract.

Users requiring a different numerical-precision policy must implement it
explicitly outside the current SnowIn contract, rather than relying on
accidental dtype promotion. This policy does not change schema 0.2, equations,
units, or phase and dSWE conventions.

## Quantities and direction

SnowIn distinguishes pairwise change from an absolute state:

```text
interferometric phase
    -> pairwise dSWE
    -> cumulative dSWE relative to an initial radar epoch
    -> absolute SWE only with an independent initial SWE condition
```

```text
phase = phi_reference - phi_secondary
dSWE = SWE_secondary - SWE_reference
temporal edge = reference -> secondary
```

Phase is in radians and dSWE is in metres. The reference and secondary names
identify the phase roles; a valid pair also has a later secondary acquisition.
Accumulation checks that edges are chronological and contiguous. It does not
sort edges, fill missing values, or interpolate between acquisitions. Each
pairwise dSWE variable must declare
`dswe_difference_definition="secondary_minus_reference"` before accumulation.
Dataset-level metadata or a schema label cannot replace this declaration.

When the source uses the known opposite definition,
`phi_secondary - phi_reference`, the adapter multiplies phase by -1 exactly once.
Delivered NISAR GUNW phase already uses the canonical definition and is retained
without inversion. Positive snow-related phase gives accumulation and negative
snow-related phase gives loss; measured phase need not be snow alone.
SnowIn raises an error if the source phase definition is missing or
unsupported; it does not infer the sign from phase values.

## Phase-to-dSWE methods

`compute_leinss_dswe()` implements the Leinss et al. (2015) approximation:

```text
dSWE = phase * wavelength_m
       / (2*pi*alpha*(1.59 + incidence_angle_rad**2.5))
```

The phase and incidence angle are in radians, wavelength is in metres, and
`alpha` is dimensionless. The empirical angle term uses radians numerically.
This is a dry-snow change retrieval, not an absolute-SWE model. Local
terrain-surface incidence is preferred; an ellipsoid-referenced angle is
identified in the output metadata.

`compute_guneriussen_dswe()` is a distinct density-dependent formulation and
requires snow density in kg m-3. `compute_oveisgharan_dswe()` is a separate
fitted model using `A(theta) = -0.6784*theta**2 + 0.2899*theta - 0.8473` and
`dSWE = phase / (-2*k_i*A(theta))`, where `k_i = 2*pi/wavelength_m`.
Scientific sources and implementation notes are in
[scientific sources](scientific_sources.md).

All named methods require explicit positive `wavelength_m`; the generic
science layer has no sensor registry. The NISAR adapter uses authoritative
`centerFrequency` metadata and computes wavelength as `c/f`. No method infers
angle units or phase convention from values.

## Incidence and geometry

Phase and incidence use radians. Every incidence array identifies its
reference as `local` or `ellipsoid`; one is not silently substituted for the
other. Valid retrieval incidence is finite and in `[0, pi/2)`. Local NISAR
incidence is calculated from GUNW target-to-sensor LOS vectors and a
DEM-derived terrain normal. Pixels without valid geometry have missing
incidence and `geometry_valid=False`.

The geometry operation requires a caller-prepared DEM and records source and
vertical datum assumptions. GUNW radar-grid heights use the WGS84 ellipsoid;
orthometric DEMs require a declared vertical correction when strict datum
matching is requested. See [vertical datums](vertical_datums.md).

## Xarray grids and missing data

SnowIn preserves dimensions, coordinate values and order, and CRS metadata.
Retrieval functions, support composition, and temporal accumulation preserve
Dask-backed arrays where promised. They do not align or resample grids. NaN
values and unknown support remain missing; SnowIn does not replace them with
zero or assume that they are valid. Call `.compute()` when you need a lazy
result in memory.

Product, geometry, reference, pairwise, temporal-path, evaluation, snow-state,
and coherence support are separate named variables. A combined mask is made
only when the caller names the support variables to combine. The NISAR
incidence operation records DEM reprojection, LOS interpolation, or native
incidence resampling and returns incidence on the phase grid. Scientific
functions require matching dimensions and coordinates.

## Reference phase and correction layers

Reference estimation requires an explicit manual offset or caller-supplied
contributors. Observed phase, expected phase, and offset all use the canonical
convention. For contributor residuals `r_i = observed_i - expected_i`, the
weighted offset is `sum(w_i*r_i)/sum(w_i)`, and the referenced phase is
`phase - offset`. Contributor IDs, weights, exclusions, eligibility, and
status remain in the returned xarray object. SnowIn does not choose stations,
dates, or expected phase.

The GUNW adapter may expose ionospheric and tropospheric phase layers with
source metadata, but does not apply them. SnowIn 0.1 has no correction
function. Callers who apply correction screens must handle their units, signs,
and source-grid alignment explicitly.

See the [phase sign audit](scientific_sources.md#phase-sign-audit) for source
evidence and the [migration guide](phase_migration.md) for schema 0.1 inputs.
