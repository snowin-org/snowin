# SnowIn Stage 2: reusable phase-to-dSWE kernel

Execute STAGE 2 ONLY.

Stage 1 is complete and committed at:

836204d Define SnowIn scientific data contracts

Treat the Stage 1 contracts as authoritative unless new primary scientific
evidence demonstrates that a contract is physically incorrect.

Stage 2 goal:
establish one scientifically verified, reusable phase-to-dSWE kernel.

Do not begin Stage 3.

===============================================================================
SCIENTIFIC CONTRACT ALREADY DECIDED
===============================================================================

SnowIn canonical normalized phase is:

    phase = phi_secondary - phi_reference

The directed temporal edge is:

    reference_time -> secondary_time

Pairwise dSWE is:

    dSWE = SWE_secondary - SWE_reference

Therefore positive canonical phase represents positive forward phase change.

Do NOT add a user-facing phase_sign switch to the new canonical API.

Raw NISAR/GUNW source-phase normalization belongs to the NISAR adapter in a
later stage, not in the generic dSWE kernel.

===============================================================================
FIRST: SCIENTIFIC PROVENANCE AUDIT
===============================================================================

Before changing production code, determine exactly what scientific equation
SnowIn v0.1 should implement.

Inspect:

1. Current SnowIn:
   - src/snowin/snow/swe.py
   - src/snowin/snow/snow_depth.py
   - workflows that call those functions
   - existing tests

2. Colorado repository:
   https://github.com/jacktarricone/nisar-grl-colorado-firstlook

   Pay particular attention to:
   - src/nisar_firstlook/phase.py
   - current frozen/reproduction configuration
   - any tests or scripts that exercise phase-to-dSWE behavior

3. Relevant prior snow implementations:
   - https://github.com/SnowEx/uavsar_pytools
   - https://github.com/SnowEx/uavsar_snow
   - https://github.com/rpalomaki/SWE_error_analysis/tree/v1.0
   - https://github.com/ehavazli/snowsar
   - https://github.com/ZachHoppinen/uavsar-validation

4. Primary published scientific references supporting the equation.

Do not use another repository as scientific authority if a primary publication
or formal algorithm description is available.

Record:

- exact equation;
- definition of each term;
- units;
- assumptions;
- sign convention;
- whether incidence is local or nominal;
- role of alpha if present;
- wavelength dependence;
- physical domain of validity.

If primary references and existing implementations disagree, STOP and report
the discrepancy rather than choosing silently.

===============================================================================
METHOD-NAMING AUDIT
===============================================================================

The current prototype exposes multiple method names including:

- guneriussen
- leinss
- oveisgharan

Audit whether these actually correspond to distinct published retrieval
equations.

In particular, determine whether the current "oveisgharan" implementation is
scientifically distinct or merely aliases the Leinss-style implementation.

Do not expose two public method names that execute the same mathematical
retrieval unless there is a documented scientific reason.

Do not preserve historical names simply for compatibility if they misrepresent
the implemented science.

If method identity cannot be verified, keep it private/deprecated or stop for
review.

===============================================================================
WAVELENGTH
===============================================================================

The current prototype contains approximate wavelength values such as 0.24 m.

The Colorado workflow uses:

    0.238403545 m

Do not silently preserve an approximate mission wavelength as the scientific
default.

Determine the proper generic SnowIn contract.

Preferred direction:

- generic kernel receives wavelength explicitly;
- a product adapter may later populate wavelength from authoritative metadata;
- no hidden NISAR-specific wavelength assumption in the generic kernel.

If a default wavelength is retained for any compatibility function, clearly
mark its provenance and status.

===============================================================================
ANGLE UNITS
===============================================================================

Stage 1 established radians as the scientific-kernel incidence-angle unit.

Remove automatic degree/radian guessing from the NEW canonical API.

Do not infer units based on numerical magnitude.

Invalid or ambiguous units should fail clearly.

Do not casually break legacy prototype functions if they are needed for
characterization. Compatibility behavior may remain temporarily, but it must
be clearly separated from the new canonical API.

===============================================================================
XARRAY-NATIVE API
===============================================================================

The new stable scientific API should be xarray-native.

Design the smallest useful API, likely conceptually similar to:

    compute_dswe(phase, incidence_angle, *, wavelength_m, ...)

but determine the exact signature from the scientific audit.

For xarray.DataArray inputs preserve as appropriate:

- dimensions;
- coordinates;
- missing values;
- lazy array backing;
- relevant attrs/provenance.

Avoid:

- .load()
- .values
- unconditional np.asarray()

in the reusable xarray computational path unless technically required and
explicitly justified.

Prefer native arithmetic that naturally preserves xarray/Dask behavior.

If scalar/NumPy support can be retained cleanly without complicating the API,
that is acceptable, but xarray behavior is the primary package contract.

===============================================================================
DEPENDENCY DECISION
===============================================================================

If xarray becomes part of SnowIn's stable public scientific API in Stage 2,
move xarray from optional/development dependencies into the package's core
runtime dependencies.

Dask should remain optional.

Do not add the broader Pangeo stack.

===============================================================================
TESTS
===============================================================================

Add scientific and API tests for at least:

- zero phase -> zero dSWE;
- positive canonical phase -> positive dSWE;
- negative canonical phase -> negative dSWE;
- known scalar calculation from the verified equation;
- wavelength dependence;
- incidence-angle dependence;
- NaN propagation;
- xarray dimensions preserved;
- xarray coordinates preserved;
- relevant attrs/provenance;
- invalid wavelength;
- invalid incidence units / ambiguous units;
- NumPy/scalar behavior if supported;
- Dask-backed equivalence if Dask is available as an optional dev dependency.

Add a Colorado characterization/regression test or comparison using known
inputs/outputs where feasible.

Do not tune the implementation to improve agreement with ASO or any validation
dataset.

===============================================================================
COLORADO RELATIONSHIP
===============================================================================

Do not migrate Colorado code into SnowIn merely because it works.

Use the Colorado implementation as:

- characterization evidence;
- regression evidence;
- a source of exercised scientific behavior.

The Colorado repository currently contains historical phase-sign branches.
Do not treat the exploratory `sign_plus` branch as physical sign authority.

Audit its source-to-retrieval lineage, but do not modify the Colorado study in
this stage.

The generic SnowIn kernel must operate on canonical normalized phase only.

===============================================================================
PROVENANCE
===============================================================================

Update docs/code_provenance.md with:

- capability;
- primary scientific publication/reference;
- exact equation implemented;
- external repositories inspected;
- implementation relationship;
- whether code was independently reimplemented or adapted;
- licensing implications;
- regression evidence;
- remaining uncertainties.

Do not invent citations or DOI information.

===============================================================================
VALIDATION
===============================================================================

Run:

    python -m pip install -e ".[dev]"
    pytest -q
    ruff check .
    ruff format --check .
    python -m build
    git diff --check

Do not commit automatically.

===============================================================================
CHECKPOINT
===============================================================================

STOP after Stage 2.

Report separately:

A. Scientific equation provenance
B. Exact equation implemented
C. Public API design
D. Method-name audit
E. Wavelength decision
F. Angle-unit decision
G. Xarray/Dask behavior
H. Dependency changes
I. Numerical regression evidence
J. Differences from old SnowIn behavior
K. Differences from Colorado implementation
L. Tests and validation
M. Unresolved scientific questions
N. Recommended next action

Do not start the NISAR adapter or Stage 3.
