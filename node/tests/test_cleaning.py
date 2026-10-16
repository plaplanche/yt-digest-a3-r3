from pathlib import Path

from yt_digest_node.cleaning import clean_cues
from yt_digest_node.vtt import Cue, parse_vtt

FIXTURES = Path(__file__).parent / "fixtures" / "vtt"


def load(name: str) -> list[Cue]:
    return parse_vtt((FIXTURES / name).read_text(encoding="utf-8"))


def cue(start: float, end: float, *lines: str) -> Cue:
    return Cue(start, end, list(lines))


def test_parse_manual_track_ignores_header_blocks_and_settings() -> None:
    cues = load("manual.vtt")
    assert [(c.start, c.end) for c in cues] == [
        (1.0, 3.0),
        (3.0, 5.0),
        (7.0, 9.0),
        (70.0, 72.5),
    ]
    assert cues[0].lines == ["Bonjour à tous,"]
    assert cues[2].lines == ["Premier sujet.", "Deuxième ligne."]


def test_parse_handles_crlf_bom_and_short_timestamps() -> None:
    cues = parse_vtt("﻿WEBVTT\r\n\r\n01:02.250 --> 01:03.000\r\nHi\r\n")
    assert cues == [Cue(62.25, 63.0, ["Hi"])]


def test_manual_track_paragraphs() -> None:
    assert clean_cues(load("manual.vtt"), []) == [
        "Bonjour à tous, bienvenue dans cette vidéo.",
        "Premier sujet. Deuxième ligne.",
        "Une heure plus tard.",
    ]


def test_auto_track_removes_rolling_duplicates_and_inline_tags() -> None:
    assert clean_cues(load("auto.vtt"), []) == [
        "hello everyone and welcome to the channel today we talk"
    ]


def test_annotations_entities_and_tags() -> None:
    paragraphs = clean_cues(load("annotations.vtt"), [])
    text = "\n\n".join(paragraphs)
    assert "[" not in text
    assert "Musique" not in text and "Applause" not in text
    assert "Tom & Jerry are here." in text
    assert 'Café <3 "quotes" and spaces' in text


def test_gap_of_two_seconds_starts_paragraph_and_1_9_does_not() -> None:
    paragraphs = clean_cues(load("annotations.vtt"), [])
    # cue ending at 6.0 then starting at 7.9 (gap 1.9): same paragraph
    assert paragraphs[0].endswith("Gap of 1.9 seconds.")
    # cue ending at 9.0 then starting at 11.0 (gap 2.0): new paragraph
    assert paragraphs[1] == "Gap of 2.0 seconds."
    assert len(paragraphs) == 2


def test_gap_is_measured_from_previous_kept_cue() -> None:
    cues = [cue(0, 1, "a"), cue(1, 5, "[Musique]"), cue(5, 6, "b")]
    assert clean_cues(cues, []) == ["a", "b"]
    cues = [cue(0, 1, "a"), cue(1, 2, "[Musique]"), cue(2.9, 3, "b")]
    assert clean_cues(cues, []) == ["a b"]


def test_duplicate_line_only_compared_with_line_kept_just_before() -> None:
    cues = [cue(0, 1, "a", "b", "b", "a")]
    assert clean_cues(cues, []) == ["a b a"]


def test_sponsor_segments_drop_cues_by_midpoint() -> None:
    cues = [cue(0, 2, "a"), cue(2, 4, "b"), cue(4, 6, "c")]
    # midpoints 1, 3, 5; start inclusive, end exclusive
    assert clean_cues(cues, [(3.0, 5.0)]) == ["a", "c"]
    assert clean_cues(cues, [(1.0, 3.0)]) == ["b c"]
    assert clean_cues(cues, [(1.5, 3.0)]) == ["a b c"]


def test_empty_input() -> None:
    assert clean_cues([], []) == []
