# Code and scientific provenance

This page records the scientific sources and product conventions used by
SnowIn. The implementations are independent SnowIn code.

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

The equations, canonical phase and dSWE directions, units, and limitations
are described in [scientific conventions](scientific_conventions.md).

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

The adapter records CRS, vertical datum, interpolation, and support. GUNW
radar-grid height is ellipsoidal; DEM assumptions and vertical correction
behavior are documented in [vertical datums](vertical_datums.md).

## Reference, support, and temporal behavior

Reference estimation retains its contributors, weights, exclusions, and
support; callers choose contributors and expected phase. Support layers retain
distinct meanings and are combined only when explicitly requested. Temporal
accumulation follows caller-ordered chronological edges and propagates
unsupported samples. These contracts are detailed in
[scientific conventions](scientific_conventions.md).
