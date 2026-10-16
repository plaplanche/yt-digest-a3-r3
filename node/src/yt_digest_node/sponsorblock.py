"""SponsorBlock client and sponsor ratio (spec 5.3)."""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from yt_digest_node.log import emit

TIMEOUT_SECONDS = 10
CATEGORIES = ["sponsor", "selfpromo", "interaction"]

State = Literal["ok", "none", "error"]


@dataclass(frozen=True)
class SponsorBlockResult:
    segments: list[tuple[float, float]]
    state: State


def _parse_segments(body: bytes) -> list[tuple[float, float]]:
    segments: list[tuple[float, float]] = []
    for item in json.loads(body):
        start, end = item["segment"]
        segments.append((float(start), float(end)))
    return segments


def fetch_segments(
    base_url: str, video_id: str, request_id: str | None = None
) -> SponsorBlockResult:
    """Call SponsorBlock once and log `sponsorblock.call`; never raises on a failed call."""
    query = urllib.parse.urlencode(
        {"videoID": video_id, "categories": json.dumps(CATEGORIES, separators=(",", ":"))}
    )
    url = f"{base_url.rstrip('/')}/api/skipSegments?{query}"
    started = time.monotonic()
    status = 0
    result = SponsorBlockResult([], "error")
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
            status = response.status
            body = response.read()
        if status == 200:
            result = SponsorBlockResult(_parse_segments(body), "ok")
    except urllib.error.HTTPError as error:
        status = error.code
        if status == 404:
            result = SponsorBlockResult([], "none")
    except (OSError, ValueError, KeyError, TypeError):
        pass
    emit(
        "sponsorblock.call",
        request_id=request_id,
        video_id=video_id,
        attrs={
            "status": status,
            "segments": len(result.segments),
            "duration_ms": round((time.monotonic() - started) * 1000),
        },
    )
    return result


def sponsor_ratio(segments: Sequence[tuple[float, float]], duration: float) -> float:
    """Length of the union of the segments clipped to [0, duration], over the duration."""
    if duration <= 0:
        return 0.0
    clipped = sorted(
        (max(0.0, start), min(duration, end)) for start, end in segments if start < end
    )
    covered = 0.0
    current_end = 0.0
    for start, end in clipped:
        start = max(start, current_end)
        if end > start:
            covered += end - start
            current_end = end
    return round(covered / duration, 3)
