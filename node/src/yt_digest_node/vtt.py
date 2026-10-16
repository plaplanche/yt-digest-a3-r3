"""WebVTT parsing (spec 5.4, step 1)."""

import re
from dataclasses import dataclass

_TIMESTAMP = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})\.(\d{3})")
_TIMING = re.compile(rf"({_TIMESTAMP.pattern})\s+-->\s+({_TIMESTAMP.pattern})")
_IGNORED_BLOCKS = ("WEBVTT", "NOTE", "STYLE", "REGION")


@dataclass(frozen=True)
class Cue:
    start: float
    end: float
    lines: list[str]


def _seconds(hours: str | None, minutes: str, seconds: str, millis: str) -> float:
    return int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000


def parse_vtt(text: str) -> list[Cue]:
    """Parse VTT text into cues, ignoring the header, NOTE/STYLE/REGION blocks and cue settings."""
    blocks = re.split(r"\n{2,}", text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n"))
    cues: list[Cue] = []
    for block in blocks:
        lines = block.strip("\n").split("\n")
        if lines[0].split(" ")[0].split("\t")[0] in _IGNORED_BLOCKS:
            continue
        for i, line in enumerate(lines):
            match = _TIMING.search(line)
            if match:
                start = _seconds(*match.group(2, 3, 4, 5))
                end = _seconds(*match.group(7, 8, 9, 10))
                cues.append(Cue(start, end, lines[i + 1 :]))
                break
    return cues
