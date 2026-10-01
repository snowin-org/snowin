# Scientific conventions

These conventions define SnowIn's phase, retrieval, grid, support, and
temporal semantics. Ambiguity in a scientifically consequential input must
fail rather than be guessed.

## Quantities and direction

SnowIn distinguishes pairwise change from an absolute state:

```text
interferometric phase
    -> pairwise dSWE
    -> cumulative dSWE relative to an initial radar epoch
    -> absolute SWE only with an independent initial SWE condition
```

The canonical phase is `phi_secondary - phi_reference`, in radians. A pair is
directed from `reference_time` to `secondary_time`; those product roles do not
imply chronological order. The dSWE sign is `SWE_secondary - SWE_reference`.
Accumulation validates chronology and contiguity and never sorts, fills, or
interpolates missing edges.

## Phase-to-dSWE methods

`compute_leinss_dswe()` implements the Leinss et al. (2015) approximation:

```text
dSWE = phase * wavelength_m
       / (2*pi*alpha*(1.59 + incidence_angle_rad**2.5))
```

The phase is canonical radians, wavelength is metres, incidence is radians,
and `alpha` is dimensionless. The empirical angle term uses radians
numerically. This is a dry-snow change retrieval, not an absolute-SWE model or
a universal accuracy guarantee. Its local terrain-surface incidence is the
physical preference; an ellipsoid-referenced approximation remains explicitly
identified in metadata.

`compute_guneriussen_dswe()` is a distinct density-dependent formulation and
requires snow density in kg m-3. `compute_oveisgharan_dswe()` is a separate
fitted model using `A(theta) = -0.6784*theta**2 + 0.2899*theta - 0.8473` and
`dSWE = phase / (-2*k_i*A(theta))`, where `k_i = 2*pi/wavelength_m`.
Scientific sources and implementation notes are in
[code provenance](code_provenance.md).

All named methods require explicit positive `wavelength_m`; the generic
science layer has no sensor registry. The NISAR adapter uses authoritative
`centerFrequency` metadata and computes wavelength as `c/f`. No method infers
angle units or phase convention from values.

## Incidence and geometry

Phase and incidence use radians. Every incidence array identifies its
reference as `local` or `ellipsoid`; one is not silently substituted for the
other. Valid retrieval incidence is finite and in `[0, pi/2)`. Local NISAR
incidence is calculated from GUNW target-to-sensor LOS vectors and a
DEM-derived terrain normal. Unsupported and back-facing terrain remains
missing and is marked invalid.

The geometry operation requires a caller-prepared DEM and records source and
vertical datum assumptions. GUNW radar-grid heights use the WGS84 ellipsoid;
orthometric DEMs require a declared vertical correction when strict datum
matching is requested. See [vertical datums](vertical_datums.md).

## xarray grid and missing-data contracts

SnowIn preserves dimensions, coordinate values and order, CRS/grid-mapping
metadata, provenance, and Dask laziness where promised. Scientific kernels do
not silently align or resample grids. NaN and unknown support propagate; they
are never replaced by zero or assumed valid.

Product validity, geometry validity, reference support, pairwise support,
temporal-path support, evaluation support, snow-state support, and coherence
validity are separate named layers. A conjunction is formed only when the
caller names its support components. SnowIn does not define a universal
`quality_mask`.

## Reference phase and correction layers

Reference estimation requires an explicit manual offset or caller-supplied
contributors. For contributor residuals `r_i = observed_i - expected_i`, the
weighted offset is `sum(w_i*r_i)/sum(w_i)`, and the referenced phase is
`phase - offset`. Contributor IDs, weights, exclusions, eligibility, and
status remain in the returned xarray object. SnowIn does not choose stations,
dates, or expected phase.

The GUNW adapter may expose ionospheric and tropospheric phase layers with
source provenance, but does not apply them. A reusable correction operation is
deferred until units, signs, grid requirements, and provenance are frozen in a
scientifically reviewed xarray contract.
