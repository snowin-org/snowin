# Scientific sources and equations

This page identifies the publications behind the selectable SnowIn retrieval
and density/permittivity formulations. Equations are implemented independently
in SnowIn. Phase and dSWE orientation follow the [SnowIn phase convention](scientific_conventions.md).

## Phase-to-dSWE retrievals

### Guneriussen density-dependent retrieval

`compute_guneriussen_dswe()` follows the dry-snow refraction relation from
Guneriussen et al. (2001),
[“InSAR for estimation of changes in snow water equivalent of dry snow”](https://doi.org/10.1109/36.957273),
*IEEE Transactions on Geoscience and Remote Sensing*, 39(10), 2101–2108.
With `κ = 2π / wavelength_m` and
`C = cos(θ) - sqrt(ε - sin²(θ))`, the phase-to-depth relation is
`phase = -2 κ C Δsnow_depth`. The SWE change is then
`ΔSWE = Δsnow_depth * (ρ_s / ρ_w)`. SnowIn makes these two physical steps
explicit in the implementation. The sign shown is the one used with the
SnowIn phase and temporal-edge definitions.

The `permittivity_model="guneriussen2001"` option names this phase-to-depth
formulation. Its rounded dry-snow density relation is
`ε = 1 + 1.6ρ + 1.8ρ³`, with `ρ` in g cm⁻³. The underlying density/permittivity
parameterization is attributed to Mätzler and Wiesmann in later literature;
the underlying dry-snow permittivity measurements are described by
[Mätzler (1996)](https://doi.org/10.1109/36.485133) and the layered snowpack
model by [Wiesmann and Mätzler (1999)](https://doi.org/10.1016/S0034-4257(99)00046-2).
The rounded expression and kg m⁻³ form used here are printed as Eq. 2 by
[Hoppinen et al. (2025)](https://tc.copernicus.org/articles/19/2895/2025/).
See also the [Mätzler option](#matzler-piecewise-permittivity-maetzler).

### Leinss approximation

`compute_leinss_dswe()` implements Eq. 18 from Leinss et al. (2015),
[“Snow Water Equivalent of Dry Snow Measured by Differential Interferometry”](https://doi.org/10.1109/JSTARS.2015.2432031),
*IEEE Journal of Selected Topics in Applied Earth Observations and Remote
Sensing*. SnowIn requires incidence in radians and uses
`dSWE = phase * wavelength_m / (2π * α * (1.59 + θ**2.5))`.
The empirical angle term uses radians numerically. This is a dry-snow change
approximation, not an absolute-SWE model.

### Oveisgharan fitted retrieval

`compute_oveisgharan_dswe()` implements Eq. 4 from Oveisgharan et al. (2024),
[“Snow water equivalent retrieval over Idaho – Part 1: Using Sentinel-1
repeat-pass interferometry”](https://doi.org/10.5194/tc-18-559-2024),
*The Cryosphere*, 18, 559–574. The fitted polynomial is
`A(θ) = -0.6784θ² + 0.2899θ - 0.8473`, and
`dSWE = phase / (-2κ A(θ))`. The paper reports a fit over incidence angles
through 80° and terrestrial snow densities of 0.15–0.45 g cm⁻³, with error
below 10% for incidence angles below 70°. The public SnowIn function does not
accept density because the fitted method removes that input from its equation.

## Density-to-permittivity formulations

The `permittivity_model` option selects the real relative permittivity used by
the Guneriussen phase-depth relation. All three models describe dry snow; wet
snow requires a different dielectric treatment.

### Rounded low-density relation (`guneriussen2001`)

The rounded cubic expression is `ε = 1 + 1.6ρ + 1.8ρ³`, with density `ρ` in
g cm⁻³. It is the rounded form of the Mätzler/Wiesmann dry-snow relation
reproduced in [Hoppinen et al. (2025), Eq. 2](https://tc.copernicus.org/articles/19/2895/2025/).
This option name refers to the retrieval formulation; it does not mean that
Guneriussen et al. introduced the density fit.

### Webb et al. dry-snow relation (`webb2021`)

`webb2021` uses
`ε = 1 + 1.4×10⁻³ρ + 2×10⁻⁷ρ²`, with density `ρ` in kg m⁻³. This is the dry-
snow relationship from Webb et al. (2021),
[“In Situ Determination of Dry and Wet Snow Permittivity: Improving Equations
for Low Frequency Radar Applications”](https://doi.org/10.3390/rs13224617),
*Remote Sensing*, 13(22), 4617, read with its
[2022 correction](https://doi.org/10.3390/rs14174407). The published work
compares field-measured seasonal snow permittivity; the equation should not be
treated as a universal model for wet snow or all snow conditions.

### Mätzler piecewise permittivity (`maetzler`)

`maetzler` uses the piecewise relation reproduced as Eq. 1 by
[Oveisgharan et al. (2024)](https://doi.org/10.5194/tc-18-559-2024) and
attributed there to Mätzler (1987):

- for `ρ < 0.4 g cm⁻³`, `ε = 1 + 1.5995ρ + 1.861ρ³`;
- for `ρ ≥ 0.4 g cm⁻³`,
  `ε = ((1 - ρ/0.917) + 1.4759ρ/0.917)³`.

The density in these expressions is in g cm⁻³. The piecewise threshold and
coefficients are part of the selected model.

## NISAR adapter and geometry

The NISAR adapter preserves the documented GUNW phase orientation and values, resolves wavelength from `centerFrequency`, and
records source metadata. The NISAR L2 Product Format Document v1.2.1 specifies
the identification `ZeroDopplerStartTime` fields as UTC, although their
timestamp text may omit an offset; the adapter applies that mission-specific
rule, while generic SnowIn timestamps still require `Z` or an explicit offset
([product format document](https://bhoonidhi.nrsc.gov.in/NISAR/NISAR_Data_Product_Format_Document_V1.2.1_digisigned.pdf)).
Terrain-local incidence uses DEM elevations,
`heightAboveEllipsoid`, LOS vectors, and the target grid. Product ellipsoid
incidence instead reads the GUNW radar-grid `incidenceAngle` field. These are
distinct geometry calculations; see the
[NISAR DEM and vertical-datum guidance](vertical_datums.md).

## Scope

The retrieval methods estimate pairwise dry-snow SWE change. They do not by
themselves remove atmospheric or ionospheric phase, establish snow-state
support, resolve unwrapping errors, or demonstrate agreement with independent
field observations. A real-product acceptance workflow still needs independent
checks of phase orientation, geometry, density/permittivity assumptions, and
dSWE sign and magnitude.

## Phase sign audit

The [ASF NISAR GUNW guide](https://nisar-docs.asf.alaska.edu/gunw/)
describes GUNW as geocoded RUNW phase in radians and lists correction screens
that are delivered without application. The subtraction order is established
by the authoritative [ISCE3 Crossmul implementation](https://github.com/isce-framework/isce3/blob/36f0b36b0e07679621c654ad19e9f90bd68c2307/cxx/isce3/signal/Crossmul.cpp#L268-L275):
reference SLC multiplied by the complex conjugate of secondary SLC. For
`SLC = amplitude * exp(i*phi)`, its argument is `phi_reference - phi_secondary`.
SnowIn preserves that orientation through unwrapped GUNW ingestion; acquisition
roles and chronological reference-to-secondary edges are unchanged.

The connection to accumulation follows the dry-snow delay equation, rather
than numeric inspection of a product. [Oveisgharan et al. (2024), Eq. 1](https://tc.copernicus.org/articles/18/559/2024/#section2)
prints the Guneriussen/Leinss refraction relation. Let
`C = cos(theta) - sqrt(epsilon - sin(theta)**2)`. For dry snow `epsilon > 1`
and `0 <= theta < pi/2`, `C < 0`, so `phase = -2*k*C*delta_depth` has positive
sensitivity to increasing depth. With positive snow/water density, increasing
depth gives positive dSWE. This is consistent with reference-minus-secondary
interferometry of the delayed secondary echo.

Each implemented inverse equation has positive scaling in its supported domain:

- Leinss: wavelength, alpha, and `1.59 + theta**2.5` are positive.
- Guneriussen: each supported density model has `epsilon > 1` for
  `0 < density < 917 kg m-3`, so `-2*k*C` and the density ratio are positive.
- Oveisgharan: `A(theta)` is negative (its discriminant is negative and its
  leading coefficient is negative), so `-2*k*A(theta)` is positive. Its physical
  fit limits remain those documented above; algebraic positivity does not
  extend the empirical validation domain.

No coefficient or blanket retrieval negation changes in schema 0.2.
These signs describe the isolated dry-snow contribution. Delivered measured
phase can also contain atmosphere, deformation, unwrapping errors, reference
offsets, and other contributions. Identity ingestion is not an assertion that
all positive measured phase is accumulation. Correction values, units, native
grids, and provenance remain delivered; application requires an explicit sign
and alignment decision. No unresolved algebraic sign discrepancy was found;
real-product SWE accuracy remains a separate validation task.
