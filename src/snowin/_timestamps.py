"""Parse SnowIn acquisition times with explicit timezone information."""

from __future__ import annotations

from datetime import UTC, datetime


def parse_utc_timestamp(value: object, name: str) -> datetime:
    """Parse an ISO 8601 timestamp with an explicit timezone and return UTC."""
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError(f"{name} is missing; provide a timestamp with a UTC offset")

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(
                f"{name} is invalid; expected an ISO 8601 timestamp with an "
                "explicit UTC offset"
            ) from exc
    else:
        raise ValueError(
            f"{name} has invalid type {type(value).__name__}; expected a datetime "
            "or ISO 8601 timestamp string"
        )

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} is missing an explicit UTC offset")
    return parsed.astimezone(UTC)


def iso_utc_timestamp(value: object, name: str) -> str:
    """Convert a timestamp to UTC and return ISO 8601 text ending in ``Z``."""
    return parse_utc_timestamp(value, name).isoformat().replace("+00:00", "Z")
