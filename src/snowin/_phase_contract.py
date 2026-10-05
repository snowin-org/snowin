"""Validation shared by phase retrieval and referencing operations."""

from collections.abc import Mapping
from typing import Any

PHASE_DEFINITION = "reference_minus_secondary"
DSWE_DEFINITION = "secondary_minus_reference"


def require_canonical_phase(attrs: Mapping[str, Any], label: str) -> None:
    """Reject ambiguous or legacy phase without changing numeric values."""
    if attrs.get("snowin_schema_version") == "0.1":
        raise ValueError(
            f"{label} uses legacy SnowIn schema 0.1; explicitly convert the "
            "recorded numeric phase convention with normalize_gunw_pair or "
            "re-read the GUNW. See docs/phase_migration.md; do not relabel phase "
            "or automatically negate saved dSWE."
        )
    definition = attrs.get("phase_difference_definition")
    if definition is None:
        raise ValueError(
            f"{label} phase_difference_definition is missing; "
            "declare reference_minus_secondary; see docs/phase_migration.md"
        )
    if definition != PHASE_DEFINITION:
        raise ValueError(
            f"{label} phase_difference_definition is {definition!r} "
            "(missing or unsupported); expected 'reference_minus_secondary'. "
            "Convert explicitly at the adapter boundary with normalize_gunw_pair; "
            "see docs/phase_migration.md."
        )
