# Release process

SnowIn is not yet published to PyPI or Conda. Until the scientific workflow is
stable, releases should remain deliberate and small.

Before the first tag:

1. Reproduce the clean Python 3.12 CI checks, including the isolated wheel and
   `snowin-plot-gunw --help` smoke test.
2. Run the external real-product geometry and Colorado phase-lineage checks;
   do not commit raw GUNW, DEM, or generated figure files.
3. Update `CHANGELOG.md`, `CITATION.cff`, version metadata, and the release
   notes with the exact commit and scientific limitations.
4. Build the sdist and wheel from the tagged commit and inspect their contents.
5. Publish documentation from `main`, then create the annotated version tag.

The first release must continue to describe pairwise/cumulative dSWE as change
relative to a radar epoch, not as absolute SWE, and must retain explicit phase,
vertical-datum, support, and provenance metadata.

## Previously completed internal validation

Earlier internal validation completed the clean Python 3.12 wheel install,
package import, CLI help smoke test, strict MkDocs build, package build, and
real Colorado GUNW/NISAR-DEM geometry and phase-lineage checks. Public release
work is intentionally deferred while collaborators review the notebooks and
the canonical-versus-legacy GUNW workflow boundary. The remaining scientific
gate is the explicit Colorado `T0_DELIVERED` phase-normalization decision and
its downstream output comparison.
