from __future__ import annotations

import os
from datetime import datetime, timezone

from engine import StreamsError


def now() -> datetime:
    text = os.environ.get("PI_STREAMS_NOW", "")
    if text == "":
        return datetime.now(timezone.utc)
    value = parse(text)
    if value is None:
        raise StreamsError(f"PI_STREAMS_NOW is not an ISO timestamp: {text}")
    return value


def parse(text: object) -> datetime | None:
    if not isinstance(text, str):
        return None
    try:
        value = datetime.fromisoformat(text)
    except ValueError:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
