from typing import Any, Self

import pytest

from yt_digest_node.extractor import Extraction
from yt_digest_node.ytdlp import YtDlpExtractor, parse_delay

INFO: dict[str, Any] = {
    "duration": 42,
    "subtitles": {
        "en": [{"ext": "json3", "url": "u/en.json3"}, {"ext": "vtt", "url": "u/en.vtt"}],
        "de": [{"ext": "vtt", "url": "u/de.vtt"}],
    },
    "automatic_captions": {"fr": [{"ext": "vtt", "url": "u/fr.vtt"}]},
}


class StubYDL:
    def __init__(self, info: dict[str, Any] | Exception, calls: list[Any]) -> None:
        self.info = info
        self.calls = calls

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def extract_info(self, url: str, download: bool = True) -> dict[str, Any]:
        self.calls.append((url, download))
        if isinstance(self.info, Exception):
            raise self.info
        return self.info


def make(
    info: dict[str, Any] | Exception, calls: list[Any], sleeps: list[float] | None = None
) -> YtDlpExtractor:
    def factory(options: dict[str, Any]) -> StubYDL:
        calls.append(options)
        return StubYDL(info, calls)

    return YtDlpExtractor(
        ["fr", "en"],
        delay=(2, 5),
        factory=factory,
        download_text=lambda url: f"text:{url}",
        sleep=(sleeps if sleeps is not None else []).append,
    )


def test_options_and_result() -> None:
    calls: list[Any] = []
    sleeps: list[float] = []
    result = make(INFO, calls, sleeps).extract("abcdefghijk")
    assert calls[0] == {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitlesformat": "vtt",
        "quiet": True,
    }
    assert "cookiefile" not in calls[0] and "cookiesfrombrowser" not in calls[0]
    assert calls[1] == ("https://www.youtube.com/watch?v=abcdefghijk", False)
    assert len(sleeps) == 1 and 2 <= sleeps[0] <= 5
    assert isinstance(result, Extraction)
    assert result.duration == 42
    assert [(t.lang, t.source, t.vtt) for t in result.tracks] == [
        ("en", "manual", "text:u/en.vtt"),
        ("fr", "auto", "text:u/fr.vtt"),
    ]


@pytest.mark.parametrize(
    "message",
    [
        "ERROR: [youtube] x: Private video. Sign in if you've been granted access",
        "ERROR: [youtube] x: Sign in to confirm your age",
        "ERROR: [youtube] x: Video unavailable",
        "ERROR: [youtube] x: This video has been removed by the uploader",
    ],
)
def test_unavailable_errors(message: str) -> None:
    assert make(Exception(message), []).extract("abcdefghijk") == "unavailable"


def test_bot_check_is_blocked() -> None:
    error = Exception("ERROR: [youtube] x: Sign in to confirm you’re not a bot")
    assert make(error, []).extract("abcdefghijk") == "blocked"


def test_unknown_error_propagates() -> None:
    with pytest.raises(Exception, match="boom"):
        make(Exception("boom"), []).extract("abcdefghijk")


def test_parse_delay() -> None:
    assert parse_delay("2-5") == (2.0, 5.0)
    assert parse_delay("0") == (0.0, 0.0)
