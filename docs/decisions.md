# Decisions

- 2026-10-16: `node/` uses hatchling as build backend and `requires-python` is pinned to 3.12 (`>=3.12,<3.13`); the spec only says "Python 3.12".
- 2026-10-16: `worker/` is an ES module package with a flat ESLint config (typescript-eslint recommended) and `tsc` with `types: []`, checking `src/` and `test/`.
- 2026-10-16: the `lint` check runs mypy on all of `node/` (source and tests) and shellcheck on every `*.sh` under `scripts/`.
- 2026-10-16: the `contracts` check passes with a message while `scripts/contracts.sh` does not exist.
