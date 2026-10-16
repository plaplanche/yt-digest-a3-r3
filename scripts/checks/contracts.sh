#!/usr/bin/env bash
# Runs ./scripts/contracts.sh --check once it exists; passes with nothing to check until then.
set -euo pipefail
cd "$(dirname "$0")/../.."

if [[ -x scripts/contracts.sh ]]; then
  ./scripts/contracts.sh --check
else
  echo "scripts/contracts.sh does not exist yet: nothing to check"
fi
