# SnowIn team workflow

## Recommended workstreams

1. Snow methods
2. NISAR I/O and data model
3. Ancillary and validation
4. Software engineering and release

## Suggested ownership model

Each workstream should have:
- one lead maintainer
- one backup reviewer
- several contributors

## Rules of engagement

- All stable new functionality goes into SnowIn, not side repos.
- Notebooks demonstrate package functionality; they do not contain canonical logic.
- Migration from legacy repos happens through issues and pull requests.
- Every migrated function gets renamed and documented in SnowIn style.

## Recommended GitHub labels

- `methods`
- `io`
- `validation`
- `docs`
- `tests`
- `good first issue`
- `needs design`
- `blocked`
