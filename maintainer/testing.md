# SnowIn scientific testing policy

This is the standard policy for tests that protect SnowIn's scientific
behavior. A scientific function is not adequately tested merely because it
runs and returns an array of the expected shape. Its mathematics, conventions,
numerics, labeled-array requirements, failure behavior, and computational behavior
must remain independently reviewable.

## Six core protections for public scientific operations

Every public scientific operation should be considered against all six areas
below. A test may be inapplicable to a particular operation, but that decision
should follow from its API rather than from convenience.

### 1. Mathematical and reference correctness

Expected values should be computed independently of the implementation under
test. Prefer a published equation evaluated directly in the test, an analytic
case, a trusted external value, or a deliberately small synthetic example.
Do not call the same private SnowIn helper to compute both expected and actual
values. For example, test the public Leinss kernel against the equation
`phase * wavelength / (2*pi*alpha*(1.59 + theta**2.5))` evaluated in the test.

For substantial algorithms, identify the source and meaning of reference
values. A frozen SnowIn output is useful regression protection, but it is not
independent scientific validation.

### 2. Scientific invariants and limiting behavior

Test properties that must hold across valid inputs, not only selected example
outputs. The primary dSWE kernel, for example, is expected to satisfy zero
phase → zero dSWE, phase sign reversal → dSWE sign reversal, linear scaling in
phase and wavelength, inverse scaling in `alpha`, and non-increasing dSWE as a
valid incidence angle increases for positive phase under the implemented
Leinss approximation. NaNs must follow the documented missing-data policy.

Temporal accumulation should be checked against analytical prefix sums on
contiguous directed paths. Adding a zero edge should preserve numeric
cumulative values while adding its endpoint. Missing or explicitly unsupported
edge support must never become zero; an unsupported pixel remains unsupported
at later path endpoints. Reversed, out-of-order, or broken paths must fail.

Reference properties must follow their documented equation and sign. Do not
infer new scientific behavior from an attractive test property; document a
discrepancy first if code and the stated convention do not agree.

### 3. Input validation and failure behavior

Scientific ambiguity should fail loudly. Use explicit `pytest.raises` checks
for invalid units, unknown phase conventions, missing required metadata,
invalid angles or wavelengths, incompatible dimensions or coordinates,
malformed temporal edges, and incompatible grids. Do not silently guess a
phase sign, convert ambiguous units, or align/resample scientific grids inside
a kernel when callers must convert or resample before calling it.

Warnings that are part of expected behavior should be asserted with
`pytest.warns(...)`. Unexpected warnings from `snowin` are configured as errors
where their source location allows pytest to identify the package module. The
only current third-party exception is Rasterio's `PendingDeprecationWarning`
for its internal use of `Affine *` instead of `Affine @`; the filter matches
only that warning category and exact message. SnowIn warnings are not covered
by this exception.

### 4. Xarray data model

For xarray-native functions, test more than `.values`. Protect applicable
dimensions and order, sizes, coordinates and orientation, names, attributes,
units, CRS/grid-mapping metadata, time ordering, phase definition, incidence
reference, wavelength, support masks, and source metadata. A correct raster on the
wrong grid or with the wrong sign or units is a failed scientific result.

Use `xr.testing.assert_allclose` for numerically tolerant labeled comparisons,
`xr.testing.assert_equal` for exact values and coordinates without requiring
equal attributes, and `xr.testing.assert_identical` when attributes and the
complete xarray structure must match.

### 5. Eager and lazy equivalence

Every operation advertised as xarray/Dask compatible should have a small test
that its eager and Dask-backed results agree within a justified tolerance.
When laziness is part of the API, assert that the returned data remain
Dask-backed before `.compute()`. A scientific operation should not trigger
`.compute()` internally unless that reduction is explicitly documented.

Tests should use tiny arrays and simple chunking. Dask equivalence is a
required behavior, not a performance benchmark.

### 6. Regression protection

Every substantive bug fix should add a permanent test that fails for the
broken behavior and passes after correction. Prefer a compact synthetic
reproduction over a large external product. Reference the issue or pull
request in a comment when it helps explain why the case exists.

## Property-based tests

Hypothesis supplements, and does not replace, deterministic analytical tests.
Use bounded physically valid domains, small scalars/1-D/2-D arrays, and useful
dtype alternatives. Keep examples small enough for the pull-request suite.
Property tests use deterministic Hypothesis settings so failures are
reproducible; retain Hypothesis's failing example in the report when
diagnosing a failure.

Prioritize public equations and invariants. Do not mechanically add generated
tests to every helper. Parameterize related deterministic examples with
`pytest.mark.parametrize` when that makes the scientific rule clearer.

## Numerical tolerances

