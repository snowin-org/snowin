# Code and science provenance

Every reusable scientific capability added to SnowIn should have a record here
or in a linked, versioned provenance record before it replaces downstream
study code. The record should answer:

| Field | Required information |
| --- | --- |
| Capability | SnowIn module and public function |
| Scientific source | Paper, ATBD, equation, or authoritative documentation |
| Repositories inspected | Relevant prior implementations and versions/commits |
| Implementation relationship | Copied, adapted, independently reimplemented, or wrapper |
| License implications | Source license and any notice/attribution requirements |
| Validation evidence | Invariants, characterization cases, regression products, and tolerances |
| Status | Prototype, reviewed, validated, or deferred |

Stage 0 establishes the framework only. The existing prototype capabilities
still require capability-specific records before they are treated as validated
SnowIn science. In particular, the dSWE formulations, GUNW product adapter,
reference-phase behavior, correction signs, and raster-grid assumptions need
primary scientific references and regression evidence in their respective
stages.

The migration rule is: define the scientific behavior, inspect the primary
reference and relevant upstream implementations, write invariant or
characterization tests, implement the smallest general version, record
provenance, and only then replace duplicate downstream code. Study-specific
basin choices, dates, station lists, paper metrics, and figure configuration
remain downstream.

## Stage 1 normalized-contract proposal

| Field | Record |
| --- | --- |
| Capability | Pairwise retrieval-ready xarray Dataset contract and scientific terminology. |
| Scientific source | `docs/snowin_architecture_v1.md`, `docs/data_model.md`, and `docs/scientific_conventions.md`, including the adopted `secondary_minus_reference` project contract; no production dSWE equation was changed. |
| Repositories inspected | Current SnowIn prototype modules and tests at the Stage 1 baseline; no external implementation was copied. |
| Implementation relationship | Independently specified schema and synthetic contract tests. |
| License implications | No third-party code copied or adapted. |
| Validation evidence | `tests/test_contracts.py` synthetic xarray objects and existing prototype characterization tests. |
| Status | Stage 1 contract finalized; GUNW source-sign transformation and Colorado sign-lineage regression audit are deferred to later stages. |

## Stage 2 canonical phase-to-dSWE kernel

| Field | Record |
| --- | --- |
| Capability | `snowin.snow.compute_dswe`: xarray-native pairwise phase-to-dSWE conversion in metres water equivalent. |
| Scientific source | Leinss et al., *Snow Water Equivalent of Dry Snow Measured by Differential Interferometry*, IEEE JSTARS (2015), DOI [`10.1109/JSTARS.2015.2432031`](https://doi.org/10.1109/JSTARS.2015.2432031), Eq. 18 and the open DLR manuscript [PDF](https://elib.dlr.de/100787/1/Leinss-2015-04.pdf). Guneriussen et al. (2001), DOI [`10.1109/36.957273`](https://doi.org/10.1109/36.957273), and Oveisgharan et al. (2024), DOI [`10.5194/tc-18-559-2024`](https://doi.org/10.5194/tc-18-559-2024), were audited as distinct supporting formulations. |
| Exact equation | `k_i = 2*pi / wavelength_m`; `dSWE = phase / (k_i*alpha*(1.59 + incidence_angle_rad**2.5))`, equivalently `phase*wavelength_m / (2*pi*alpha*(1.59 + incidence_angle_rad**2.5))`. |
| Terms and units | `phase` is canonical `phi_secondary - phi_reference` in radians; `dSWE` is `SWE_secondary - SWE_reference` in metres water equivalent; `wavelength_m` is metres; `k_i` is m^-1; incidence is radians; `alpha` is dimensionless. |
| Assumptions and domain | Dry snow, negligible liquid water, and the dry-snow scattering conditions described by Leinss et al.; this is a change retrieval, not absolute SWE. The physical angle is incidence relative to the snow surface. The empirical approximation has documented incidence/density error limits and does not establish a universal accuracy bound. |
| Implementation relationship | Independently reimplemented in `src/snowin/snow/dswe.py` with native xarray arithmetic. No external source code was copied or adapted. The legacy `swe.py` method dispatch was corrected so its Leinss and Oveisgharan compatibility methods represent their distinct published equations. |
| Repositories inspected | `SnowEx/uavsar_pytools` (`51fed9a`, setup metadata identifies MIT); `SnowEx/uavsar_snow` (`c76c4de`); `rpalomaki/SWE_error_analysis` tag `v1.0` (`1b01509`); `ehavazli/snowsar` tag `v0.1.1` (`5181f9b`, Apache-2.0); `ZachHoppinen/uavsar-validation` (`d9f94ae`, MIT); and the verified Colorado checkout `jacktarricone/nisar-grl-colorado-firstlook`, remote-confirmed at `/Users/jtarrico/ch13_nisar_prelim`, committed `HEAD d1afba2`. The Colorado evidence was read from committed `src/nisar_firstlook/phase.py`, `config/frozen/paper_reproduction_v2.json`, and committed tests; its unrelated dirty working-tree changes were not used. |
| External implementation findings | `uavsar_snow`/`uavsar_pytools` contain both the Guneriussen density-dependent relation and separate Leinss and Oveisgharan approximations. `uavsar-validation` uses the Leinss path-constant equation with explicit degree-to-radian conversion. `SWE_error_analysis` reproduces the Leinss forward/inverse relation. The current `snowsar` Python tree did not expose an independent phase-to-dSWE kernel. Colorado's committed frozen equation uses the same Leinss denominator and frozen `0.238403545` m wavelength, but retains an explicit historical `phase_sign` branch. |
| License implications | SnowIn contains no copied third-party code. External repository license metadata was recorded where present (MIT for `uavsar_pytools` setup metadata and `uavsar-validation`; Apache-2.0 for `snowsar`); no license file/metadata was found in the inspected `uavsar_snow` or `SWE_error_analysis` checkouts. Equation use and independent implementation do not substitute for any future code-level attribution review. |
| Validation evidence | `tests/test_dswe_kernel.py` covers zero/sign invariants, a known scalar, wavelength and angle dependence, NaN propagation, explicit units and wavelength errors, alignment, metadata, Dask laziness/equivalence, and Colorado frozen-parameter characterization. The frozen Colorado constants are used as numerical characterization only; no ASO or validation dataset was used for tuning. |
| Status | Stage 2 canonical kernel implemented and tested; product-specific NISAR phase normalization, authoritative wavelength extraction, and temporal/path integration remain deferred. |
