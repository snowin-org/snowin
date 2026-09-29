# SnowIn scientific conventions

These conventions define package-wide normalized data contracts and the
supported phase-to-dSWE methods.

## Quantities and units

SnowIn distinguishes the following quantities:

| Quantity | Contract |
| --- | --- |
| Interferometric phase | Unwrapped phase associated with one directed acquisition pair; radians internally. It is not an absolute snow quantity. |
| Pairwise dSWE | Snow-water-equivalent change for one directed pair, metres water equivalent internally. |
| Cumulative dSWE | Sum of supported pairwise changes along an explicit path from an initial radar epoch; it remains a change relative to that epoch. |
| Absolute SWE | An absolute state that requires an independent initial SWE condition in addition to cumulative dSWE. |

The scientific chain is therefore:

```text
interferometric phase
    -> pairwise dSWE
    -> cumulative dSWE relative to t0
    -> absolute SWE only with an independent SWE(t0)
```

SnowIn must not expose a generic `stack_to_swe()` operation that hides these
distinct meanings.

Other internal conventions are:

- incidence angle is in radians;
- wavelength is in metres;
- coherence is dimensionless and is a diagnostic, not automatically a mask;
- projected grid coordinates use the declared CRS units;
- dates are explicit ISO 8601 UTC values at the pair boundary.

The local incidence angle used by the dSWE kernel must be in `[0, pi/2)`. The
NISAR geometry adapter computes the angle between the target-to-sensor LOS and
the upward terrain normal. Where their dot product is nonpositive, the terrain
face is not oriented toward the sensor: the adapter stores incidence as missing
and `geometry_valid=False`. It does not fold the angle with an absolute value
or clip it into the valid range.

Unit labels are required metadata. Scientific kernels must reject an absent or
ambiguous angle unit rather than infer degrees or radians from value magnitude.
The prototype `incidence_angle_unit="auto"` compatibility path is retained as
documented legacy debt. It is not used by the Stage 2 canonical kernel.

## Directed acquisition pairs

An interferogram is a directed edge:

```text
reference acquisition  ->  secondary acquisition
```

The normalized pair contract names this orientation
`temporal_edge="reference_to_secondary"` and stores both acquisition times.
“Reference” and “secondary” are product roles; the reference is not assumed to
be earlier in calendar time. A temporal accumulation operation must check
chronology explicitly and may not use an edge merely because its array shape
matches another edge.

Missing pairwise support remains missing. A missing edge is not zero dSWE, zero
ablation, or a valid path contribution.

## Canonical phase sign

Phase sign is scientifically consequential because it propagates directly into
the sign of dSWE. SnowIn's canonical normalized phase is:

```text
phase = phi_secondary - phi_reference
```

The normalized Dataset must set
`phase_difference_definition="secondary_minus_reference"`. This follows the
directed acquisition edge:

```text
reference_time -> secondary_time
```

and the physical change definition:

```text
dSWE = SWE_secondary - SWE_reference
```

Positive normalized phase is positive forward phase change. The Stage 2
SnowIn retrieval kernel uses the positive proportionality from the Leinss
approximation:

```text
dSWE = phase * wavelength
       / (2*pi*alpha*(1.59 + incidence**2.5))
```

