"""Transcript cleaning (spec 5.4, steps 2 to 5)."""

import html
import re
from collections.abc import Sequence

from yt_digest_node.vtt import Cue

PARAGRAPH_GAP_SECONDS = 2.0

_TAG = re.compile(r"<[^>]*>")
_ANNOTATION = re.compile(r"\[[^\]]*\]")
_SPACES = re.compile(r"\s+")


def _clean_line(line: str) -> str:
    line = html.unescape(_TAG.sub("", line))
    return _SPACES.sub(" ", _ANNOTATION.sub("", line)).strip()


def is_sponsored(cue: Cue, segments: Sequence[tuple[float, float]]) -> bool:
    """Whether the midpoint of the cue lies in a segment (start inclusive, end exclusive)."""
    midpoint = (cue.start + cue.end) / 2
    return any(start <= midpoint < end for start, end in segments)


def clean_cues(cues: Sequence[Cue], segments: Sequence[tuple[float, float]]) -> list[str]:
    """Return the paragraphs of the cleaned text; `segments` are SponsorBlock (start, end) pairs."""
    paragraphs: list[list[str]] = []
    previous_line: str | None = None
    previous_end = 0.0
    for cue in cues:
        if is_sponsored(cue, segments):
            continue
        kept: list[str] = []
        for line in map(_clean_line, cue.lines):
            if line and line != previous_line:
                kept.append(line)
                previous_line = line
        if not kept:
            continue
        if not paragraphs or round(cue.start - previous_end, 3) >= PARAGRAPH_GAP_SECONDS:
            paragraphs.append([])
        paragraphs[-1].extend(kept)
        previous_end = cue.end
    return [" ".join(lines) for lines in paragraphs]
