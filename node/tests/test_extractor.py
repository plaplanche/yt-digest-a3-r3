import json
from pathlib import Path

import pytest

from yt_digest_node.extractor import Extraction, FakeExtractor, Track, choose_track
from yt_digest_node.ytdlp import YtDlpExtractor, make_extractor

VIDEO_ID = "abcdefghijk"


def make_video(root: Path, meta: dict[str, object], files: list[str]) -> None:
    video = root / VIDEO_ID
    video.mkdir()
    (video / "meta.json").write_text(json.dumps(meta))
    for name in files:
        (video / name).write_text(f"WEBVTT\n\n{name}")


def test_missing_directory_is_unavailable(tmp_path: Path) -> None:
    assert FakeExtractor(tmp_path).extract(VIDEO_ID) == "unavailable"


@pytest.mark.parametrize("status", ["blocked", "unavailable"])
def test_meta_status_is_returned_as_is(tmp_path: Path, status: str) -> None:
    make_video(tmp_path, {"duration": 10, "status": status}, ["en.manual.vtt"])
    assert FakeExtractor(tmp_path).extract(VIDEO_ID) == status


def test_tracks_and_duration_are_read(tmp_path: Path) -> None:
    make_video(tmp_path, {"duration": 12}, ["fr.auto.vtt", "en.manual.vtt", "notes.txt"])
    result = FakeExtractor(tmp_path).extract(VIDEO_ID)
    assert isinstance(result, Extraction)
    assert result.duration == 12
    assert {(t.lang, t.source) for t in result.tracks} == {("fr", "auto"), ("en", "manual")}


def test_manual_track_beats_earlier_language_auto_track(tmp_path: Path) -> None:
    make_video(tmp_path, {"duration": 1}, ["fr.auto.vtt", "en.manual.vtt"])
    result = FakeExtractor(tmp_path).extract(VIDEO_ID)
    assert isinstance(result, Extraction)
    track = choose_track(result.tracks, ["fr", "en"])
    assert track is not None and (track.lang, track.source) == ("en", "manual")


def test_auto_tracks_follow_language_order() -> None:
    tracks = [Track("en", "auto", ""), Track("fr", "auto", "")]
    track = choose_track(tracks, ["fr", "en"])
    assert track is not None and track.lang == "fr"


def test_no_matching_track(tmp_path: Path) -> None:
    make_video(tmp_path, {"duration": 1}, ["de.manual.vtt"])
    result = FakeExtractor(tmp_path).extract(VIDEO_ID)
    assert isinstance(result, Extraction)
    assert choose_track(result.tracks, ["fr", "en"]) is None


def test_make_extractor_selects_fake(tmp_path: Path) -> None:
    env = {"FETCHER_FAKE_YTDLP": "1", "FAKE_YTDLP_DIR": str(tmp_path)}
    assert isinstance(make_extractor(env, ["en"]), FakeExtractor)
    with pytest.raises(ValueError):
        make_extractor({"FETCHER_FAKE_YTDLP": "1"}, ["en"])
    assert isinstance(make_extractor({}, ["en"]), YtDlpExtractor)
