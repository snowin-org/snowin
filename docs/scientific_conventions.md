# SnowIn scientific conventions

Status: Stage 2 contract. These conventions retain the Stage 1 normalized
data contracts and define the verified phase-to-dSWE kernel.

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
produced canonical phase. The old NumPy `phase_to_dswe` function remains a
legacy characterization path only.

The Oveisgharan fit is scientifically distinct, not an alias for Leinss. Its
independent approximation is described by
[Oveisgharan et al. (2024)](https://tc.copernicus.org/articles/18/559/2024/):
`A(theta) = -0.6784*theta**2 + 0.2899*theta - 0.8473` and
`dSWE = phase / (-2*k_i*A(theta))`. It remains available only through the
legacy method path in Stage 2 and is not selected by the canonical kernel.

NISAR/ISCE3 source interferograms use the opposite source convention for this
boundary:

```text
source phase = phi_reference - phi_secondary
```

The future NISAR adapter must explicitly normalize it:

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

The Colorado `sign_plus` exploratory/frozen branch is not physical sign
authority. Its verified frozen parameters are used only as Stage 2
characterization evidence; source-to-retrieval migration remains deferred.

## Wavelength and incidence angle

`wavelength_m` is explicit, positive, and resolved before the canonical
retrieval kernel runs. The generic kernel has no sensor registry or mission
default. In particular, the approximate legacy NISAR value near 0.24 m is not
a Stage 2 scientific default; an authoritative product adapter may later
populate the explicit value from metadata. The Colorado frozen characterization
uses `0.238403545` m, but that study value is not silently promoted to a
generic default.

`incidence_angle` is a spatial variable in radians. Its
`incidence_angle_reference` attribute is required and must distinguish at
least `ellipsoid` from `local`. The package must not substitute one for the
other or infer the distinction from a variable name.

## Reference phase and corrections

Reference subtraction is a scientific operation, not a cosmetic preprocessing
step. A result must retain the method, signed offset, contributors,
observations, weights, exclusions, support, and status. A scalar offset with
no provenance is insufficient for validation or reproducibility.

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

Stage 2 does not implement product adapters or temporal accumulation. The
following remain for later stages:

- implement the GUNW source-to-canonical phase transformation;
- regression-audit the GUNW source sign lineage against authoritative product
  behavior;
- validate mission wavelength provenance in a product adapter;
- define graph/path representation for temporal accumulation.
