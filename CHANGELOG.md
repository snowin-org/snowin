# Changelog

## 0.1.0 - unreleased

The first release line provides named xarray-native phase-to-dSWE methods,
explicit NISAR GUNW product normalization, optional local-incidence geometry
from caller-prepared DEMs, auditable reference offsets, directed temporal
accumulation, and named support composition. Normalized Dataset metadata uses
the frozen schema version `0.1`.

The package exposes correction layers with provenance but does not apply them.
Product discovery, download, cloud staging, vector masking, station I/O,
plotting, and generic evaluation metrics remain caller-owned or downstream
workflow responsibilities. Pairwise dSWE is `SWE_secondary - SWE_reference`,
not absolute SWE.

The release line includes synthetic and regression tests, optional integration
checks for caller-supplied real products, CI coverage, wheel-install checks, and
minimal reusable examples. It does not require product data or network access
for its normal test suite.
