#!/usr/bin/env bash
# Python (ruff, mypy --strict), TypeScript (tsc, ESLint) and shell (shellcheck) linters.
set -euo pipefail
cd "$(dirname "$0")/../.."

(
  cd node
  uv sync --locked
  uv run ruff check .
  uv run ruff format --check .
  uv run mypy --strict .
)
(
  cd worker
  npm ci
  npx tsc --noEmit
  npx eslint .
)
find scripts -name '*.sh' -print0 | xargs -0 uvx --from shellcheck-py shellcheck
