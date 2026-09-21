# SnowIn scientific conventions

Status: Stage 1 contract. These conventions define terminology and
validation requirements before new retrieval implementation is added.

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
documented debt and is not changed in Stage 1.

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

Positive normalized phase is positive forward phase change. The Leinss-style
SnowIn retrieval contract therefore uses the positive proportionality:

```text
dSWE = phase * wavelength
       / (2*pi*alpha*(1.59 + incidence**2.5))
```

The equation is documented here as a Stage 1 contract; the existing
production dSWE implementation is not changed in this stage.

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
authority. Its source-to-retrieval sign lineage will be regression-audited
during the later dSWE and Colorado migration stages.

## Wavelength and incidence angle

`wavelength_m` is explicit, positive, and resolved before a retrieval kernel
runs. A sensor registry may provide a convenience value only when it is
authoritative for the declared sensor/band; it must not hide an approximate
mission wavelength in a normalized Dataset.

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

Stage 1 intentionally does not change the prototype's numerical behavior. The
following remain for later stages:

- implement the GUNW source-to-canonical phase transformation;
- regression-audit the GUNW and Colorado sign lineage against authoritative
  product/equation behavior;
- decide how the NumPy prototype becomes an xarray-preserving dSWE kernel;
- replace automatic angle-unit inference with explicit contract enforcement;
- validate mission wavelength provenance;
- define graph/path representation for temporal accumulation.
