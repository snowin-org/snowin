# Contributing to SnowIn

Thanks for contributing.

## Development setup

```bash
python --version  # Python 3.12 or newer
python -m pip install -e ".[dev]"
pytest
ruff check .
ruff format --check .
python -m build
```

SnowIn uses a `src/` layout. Tests and examples should import the installed
package (`snowin`), not files by path or by modifying `sys.path`.

## Branch naming

Use short, descriptive branch names:

- `feature/core-swe-methods`
- `feature/gunw-reader`
- `docs/architecture`
- `fix/incidence-angle-validation`
- `chore/ci-setup`

## Pull request expectations

A PR should:
- address one issue or one tightly related issue set
- include tests for new functionality
- include docstring updates for public functions
- keep notebooks as examples, not as the home of core logic

## Style

- use snake_case for functions and variables
- keep public APIs stable and explicit
- prefer small modules with clear roles
- avoid copying large chunks from legacy repos without refactoring
- keep scientific conventions and provenance explicit
- do not commit generated caches, plots, or workflow outputs
