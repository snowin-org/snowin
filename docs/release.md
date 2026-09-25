# Release process

SnowIn is pre-release software and is not yet published to PyPI or conda-forge.
Keep initial releases small and tied to a reviewed, reproducible source state.

Before the first release:

1. Obtain scientific and API review for the supported equations, phase sign,
   temporal direction, units, grid behavior, support semantics, and metadata.
2. Run the complete fast CI suite, including minimum/latest dependency jobs,
   package build, and clean wheel-install smoke test.
3. Run optional real-product checks with documented inputs where available;
   never require those files or credentials for the standard test suite.
4. Update `CHANGELOG.md`, `CITATION.cff`, package version metadata, and release
   notes with the exact commit and known scientific limitations.
5. Build and inspect both the source distribution and wheel. Confirm that the
   wheel contains the SnowIn package and does not bundle example data or
   study-specific processing scripts.
6. Publish the documentation from the reviewed release commit and create an
   annotated version tag.

Describe pairwise and cumulative dSWE as change relative to a radar epoch, not
as absolute SWE. Preserve explicit phase, vertical-datum, support, and
provenance metadata in released workflows.
