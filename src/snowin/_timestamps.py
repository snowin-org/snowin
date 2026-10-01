"""Shared parsing for timezone-aware SnowIn acquisition timestamps."""

from __future__ import annotations

from datetime import UTC, datetime


def parse_utc_timestamp(value: object, name: str) -> datetime:
    """Parse an ISO 8601 timestamp with an explicit timezone and return UTC."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        text = value.strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(
                f"{name} must be a valid ISO 8601 timestamp with an explicit UTC offset"
            ) from exc
    else:
        raise ValueError(
            f"{name} must be a valid ISO 8601 timestamp with an explicit UTC offset"
        )

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must include an explicit UTC offset")
    return parsed.astimezone(UTC)


def iso_utc_timestamp(value: object, name: str) -> str:
    """Return a timezone-aware ISO 8601 timestamp normalized to ``Z``."""
    return parse_utc_timestamp(value, name).isoformat().replace("+00:00", "Z")
