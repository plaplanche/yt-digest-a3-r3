import json
import os
import subprocess
import sys
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest

from yt_digest_node.contracts.transcript_result import TranscriptResult

VIDEO_ID = "abcdefghijk"
FIXTURES = Path(__file__).parent / "fixtures" / "vtt"
reply: dict[str, Any] = {"status": 404, "body": ""}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(reply["status"])
        self.end_headers()
        self.wfile.write(reply["body"].encode())

    def log_message(self, format: str, *args: Any) -> None:
        pass


@pytest.fixture
def sponsorblock() -> Iterator[str]:
    reply.update(status=404, body="")
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


def make_video(root: Path, video_id: str, meta: dict[str, object], **tracks: str) -> None:
    video = root / video_id
    video.mkdir()
    (video / "meta.json").write_text(json.dumps(meta))
    for name, fixture in tracks.items():
        (video / f"{name}.vtt").write_text((FIXTURES / fixture).read_text(encoding="utf-8"))


def run_proc(
    tmp_path: Path, sponsorblock: str, *args: str, **env: str
) -> subprocess.CompletedProcess[str]:
    full_env = {
        **os.environ,
        "FETCHER_FAKE_YTDLP": "1",
        "FAKE_YTDLP_DIR": str(tmp_path),
        "SPONSORBLOCK_URL": sponsorblock,
        **env,
    }
    return subprocess.run(
        [sys.executable, "-m", "yt_digest_node", "transcript", *args],
        env=full_env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def run_cli(
    tmp_path: Path, sponsorblock: str, *args: str, **env: str
) -> tuple[int, str, list[dict[str, Any]]]:
    proc = run_proc(tmp_path, sponsorblock, *args, **env)
    logs = [json.loads(line) for line in proc.stderr.splitlines() if line.startswith("{")]
    return proc.returncode, proc.stdout, logs


def test_ok_with_sponsor_cuts(tmp_path: Path, sponsorblock: str) -> None:
    make_video(tmp_path, VIDEO_ID, {"duration": 20}, **{"fr.manual": "manual.vtt"})
    full = run_cli(tmp_path, sponsorblock, VIDEO_ID)[1]
    reply.update(status=200, body=json.dumps([{"segment": [3.0, 5.0]}]))
    code, out, logs = run_cli(tmp_path, sponsorblock, VIDEO_ID, "--request-id", "r1")
    assert code == 0
    result = TranscriptResult.model_validate_json(out)
    assert (result.status, result.lang, result.source) == ("ok", "fr", "manual")
    assert result.sponsor_ratio == 0.1
    assert result.word_count == len(" ".join(result.pages).split()) > 0
    assert result.word_count < TranscriptResult.model_validate_json(full).word_count
    assert [log["event"] for log in logs] == [
        "service.started",
        "sponsorblock.call",
        "fetch.transcript",
    ]
    assert logs[-1]["request_id"] == "r1"
    assert logs[-1]["attrs"]["sponsorblock"] == "ok"
    assert logs[-1]["attrs"]["words"] == result.word_count


def test_logs_hold_no_transcript_text(tmp_path: Path, sponsorblock: str) -> None:
    make_video(tmp_path, VIDEO_ID, {"duration": 20}, **{"fr.manual": "manual.vtt"})
    proc = run_proc(tmp_path, sponsorblock, VIDEO_ID)
    assert proc.returncode == 0
    transcript_words = set(" ".join(json.loads(proc.stdout)["pages"]).split())
    assert transcript_words
    assert not {w for w in transcript_words if len(w) > 4 and w in proc.stderr}


def test_truncation_from_environment(tmp_path: Path, sponsorblock: str) -> None:
    make_video(tmp_path, VIDEO_ID, {"duration": 20}, **{"fr.manual": "manual.vtt"})
    _, out, _ = run_cli(tmp_path, sponsorblock, VIDEO_ID, MAX_WORDS="4", PAGE_WORDS="2")
    result = TranscriptResult.model_validate_json(out)
    assert result.truncated
    assert result.word_count == 4
    assert len(result.pages) >= 2


def test_langs_option_picks_track(tmp_path: Path, sponsorblock: str) -> None:
    make_video(
        tmp_path, VIDEO_ID, {"duration": 20}, **{"fr.manual": "manual.vtt", "en.auto": "auto.vtt"}
    )
    _, out, _ = run_cli(tmp_path, sponsorblock, VIDEO_ID, "--langs", "en")
    result = TranscriptResult.model_validate_json(out)
    assert (result.lang, result.source) == ("en", "auto")


def test_sponsorblock_failure_gives_null_ratio(tmp_path: Path, sponsorblock: str) -> None:
    make_video(tmp_path, VIDEO_ID, {"duration": 20}, **{"fr.manual": "manual.vtt"})
    reply.update(status=500, body="")
    _, out, logs = run_cli(tmp_path, sponsorblock, VIDEO_ID)
    result = TranscriptResult.model_validate_json(out)
    assert result.status == "ok"
    assert result.sponsor_ratio is None
    assert logs[-1]["attrs"]["sponsorblock"] == "error"


def test_no_transcript(tmp_path: Path, sponsorblock: str) -> None:
    make_video(tmp_path, VIDEO_ID, {"duration": 20}, **{"de.manual": "manual.vtt"})
    code, out, logs = run_cli(tmp_path, sponsorblock, VIDEO_ID)
    result = TranscriptResult.model_validate_json(out)
    assert code == 0
    assert (result.status, result.pages, result.sponsor_ratio) == ("no_transcript", [], None)
    assert logs[-1]["attrs"]["outcome"] == "no_transcript"


def test_unavailable(tmp_path: Path, sponsorblock: str) -> None:
    code, out, logs = run_cli(tmp_path, sponsorblock, VIDEO_ID)
    assert code == 0
    assert TranscriptResult.model_validate_json(out).status == "unavailable"
    assert logs[-1]["attrs"]["outcome"] == "unavailable"


def test_blocked(tmp_path: Path, sponsorblock: str) -> None:
    make_video(tmp_path, VIDEO_ID, {"duration": 20, "status": "blocked"})
    code, out, _ = run_cli(tmp_path, sponsorblock, VIDEO_ID)
    assert code == 0
    assert TranscriptResult.model_validate_json(out).status == "blocked"


def test_invalid_video_id_exits_2_without_result(tmp_path: Path, sponsorblock: str) -> None:
    code, out, _ = run_cli(tmp_path, sponsorblock, "short")
    assert code == 2
    assert out == ""
