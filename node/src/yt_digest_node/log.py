"""Structured logger: one JSON line per event on standard error, validated against the contract."""

import sys
from datetime import UTC, datetime
from typing import Any

from yt_digest_node.contracts.log_event import LogEvent


def emit(event: str, level: str = "info", **fields: Any) -> None:
    """Write one log line; raise ValueError on an event outside the catalogue or an unknown field."""
    now = datetime.now(UTC).isoformat(timespec="milliseconds").removesuffix("+00:00") + "Z"
    line: dict[str, Any] = {
        "ts": now,
        "level": level,
        "service": "node",
        "event": event,
        "attrs": {},
        **fields,
    }
    model = LogEvent.model_validate(line)
    sys.stderr.write(model.model_dump_json(exclude_none=True) + "\n")
