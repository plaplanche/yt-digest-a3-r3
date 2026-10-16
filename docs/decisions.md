# Decisions

- 2026-10-16: `node/` uses hatchling as build backend and `requires-python` is pinned to 3.12 (`>=3.12,<3.13`); the spec only says "Python 3.12".
- 2026-10-16: `worker/` is an ES module package with a flat ESLint config (typescript-eslint recommended) and `tsc` with `types: []`, checking `src/` and `test/`.
- 2026-10-16: the `lint` check runs mypy on all of `node/` (source and tests) and shellcheck on every `*.sh` under `scripts/`.
- 2026-10-16: the `contracts` check passes with a message while `scripts/contracts.sh` does not exist.
- 2026-10-16: contracts are generated with `datamodel-code-generator` (Python) and `json-schema-to-typescript` (TypeScript), both pinned dev dependencies; `contracts.sh` runs `uv sync --locked` and `npm ci` (only when `worker/node_modules` is missing) itself.
- 2026-10-16: schemas encode types and ranges only; "null unless `ok`" style rules of 4.1 are the pipeline's job, and `attrs` of a log event is a free object whose per-event keys (4.2) are not validated.
- 2026-10-16: the log catalogue lives in `$defs/LogEventName` of the log schema; the TypeScript runtime check uses a generated `LOG_EVENTS` array appended to `log-event.ts`; the Service column of the catalogue is not enforced, each logger stamps its own `service`.
- 2026-10-16: `emit` and `log` take `request_id`, `video_id` and `attrs` as fields; `ts` is set by the logger and `attrs` defaults to `{}`.
- 2026-10-16: `vtt.py` holds `parse_vtt` and `Cue`, `cleaning.py` holds `clean_cues(cues, segments)` returning the paragraphs as a list of strings; segments are `(start, end)` pairs in seconds.
- 2026-10-16: a cue is "kept" (5.4 step 5) when at least one of its lines survives steps 3 and 4; the gap is compared after rounding to milliseconds so that 2.0 s is not lost to float error.
- 2026-10-16: any `<...>` is treated as an inline tag in step 3, and bracketed annotations do not span lines.
- 2026-10-16: `sponsorblock.py` uses the standard library `urllib` (no new dependency); `fetch_segments(base_url, video_id, request_id)` returns `SponsorBlockResult(segments, state)` and a 200 with an unparsable body counts as `error` (logged with status 200); the midpoint rule is `cleaning.is_sponsored`, and a non-positive duration gives a ratio of 0.
