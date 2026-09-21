# Scientific conventions

This is a Stage 0 placeholder for the reviewed scientific contracts that will
be completed before new retrieval architecture is added. The following
conventions are the intended internal defaults:

- phase is in radians;
- incidence angle is in radians in scientific kernels;
- wavelength is in metres;
- dSWE is in metres water equivalent internally;
- temporal direction and reference/secondary ordering are explicit;
- CRS and grid relationships are preserved and validated;
- pairwise dSWE is distinct from cumulative dSWE and from absolute SWE.

The package must not hide phase-sign conventions, silently substitute a
mission wavelength, or treat missing temporal support as zero change.

The existing prototype predates the final contract in a few places. In
particular, `phase_raster_to_dswe(..., incidence_angle_unit="auto")` retains a
warning-producing degree/radian inference path for demonstration compatibility.
That behavior is recorded here as technical/scientific debt. Stage 1 must
decide whether the public contract rejects ambiguity or supports an explicit
metadata-based conversion before later retrieval work relies on it.

No scientific algorithm was changed as part of Stage 0.
