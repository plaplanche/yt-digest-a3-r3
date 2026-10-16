"""Extractor interface, fake extractor and track choice (spec 5.2)."""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

Source = Literal["manual", "auto"]
Failure = Literal["unavailable", "blocked"]


@dataclass(frozen=True)
class Track:
    lang: str
    source: Source
    vtt: str


@dataclass(frozen=True)
class Extraction:
    duration: float
    tracks: list[Track]


class Extractor(Protocol):
    def extract(self, video_id: str) -> Extraction | Failure: ...


class FakeExtractor:
    """Reads `<fixture_dir>/<video_id>/meta.json` and `<lang>.<manual|auto>.vtt`."""

    def __init__(self, fixture_dir: Path) -> None:
        self._dir = fixture_dir

    def extract(self, video_id: str) -> Extraction | Failure:
        video_dir = self._dir / video_id
        if not video_dir.is_dir():
            return "unavailable"
        meta = json.loads((video_dir / "meta.json").read_text(encoding="utf-8"))
        status = meta.get("status")
        if status == "unavailable":
            return "unavailable"
        if status == "blocked":
            return "blocked"
        tracks: list[Track] = []
        for path in sorted(video_dir.glob("*.vtt")):
            lang, _, source = path.name.removesuffix(".vtt").rpartition(".")
            if lang and source in ("manual", "auto"):
                text = path.read_text(encoding="utf-8")
                tracks.append(Track(lang, "manual" if source == "manual" else "auto", text))
        return Extraction(float(meta["duration"]), tracks)


def choose_track(tracks: Sequence[Track], langs: Sequence[str]) -> Track | None:
    """Manual tracks in language order, then auto tracks in language order."""
    for source in ("manual", "auto"):
        for lang in langs:
            for track in tracks:
                if track.source == source and track.lang == lang:
                    return track
    return None
