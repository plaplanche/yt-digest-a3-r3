"""The `yt-digest-node` command (spec 5)."""

import argparse
import os
import re
import sys
import time
from collections.abc import Mapping, Sequence
from importlib.metadata import version

from yt_digest_node.cleaning import clean_cues
from yt_digest_node.contracts.transcript_result import TranscriptResult
from yt_digest_node.extractor import Extraction, choose_track
from yt_digest_node.log import emit
from yt_digest_node.pages import count_words, paginate, truncate
from yt_digest_node.sponsorblock import SponsorBlockResult, fetch_segments, sponsor_ratio
from yt_digest_node.vtt import parse_vtt
from yt_digest_node.ytdlp import make_extractor

VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="yt-digest-node")
    commands = parser.add_subparsers(dest="command", required=True)
    transcript = commands.add_parser("transcript", help="print the transcript result of a video")
    transcript.add_argument("video_id")
    transcript.add_argument("--langs")
    transcript.add_argument("--request-id")
    return parser


def _int_setting(env: Mapping[str, str], name: str, default: int) -> int:
    value = int(env.get(name, default))
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value


def _empty(video_id: str, status: str) -> TranscriptResult:
    return TranscriptResult.model_validate(
        {
            "video_id": video_id,
            "status": status,
            "lang": None,
            "source": None,
            "word_count": 0,
            "truncated": False,
            "sponsor_ratio": None,
            "pages": [],
        }
    )


def run(argv: Sequence[str], env: Mapping[str, str]) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    video_id: str = args.video_id
    request_id: str | None = args.request_id
    if not VIDEO_ID.fullmatch(video_id):
        parser.error(f"invalid video id: {video_id!r}")
    langs = [
        lang for lang in (args.langs or env.get("TRANSCRIPT_LANGS", "fr,en")).split(",") if lang
    ]
    try:
        max_words = _int_setting(env, "MAX_WORDS", 60000)
        page_words = _int_setting(env, "PAGE_WORDS", 12000)
        extractor = make_extractor(env, langs)
    except ValueError as error:
        parser.error(str(error))

    emit("service.started", request_id=request_id, attrs={"version": version("yt-digest-node")})
    started = time.monotonic()
    result = _empty(video_id, "unavailable")
    sponsorblock = "none"
    ratio: float | None = None

    extraction = extractor.extract(video_id)
    if not isinstance(extraction, Extraction):
        result = _empty(video_id, extraction)
    else:
        track = choose_track(extraction.tracks, langs)
        if track is None:
            result = _empty(video_id, "no_transcript")
        else:
            blocks: SponsorBlockResult = fetch_segments(
                env.get("SPONSORBLOCK_URL", "https://sponsor.ajay.app"), video_id, request_id
            )
            sponsorblock = blocks.state
            if blocks.state != "error":
                ratio = sponsor_ratio(blocks.segments, extraction.duration)
            paragraphs = clean_cues(parse_vtt(track.vtt), blocks.segments)
            paragraphs, truncated = truncate(paragraphs, max_words)
            pages = paginate(paragraphs, page_words)
            if not pages:
                result = _empty(video_id, "no_transcript")
            else:
                result = TranscriptResult(
                    video_id=video_id,
                    status="ok",
                    lang=track.lang,
                    source=track.source,
                    word_count=count_words([p for p in paragraphs if p != "[…]"]),
                    truncated=truncated,
                    sponsor_ratio=ratio,
                    pages=pages,
                )

    emit(
        "fetch.transcript",
        request_id=request_id,
        video_id=video_id,
        attrs={
            "outcome": result.status,
            "source": result.source,
            "words": result.word_count,
            "pages": len(result.pages),
            "sponsor_ratio": result.sponsor_ratio,
            "sponsorblock": sponsorblock,
            "duration_ms": round((time.monotonic() - started) * 1000),
        },
    )
    sys.stdout.write(result.model_dump_json() + "\n")
    return 0


def main() -> None:
    sys.exit(run(sys.argv[1:], os.environ))