The implemented kernel is independently reimplemented from Eq. 18 of
[Leinss et al. (2015)](https://elib.dlr.de/100787/1/Leinss-2015-04.pdf).
Here `phase` is the canonical pairwise phase change in radians, `dSWE` is
pairwise snow-water-equivalent change in metres water equivalent, `wavelength`
is the radar wavelength in metres, `k_i = 2*pi/wavelength` is the incidence
wavenumber in m^-1, `incidence` is the supplied radar incidence angle in
radians, and `alpha` is the dimensionless empirical path factor. The empirical
`1.59 + theta**(5/2)` term uses theta numerically in radians; it is not a
degree-valued polynomial.

The relation is a dry-snow change retrieval, not an absolute-SWE model. It
assumes dry snow, negligible liquid water, and the scattering/low-frequency
conditions described by Leinss et al. The angle in the physical refraction
problem is incidence relative to the snow surface: a local terrain-surface
angle is preferred for spatial retrievals. An ellipsoid-referenced angle may
only be used when it is the declared approximation to that physical angle;
SnowIn records the distinction and never substitutes one for the other.
Leinss reports a few-percent approximation error in its tested range with
optimized alpha, and larger error toward high incidence angles; the fixed
`alpha=1` approximation is not a universal accuracy guarantee.

The canonical `snowin.snow.compute_dswe` function requires xarray DataArrays,
explicit radians metadata, explicit positive `wavelength_m`, and no phase-sign
or angle-unit switch. It assumes that source normalization has already
produced canonical phase. The retired NumPy method dispatcher is not part of the supported scientific
API; use the named xarray retrieval methods.

The Oveisgharan fit is scientifically distinct, not an alias for Leinss. Its
independent approximation is described by
[Oveisgharan et al. (2024)](https://tc.copernicus.org/articles/18/559/2024/):
`A(theta) = -0.6784*theta**2 + 0.2899*theta - 0.8473` and
`dSWE = phase / (-2*k_i*A(theta))`. SnowIn exposes it through its own named
method; it is selected explicitly through its named xarray function.

NISAR/ISCE3 source interferograms use the opposite source convention for this
boundary:

```text
source phase = phi_reference - phi_secondary
```

The NISAR adapter explicitly normalizes it:

```text
snowin_phase = -gunw_source_phase
```

and record:

```text
canonical convention: secondary_minus_reference
source convention: reference_minus_secondary
transform: multiply by -1
```

Phase conventions must never be inferred from data magnitudes or guessed from
variable names. An adapter with a missing or unknown source convention must
fail. An adapter may not silently negate phase or claim canonical output
without recording the source convention and transform.

Legacy downstream sign switches are not physical sign authority. Product
adapters must normalize the declared source convention and record the
transform before a scientific retrieval runs.

## Wavelength and incidence angle

`wavelength_m` is positive and resolved before the retrieval equation runs.
The named public methods accept either an explicit wavelength or an explicitly
selected stock sensor and band. NISAR GUNW adapters use the product's
authoritative center-frequency metadata when available. SnowIn does not infer
a sensor from array values or silently replace product metadata with a stock
value.

`incidence_angle` is a spatial variable in radians. Its
`incidence_angle_reference` attribute is required and must distinguish at
least `ellipsoid` from `local`. The package must not substitute one for the
other or infer the distinction from a variable name. The Stage 3 NISAR
adapter defaults to `local` incidence generated from the NISAR-modified
Copernicus DEM and the
product radar-grid LOS cube; the product's ellipsoid-normal `incidenceAngle`
is available only through an explicit adapter mode.

The geometry boundary also records reference-system assumptions explicitly.
GUNW radar-grid height coordinates are heights above the WGS84 ellipsoid.
The NISAR-modified Copernicus DEM is re-referenced to the WGS84 ellipsoid for
SAR processing. The original Copernicus GLO-30 elevation is documented against
the EGM2008 orthometric datum and remains an explicit compatibility source.

## Reference phase and corrections

Reference subtraction is a scientific operation, not a cosmetic preprocessing
step. A result must retain the method, signed offset, contributors,
observations, weights, exclusions, support, and status. A scalar offset with
no provenance is insufficient for validation or reproducibility.

The reference API supports several explicit ways to obtain the additive
offset. Its coherence-weighted method follows the calibration algebra
described by Zhou et al. (2025), Eq. 6:

```text
C_hat = sum_i[weight_i * (observed_phase_i - expected_phase_i)]
        / sum_i[weight_i]
phase_referenced = phase - C_hat
```

The xarray-native public function is `snowin.reference_phase()`. It supports:

- `method="manual_offset"` with an explicit `offset_rad`;
- `method="single_station_offset"` with exactly one eligible contributor;
- `method="mean_additive_offset"` with an unweighted mean of eligible
  contributor residuals;
- `method="median_additive_offset"` with the robust median residual; and
- `method="coherence_weighted_additive_offset"` using caller-supplied,
  documented calibration weights.

The non-coherence-weighted methods are explicit input/aggregation policies,
not claims of additional published physical retrieval equations.
Contributor-level observed phase, expected phase, weights, IDs, and exclusion
reasons remain explicit inputs. SnowIn does not decide how stations are
selected, how dates are matched, or how expected phase is constructed. Those
are caller-owned scientific inputs and must be recorded in provenance.

This operation is distinct from `reference_time`: `reference_time` identifies
one acquisition in the directed temporal pair, while the Stage 5 reference
phase defines the spatial/physical phase baseline applied before dSWE
interpretation. It does not change the pair’s temporal edge or canonical phase
direction.

Likewise, correction layers such as ionospheric and tropospheric phase are not
applied merely because they are present. The operation and sign must be
explicit and recorded.

## Support semantics

The following meanings remain separate:

- product sample validity;
- geometry validity;
- connected-component identity;
- reference support;
- temporal-path support;
- evaluation-data support;
- snow-state evidence;
- coherence diagnostics and any declared coherence policy.

There is no universal SnowIn quality mask. A downstream study may define a
combined evaluation mask, but that combination is a named policy with
provenance rather than an implicit package default.

## Scientific debt carried forward

Stage 2 does not implement product adapters. Temporal accumulation is provided
by the Stage 6 `snowin.accumulate_dswe()` path API, and Stage 7 provides named
support and metrics helpers. The following remain for later stages:

- implement the GUNW source-to-canonical phase transformation;
- regression-audit the GUNW source sign lineage against authoritative product
  behavior;
- validate mission wavelength provenance in a product adapter;
- define a general graph/edge-table representation beyond one explicit path;
- define study-specific evaluation subsets and validation metrics outside the
  reusable metric primitives.
