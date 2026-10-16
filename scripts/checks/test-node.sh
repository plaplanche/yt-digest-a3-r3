#!/usr/bin/env bash
# pytest on node/tests/.
set -euo pipefail
cd "$(dirname "$0")/../../node"

uv sync --locked
uv run pytest tests/