Every tolerance must be physically or numerically justified, as strict as
practical, and appropriate to the dtype and algorithm. Important scientific
comparisons should specify both `rtol` and `atol` explicitly. Use exact
equality only when exact equality is genuinely expected (for example, a
zero-phase result or a boolean support mask). Never widen a tolerance merely
to make CI pass. A widened tolerance requires a test comment explaining the
roundoff, interpolation, or reference-data precision that necessitates it.

There is no universal tolerance for all SnowIn products. Float32 closed-form
kernels, reference reductions, temporal sums, raster reprojection, and external
reference statistics have different error sources and must be justified
separately. Test Float32 science outputs even for Float64 caller inputs, while
protecting native coordinate precision and eager/lazy equivalence.

## Oracle, characterization, and regression cases

Label the evidence accurately:

* **Analytical/oracle tests** compare to independently evaluated equations,
  analytic results, or trusted external references.
* **Characterization tests** freeze verified existing behavior or configuration
  values. They protect compatibility but do not independently validate the
  underlying science.
* **Regression tests** reproduce a specific previously discovered defect and
  prove the corrected behavior remains protected.

Retain useful frozen parameter characterizations where they document a supported
scientific configuration, and label them as characterizations. Do not describe
their frozen outputs as independent validation.

## Data, fixtures, and integration

The required pull-request suite is small, data-free, and usable without
credentials, downloads, private files, or study-specific paths. Construct
minimal xarray objects in the test that uses them. Shared fixtures are useful
when they remove substantial repeated setup, but they should not hide grid,
unit, sign, or support assumptions. Keep fixture factories small and explicit.

At least one synthetic integration test should connect meaningful public
operations—for example, product phase conversion, reference handling,
support composition, phase-to-dSWE conversion, temporal
accumulation, and inspection of the final xarray result. Its expected values
should follow from a small analytical example.

Tests requiring externally supplied real mission products should be marked
`integration`, document their source metadata and environment variables, and remain
optional. They must not make the normal test suite depend on those files.
Optional NISAR input metadata and environment variables are recorded in
`tests/fixtures/README.md` alongside the tests and fixture manifests.

## Coverage and repository checks

Coverage is a diagnostic for unexecuted code, not a measure of scientific
validity. Do not inflate it with meaningless assertions, broad `no cover`
annotations, or exclusions of difficult scientific modules. Kernel and
temporal science should have stronger direct protection than peripheral I/O
plumbing. Review uncovered lines for meaningful scientific gaps before
changing the coverage floor. The CI floor is currently 85% overall line
coverage, measured after adding direct tests for scientific kernels,
temporal/reference behavior, and common product workflows. Coverage remains
diagnostic and does not claim that all scientific branches have independent
validation.

The local required checks are:

```bash
pytest -q
pytest --cov=snowin --cov-report=term-missing --cov-report=xml
ruff check .
ruff format --check .
python -m build
git diff --check
```

CI additionally installs a built wheel in a clean environment and imports it
while exercising a small public API call. Ruff is scoped to source, tests, and
scripts; Markdown and notebook documents are excluded because their embedded
examples and generated notebook cells need document-aware checks. The README
quick-start example is executed as a smoke test from its tagged code block.
Other product examples require real inputs or network access, so they remain
documented manual workflows and are not part of the normal offline suite.

## Supported dependencies

CI tests the latest resolvable development stack on each supported Python
version and a minimum scientific-dependency stack on Python 3.12. The declared
`numpy>=1.26` floor is the first NumPy release supporting Python 3.12. The
minimum job uses NumPy 1.26.4 with xarray 2024.1 on Python 3.12. See the
[NumPy 1.24 release notes](https://numpy.org/doc/1.24/release/1.24.0-notes.html)
and [NumPy 1.26 release notes](https://numpy.org/doc/1.26/release/1.26.0-notes.html).

Static type checking is not a SnowIn 0.1 release gate. Do not add strict rules
without evidence that they improve the public API without broad ignores or
scientific API distortions.

## Delivered phase regression (schema 0.2)

Protect identity ingestion of signed NISAR phase, explicit opposite-convention
conversion exactly once, and legacy-schema rejection. Independently evaluate
all three dry-snow equations for positive, negative, and zero canonical phase,
including each supported Guneriussen permittivity model. Reference contributor
phase and offsets must be radians in reference-minus-secondary convention.
An end-to-end synthetic case must retain chronological edges and signed
accumulation through referencing and missing support, in eager and lazy forms.
Optional real-product phase checks compare returned phase directly to delivered
`unwrappedPhase` on shared valid support; they do not establish snow attribution.

Temporal input regressions must require an explicit
`dswe_difference_definition="secondary_minus_reference"` on every dSWE
variable, including schema 0.2 and schema-unlabeled inputs. Dataset metadata
must not substitute for it. Cover missing/unsupported definitions, custom
variable names, and eager/lazy rejection, while retaining signed analytical
prefix sums and retrieval-produced metadata.
