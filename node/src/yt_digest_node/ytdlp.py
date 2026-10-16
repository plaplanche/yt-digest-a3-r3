"""yt-dlp extractor and extractor selection (spec 5.1, 5.2)."""

import random
import time
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, ClassVar, Protocol, Self

from yt_digest_node.extractor import Extraction, Extractor, Failure, FakeExtractor, Track

DEFAULT_DELAY = "2-5"

_BLOCKED_MARKERS = ("not a bot",)
_UNAVAILABLE_MARKERS = (
    "private video",
    "age",
    "removed",
    "unavailable",
    "does not exist",
    "terminated",
)


class YoutubeDL(Protocol):
    def __enter__(self) -> Self: ...

    def __exit__(self, *args: object) -> None: ...

    def extract_info(self, url: str, download: bool = ...) -> dict[str, Any]: ...


YoutubeDLFactory = Callable[[dict[str, Any]], AbstractContextManager[YoutubeDL]]


def _default_factory(options: dict[str, Any]) -> AbstractContextManager[YoutubeDL]:
    import yt_dlp  # type: ignore[import-untyped]

    return yt_dlp.YoutubeDL(options)  # type: ignore[no-any-return]


def _download_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read().decode("utf-8")  # type: ignore[no-any-return]


def map_error(message: str) -> Failure | None:
    text = message.lower()
    if any(marker in text for marker in _BLOCKED_MARKERS):
        return "blocked"
    if any(marker in text for marker in _UNAVAILABLE_MARKERS):
        return "unavailable"
    return None


def parse_delay(value: str) -> tuple[float, float]:
    low, _, high = value.partition("-")
    return float(low), float(high or low)


class YtDlpExtractor:
    """Only tracks in `langs` are downloaded: auto captions list hundreds of languages."""

    OPTIONS: ClassVar[dict[str, Any]] = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitlesformat": "vtt",
        "quiet": True,
    }

    def __init__(
        self,
        langs: Sequence[str],
        delay: tuple[float, float] = (2.0, 5.0),
        factory: YoutubeDLFactory = _default_factory,
        download_text: Callable[[str], str] = _download_text,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._langs = list(langs)
        self._delay = delay
        self._factory = factory
        self._download_text = download_text
        self._sleep = sleep

    def extract(self, video_id: str) -> Extraction | Failure:
        self._sleep(random.uniform(*self._delay))
        try:
            with self._factory(dict(self.OPTIONS)) as ydl:
                info = ydl.extract_info(
                    f"https://www.youtube.com/watch?v={video_id}", download=False
                )
        except Exception as error:
            failure = map_error(str(error))
            if failure is None:
                raise
            return failure
        tracks: list[Track] = []
        for source, key in (("manual", "subtitles"), ("auto", "automatic_captions")):
            for lang in self._langs:
                for entry in (info.get(key) or {}).get(lang, []):
                    if entry.get("ext") == "vtt":
                        tracks.append(Track(lang, source, self._download_text(entry["url"])))  # type: ignore[arg-type]
                        break
        return Extraction(float(info.get("duration") or 0), tracks)


def make_extractor(env: Mapping[str, str], langs: Sequence[str]) -> Extractor:
    """The fake extractor when `FETCHER_FAKE_YTDLP=1` (no delay), else yt-dlp."""
    if env.get("FETCHER_FAKE_YTDLP") == "1":
        fixture_dir = env.get("FAKE_YTDLP_DIR")
        if not fixture_dir:
            raise ValueError("FAKE_YTDLP_DIR is required when FETCHER_FAKE_YTDLP=1")
        return FakeExtractor(Path(fixture_dir))
    return YtDlpExtractor(langs, parse_delay(env.get("YT_DELAY_SECONDS", DEFAULT_DELAY)))
