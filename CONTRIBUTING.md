# Contributing to SnowIn

Thanks for contributing.

## Development setup

```bash
python -m pip install -e ".[dev]"
pytest
```

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
