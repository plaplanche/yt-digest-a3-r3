import io
import json
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stderr
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from yt_digest_node.contracts.log_event import LogEvent, LogEventName
from yt_digest_node.contracts.transcript_result import TranscriptResult
from yt_digest_node.log import emit

ROOT = Path(__file__).resolve().parents[2]
GENERATED = ROOT / "node/src/yt_digest_node/contracts/log_event.py"
SCHEMA = ROOT / "contracts/transcript-result.schema.json"


def valid_result() -> dict[str, Any]:
    return {
        "video_id": "dQw4w9WgXcQ",
        "status": "ok",
        "lang": "en",
        "source": "manual",
        "word_count": 3,
        "truncated": False,
        "sponsor_ratio": 0.25,
        "pages": ["one two three"],
    }


def test_valid_transcript_result_is_accepted() -> None:
    assert TranscriptResult.model_validate(valid_result()).word_count == 3


@pytest.mark.parametrize(
    "change",
    [
        {"extra": 1},
        {"video_id": "short"},
        {"video_id": "bad id with 11"},
        {"status": "done"},
        {"source": "other"},
        {"word_count": -1},
        {"sponsor_ratio": 1.5},
    ],
)
def test_invalid_transcript_result_is_rejected(change: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        TranscriptResult.model_validate({**valid_result(), **change})


def test_log_event_catalogue_is_a_str_enum() -> None:
    assert {e.value for e in LogEventName} == {
        "service.started",
        "fetch.transcript",
        "sponsorblock.call",
    }


def test_valid_log_line_is_accepted() -> None:
    line = {
        "ts": "2026-10-16T10:00:00.000Z",
        "level": "info",
        "service": "node",
        "event": "service.started",
        "attrs": {"version": "0.1.0"},
    }
    assert LogEvent.model_validate(line).event is LogEventName.service_started


def test_log_line_with_unknown_event_is_rejected() -> None:
    line = {
        "ts": "2026-10-16T10:00:00.000Z",
        "level": "info",
        "service": "node",
        "event": "nope",
        "attrs": {},
    }
    with pytest.raises(ValidationError):
        LogEvent.model_validate(line)


def run_emit(*args: Any, **fields: Any) -> dict[str, Any]:
    buf = io.StringIO()
    with redirect_stderr(buf):
        emit(*args, **fields)
    out = buf.getvalue()
    assert out.endswith("\n") and out.count("\n") == 1
    parsed: dict[str, Any] = json.loads(out)
    return parsed


def test_emit_writes_one_json_line() -> None:
    line = run_emit("sponsorblock.call", video_id="dQw4w9WgXcQ", attrs={"status": 200})
    assert line["event"] == "sponsorblock.call"
    assert line["service"] == "node"
    assert line["level"] == "info"
    assert line["attrs"] == {"status": 200}
    assert LogEvent.model_validate(line).video_id == "dQw4w9WgXcQ"


def test_emit_rejects_event_outside_catalogue() -> None:
    with pytest.raises(ValueError):
        emit("not.in.catalogue")


def test_emit_rejects_unknown_field() -> None:
    with pytest.raises(ValueError):
        emit("service.started", bogus=1)


@contextmanager
def restored(path: Path) -> Iterator[None]:
    original = path.read_bytes()
    try:
        yield
    finally:
        path.write_bytes(original)


def check_contracts() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(ROOT / "scripts/contracts.sh"), "--check"],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


def test_check_passes_when_generated_files_are_current() -> None:
    assert check_contracts().returncode == 0


def test_check_fails_naming_a_hand_edited_generated_file() -> None:
    with restored(GENERATED):
        GENERATED.write_text(GENERATED.read_text() + "# hand edit\n")
        result = check_contracts()
    assert result.returncode == 1
    assert "node/src/yt_digest_node/contracts/log_event.py" in result.stderr


def test_check_fails_naming_files_when_a_schema_changes_without_regeneration() -> None:
    with restored(SCHEMA):
        schema = json.loads(SCHEMA.read_text())
        schema["properties"]["extra_count"] = {"type": "integer"}
        SCHEMA.write_text(json.dumps(schema, indent=2) + "\n")
        result = check_contracts()
    assert result.returncode == 1
    assert "node/src/yt_digest_node/contracts/transcript_result.py" in result.stderr
    assert "worker/src/contracts/transcript-result.ts" in result.stderr


def test_check_fails_on_a_stray_file_in_a_generated_directory() -> None:
    stray = GENERATED.parent / "stray.py"
    try:
        stray.write_text("")
        result = check_contracts()
    finally:
        stray.unlink(missing_ok=True)
    assert result.returncode == 1
    assert "stray.py" in result.stderr


def test_regeneration_fixes_a_stale_file() -> None:
    original = GENERATED.read_bytes()
    try:
        GENERATED.write_text("# garbage\n")
        subprocess.run([str(ROOT / "scripts/contracts.sh")], check=True, cwd=ROOT)
        assert GENERATED.read_bytes() == original
    finally:
        GENERATED.write_bytes(original)
