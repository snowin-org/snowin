# Stage 0 prompt: stabilize the project

Using `docs/codex_prompts/master.md` and the SnowIn master development
instructions, execute Stage 0 only.

## Goal

Stabilize the existing local SnowIn project as a trustworthy modern Python
package before changing scientific architecture. Do not implement new snow
algorithms in this stage.

## First inspect the actual local repository

Run and inspect:

```bash
git status
git branch --show-current
git log --oneline --decorate -15
find . -maxdepth 3 -type f | sort
```

Read `pyproject.toml`, `README.md`, `CONTRIBUTING.md`, any `AGENTS.md`,
`docs/`, `src/snowin/`, `tests/`, `examples/`, `.github/`, and
`docs/snowin_architecture_v1.md` when present. If the local tree differs from
GitHub planning documentation, preserve local work and report the discrepancy.

## Tasks

1. Establish Python `>=3.12` consistently in packaging metadata, Ruff, CI,
   documentation, and environment/config files. Remove stale assumptions.
2. Verify the `src/` layout, installed-package test behavior, editable install,
   and absence of `sys.path` hacks.
3. Audit repository hygiene. Ignore caches, machine-specific files, generated
   plots/results, temporary files, and packaging artifacts as appropriate. Do
   not delete scientifically important data without review.
4. Audit `pyproject.toml`. Keep setuptools, verify PEP 621 metadata and useful
   project URLs, and keep base/runtime dependencies minimal.
5. Establish a simple quality toolchain using pytest, `ruff check`,
   `ruff format --check`, and `python -m build`. Do not force strict mypy on
   immature scientific code.
6. Add minimal GitHub Actions CI using Python 3.12, package installation,
   tests, lint, formatting checks, and no private data.
7. Audit imports and public exports. Do not import study repositories,
   examples, tests, or scripts from package code. Do not redesign the science
   API yet.
8. Preserve current behavior. Run the existing tests before and after edits;
   characterize failures and do not rewrite tests merely to make them pass.
9. Establish/update architecture, development workflow, scientific
   conventions placeholder, data-model placeholder, and code-provenance
   framework documentation.
10. Record scientific or technical debt for later stages rather than casually
    changing questionable retrieval behavior.

## Validation

Where available, run:

```bash
python -m pip install -e ".[dev]"
pytest -q
ruff check .
ruff format --check .
python -m build
git diff --check
```

Use an explicitly supported Python interpreter or environment if the shell has
no `python` command, and report that environmental limitation.

## Stop condition

Stop after Stage 0. Provide the full checkpoint report required by the master
prompt and recommend Stage 1 without starting it.
