# Code and science provenance

This record identifies the scientific sources and validation layers for the
reusable SnowIn operations. Study-specific station selection, dates, basin
boundaries, and result figures remain downstream inputs.

## Phase-to-dSWE methods

SnowIn implements distinct named relations rather than treating the equations
as interchangeable:

- The Leinss dry-snow approximation follows Eq. 18 in Leinss et al. (2015),
  [DOI 10.1109/JSTARS.2015.2432031](https://doi.org/10.1109/JSTARS.2015.2432031).
- The density-dependent Guneriussen relation follows Guneriussen et al. (2001),
  [DOI 10.1109/36.957273](https://doi.org/10.1109/36.957273), with explicitly
  selected permittivity models.
- The Oveisgharan fit follows Oveisgharan et al. (2024),
  [The Cryosphere 18, 559](https://doi.org/10.5194/tc-18-559-2024).

The equations are independently implemented with xarray in `src/snowin/snow/`;
no external repository code is copied into SnowIn. Related implementations
were inspected in [SnowEx/uavsar_snow](https://github.com/SnowEx/uavsar_snow),
[SnowEx/uavsar_pytools](https://github.com/SnowEx/uavsar_pytools),
[uavsar-validation](https://github.com/ZachHoppinen/uavsar-validation), and
[SWE_error_analysis](https://github.com/rpalomaki/SWE_error_analysis). They
serve as equation and convention references, not runtime dependencies.

`tests/test_dswe_kernel.py`, `tests/test_dswe_methods.py`, and the associated
property tests protect independent values, scientific invariants, input
validation, xarray structure, missing-data behavior, and eager/lazy equivalence.

## NISAR GUNW adapter and geometry

The product boundary follows the NASA/ASF [GUNW user guide](https://nisar-docs.asf.alaska.edu/gunw/),
[metadata guide](https://nisar-docs.asf.alaska.edu/metadata/), and the NISAR
L2 GUNW product specification. It reads unwrapped phase in radians, normalizes
the declared source convention to SnowIn's `secondary_minus_reference` phase,
and resolves wavelength from center-frequency metadata. The adapter records
the transform and wavelength source in xarray metadata.

Local incidence is calculated from the GUNW target-to-sensor LOS vectors and
the selected DEM-derived terrain normal, with interpolation on the product's
radar-grid height/y/x coordinates. The default NISAR-modified Copernicus DEM is
ellipsoidal; raw public GLO-30 is an explicit orthometric compatibility source
that requires a declared vertical correction for strict datum matching. The
implementation is independent; NASA/ASF documentation is used as product
documentation, not bundled code.

`tests/test_nisar_adapter.py` and `tests/test_geometry.py` use synthetic HDF5,
analytic terrain, and malformed grids to protect adapter and geometry
behavior. The optional `real_product_geometry.json` fixture records expected
statistics for one externally supplied GUNW/DEM pair. Its inputs are not
bundled and its test does not run in the normal fast suite.

## Reference phase, support, and temporal paths

Reference-phase aggregation accepts explicit contributor values and weights;
SnowIn does not choose stations, dates, or expected-phase construction. The
coherence-weighted algebra is described by Zhou et al. (2025),
[DOI 10.5194/tc-19-5361-2025](https://doi.org/10.5194/tc-19-5361-2025).
The implementation and test cases are in `src/snowin/reference/` and
`tests/test_reference.py`.

Temporal accumulation follows explicit directed edges from reference to
secondary time. Missing or unsupported samples remain unsupported along the
path. Named support layers and metrics keep product, geometry, retrieval, and
evaluation policies separate. Their contracts are covered by
`tests/test_temporal.py`, `tests/test_support_metrics.py`, and the property and
integration tests.

## Implementation and licensing

The equations and product documentation above inform independent
implementations. No third-party implementation code is copied into SnowIn.
SnowIn is distributed under Apache-2.0; consult the upstream projects and
scientific publications for their own license and citation requirements.
