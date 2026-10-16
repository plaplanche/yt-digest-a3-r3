import json
import socket
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest

from yt_digest_node.cleaning import is_sponsored
from yt_digest_node.sponsorblock import fetch_segments, sponsor_ratio
from yt_digest_node.vtt import Cue

VIDEO_ID = "abcdefghijk"
requests: list[str] = []
reply: dict[str, Any] = {}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        requests.append(self.path)
        body = reply["body"].encode()
        self.send_response(reply["status"])
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        pass


@pytest.fixture
def server() -> Iterator[str]:
    requests.clear()
    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    httpd.server_close()


def log_lines(capsys: pytest.CaptureFixture[str]) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = [
        json.loads(line) for line in capsys.readouterr().err.splitlines()
    ]
    return lines


def test_200_returns_segments_and_logs(server: str, capsys: pytest.CaptureFixture[str]) -> None:
    reply.update(status=200, body=json.dumps([{"segment": [1, 2.5]}, {"segment": [10.0, 12]}]))
    result = fetch_segments(server, VIDEO_ID, request_id="r1")
    assert result.state == "ok"
    assert result.segments == [(1.0, 2.5), (10.0, 12.0)]
    (line,) = log_lines(capsys)
    assert line["event"] == "sponsorblock.call"
    assert line["video_id"] == VIDEO_ID
    assert line["request_id"] == "r1"
    assert line["attrs"]["status"] == 200
    assert line["attrs"]["segments"] == 2
    assert line["attrs"]["duration_ms"] >= 0


def test_request_url(server: str) -> None:
    reply.update(status=200, body="[]")
    fetch_segments(server, VIDEO_ID)
    url = urlparse(requests[0])
    assert url.path == "/api/skipSegments"
    query = parse_qs(url.query)
    assert query["videoID"] == [VIDEO_ID]
    assert json.loads(query["categories"][0]) == ["sponsor", "selfpromo", "interaction"]
    assert "%5B" in url.query


def test_404_means_none(server: str, capsys: pytest.CaptureFixture[str]) -> None:
    reply.update(status=404, body="Not Found")
    result = fetch_segments(server, VIDEO_ID)
    assert (result.state, result.segments) == ("none", [])
    (line,) = log_lines(capsys)
    assert line["attrs"]["status"] == 404
    assert line["attrs"]["segments"] == 0


def test_500_is_an_error(server: str, capsys: pytest.CaptureFixture[str]) -> None:
    reply.update(status=500, body="boom")
    result = fetch_segments(server, VIDEO_ID)
    assert (result.state, result.segments) == ("error", [])
    (line,) = log_lines(capsys)
    assert line["attrs"]["status"] == 500
    assert line["attrs"]["segments"] == 0


def test_200_with_bad_body_is_an_error(server: str) -> None:
    reply.update(status=200, body="not json")
    assert fetch_segments(server, VIDEO_ID).state == "error"
    reply.update(status=200, body='[{"nope": 1}]')
    assert fetch_segments(server, VIDEO_ID).state == "error"


def test_connection_refused(capsys: pytest.CaptureFixture[str]) -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    result = fetch_segments(f"http://127.0.0.1:{port}", VIDEO_ID)
    assert (result.state, result.segments) == ("error", [])
    (line,) = log_lines(capsys)
    assert line["attrs"]["status"] == 0
    assert line["attrs"]["segments"] == 0


def cue_at(start: float, end: float) -> Cue:
    return Cue(start, end, ["x"])


def test_midpoint_start_inclusive_end_exclusive() -> None:
    segments = [(10.0, 20.0)]
    assert is_sponsored(cue_at(9.0, 11.0), segments)  # midpoint 10.0 == start
    assert not is_sponsored(cue_at(8.0, 11.9), segments)  # midpoint just before start
    assert not is_sponsored(cue_at(19.0, 21.0), segments)  # midpoint 20.0 == end
    assert is_sponsored(cue_at(18.0, 21.8), segments)  # midpoint just before end
    assert not is_sponsored(cue_at(0.0, 5.0), [])


def test_ratio_without_segments() -> None:
    assert sponsor_ratio([], 100.0) == 0.0


def test_ratio_union_of_overlapping_segments() -> None:
    # [10,30] u [20,40] u [60,70] = 30 + 10 = 40 s of 100
    assert sponsor_ratio([(20, 40), (10, 30), (60, 70)], 100.0) == 0.4


def test_ratio_clips_to_duration() -> None:
    assert sponsor_ratio([(90, 500)], 100.0) == 0.1
    assert sponsor_ratio([(200, 300)], 100.0) == 0.0
    assert sponsor_ratio([(-5, 10)], 100.0) == 0.1


def test_ratio_rounds_to_three_decimals() -> None:
    assert sponsor_ratio([(0, 1)], 3.0) == 0.333
