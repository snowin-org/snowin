# Release checklist

Use this checklist for each reviewed SnowIn source release.

1. Start from a clean main or release branch and confirm the reviewed commit.
2. Review and freeze the normalized data contract and public API for the
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
