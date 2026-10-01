# Independent acceptance review and release sequence

SnowIn remains pre-0.1 until Zach and Ross have independently run and reviewed
the current commit. The next step is acceptance review, not release packaging.

## Zach and Ross acceptance review

Each reviewer should independently clone or fetch the current SnowIn commit,
create a fresh environment, install the package with the `nisar`, `geometry`,
and `dask` extras plus development and notebook tools, and run the automated
checks documented in [development](development.md). Each reviewer should then:

1. Run Notebook 01 and confirm it remains synthetic and offline.
2. Run Notebook 02 in bundled-sample mode.
3. Run Notebook 02 with a real NISAR GUNW and matching NISAR-modified
   Copernicus DEM, when suitable data are available.
4. Inspect phase orientation, incidence geometry, DEM vertical-reference
   metadata, and dSWE sign and magnitude.
5. Compare results with an independent trusted implementation or calculation,
   rather than only with output derived from SnowIn.
6. Report unexpected behavior and observations that need resolving.

Do not add private data paths, credentials, or large research products to the
repository. A Colorado acceptance case can be used when it is already
available to the reviewer.

## Deferred release checklist

Only after both reviews are complete and their findings are resolved should a
separate release decision and packaging task begin. That later task should:

1. Start from a clean main or release branch and confirm the reviewed commit.
2. Review the supported Dataset variables, attributes, and public API for the
   release; record the schema version.
3. Run tests, coverage, Ruff, strict MkDocs, package build, and wheel smoke
   checks from the release environment.
4. Check the version in pyproject.toml, snowin.__version__, CHANGELOG.md, and
   CITATION.cff. Confirm Python and runtime dependency floors and license data.
5. Build the sdist and wheel with python -m build; inspect their contents and
   run python -m twine check dist/*.
6. Install the wheel in a new temporary environment with base dependencies.
   Check imports, a synthetic dSWE call, and useful optional-extra errors.
7. Create and push an annotated version tag at the reviewed commit.
8. Create the GitHub Release from that tag with the matching changelog notes.
9. Publish the checked sdist and wheel to PyPI.
10. Confirm the published install and documentation links. The docs workflow
    validates the site; GitHub Pages deployment requires Pages to be enabled.
11. Begin conda-forge packaging as a separate recipe and review.

Keep credentials out of this repository. Describe pairwise and cumulative
dSWE as changes relative to a radar epoch, not as absolute SWE.
