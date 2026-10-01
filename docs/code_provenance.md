# Code and scientific provenance

This record identifies the scientific basis and deliberate package boundary
for SnowIn 0.1. The implementations are independent SnowIn code; referenced
equations and product conventions do not imply that external code was copied.

## Retrieval equations

- **Leinss:** Leinss et al., “Snow Water Equivalent of Dry Snow Measured by
  Differential Interferometry,” IEEE JSTARS (2015), Eq. 18,
  [DOI 10.1109/JSTARS.2015.2432031](https://doi.org/10.1109/JSTARS.2015.2432031)
  and [open manuscript](https://elib.dlr.de/100787/1/Leinss-2015-04.pdf).
- **Guneriussen:** Guneriussen et al. (2001),
  [DOI 10.1109/36.957273](https://doi.org/10.1109/36.957273), with named
  density-permittivity options documented in the implementation.
- **Oveisgharan:** Oveisgharan et al. (2024), The Cryosphere,
  [DOI 10.5194/tc-18-559-2024](https://doi.org/10.5194/tc-18-559-2024).

The canonical phase and pairwise dSWE directions, units, equation forms, and
limitations are in [scientific conventions](scientific_conventions.md).
Synthetic analytical and invariant tests cover the equations; the package does
not tune them against validation data.

## NISAR product and geometry

The adapter delegates GUNW hierarchy access to
[`nisar-pytools`](https://github.com/ZachHoppinen/nisar_pytools) and keeps
product normalization in `snowin.io`. NISAR/ISCE3 source phase is explicitly
converted from `reference_minus_secondary` to SnowIn's
`secondary_minus_reference`. Wavelength is resolved from product
`centerFrequency` as `c/f`. Correction screens retain source metadata and are
never applied automatically.

Local incidence follows the terrain-normal/LOS dot-product geometry:

```text
n = normalize((-dz/dx, -dz/dy, 1))
incidence = arccos(clip(dot(target_to_sensor_los, n), -1, 1))
```

DEM reprojection and LOS interpolation are validated against analytic
synthetic cases. The adapter records CRS, vertical datum, interpolation, and
support decisions. GUNW radar-grid height is ellipsoidal; DEM source
assumptions and explicit vertical correction behavior are documented in
[vertical datums](vertical_datums.md). External real-product regression inputs
are optional and described in `tests/fixtures/README.md`.

## Reference, support, and temporal behavior

Reference estimation is independently implemented as xarray operations in
`snowin.reference.phase`. It retains contributors, weights, exclusions,
support, and status. The generic residual-weighted algebra is documented in
[scientific conventions](scientific_conventions.md); station selection and
expected-phase construction remain caller-owned.

Support layers retain distinct meanings in `snowin.quality.support` and are
combined only when explicitly requested. `snowin.temporal` accumulates only
caller-ordered chronological contiguous edges and propagates unsupported
samples. Both are protected by synthetic xarray and Dask tests.

## Deliberate 0.1 scope decisions

- **Removed sensor wavelength registry and retrieval aliases:** no stable
  release has depended on them; generic equations now require explicit
  wavelength, while NISAR metadata supplies its authoritative value.
- **Removed legacy NumPy reference strategies:** they duplicated the
  contributor-based xarray reference API. `reference_phase`,
  `estimate_reference_offset`, and `apply_reference_offset` retain the
  auditable behavior.
- **Removed NumPy correction configuration/result API:** it lacked an xarray
  grid, unit, and product-aware correction contract. No scientific correction
  capability is silently lost or substituted; GUNW fields remain inspectable.
  Correction application remains caller-owned in 0.1, and a workflow must
  explicitly resolve correction signs and source-grid alignment.
- **Removed generic evaluation metrics:** bias, MAE, RMSE, and correlation are
  generic evaluation operations; callers can use their chosen evaluation
  libraries over explicitly composed support.
- **Removed generic array utilities:** shape checks and finite fractions were
  implementation helpers without a SnowIn scientific meaning.
- **Removed study scripts, spatial-mask code, and historical planning files:**
  search/download, unwrapping, basin and station policy, vector rasterization,
  plots, and research records belong in their source or downstream workflow.
  Their deletion from this branch does not alter the retained scientific
  kernels. Git history preserves development artifacts.
