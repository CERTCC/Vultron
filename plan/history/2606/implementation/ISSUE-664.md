---
source: ISSUE-664
timestamp: '2026-06-02T20:13:45.658911+00:00'
title: Add case log REST endpoints for demo tooling
type: implementation
---

## Issue #664 — Add case log REST endpoints: ordered list and single-entry lookup

Added two demo-only GET endpoints to the `demo_triggers` router:

- `GET /actors/{actor_id}/demo/cases/{case_id:path}/log` — returns all
  `VultronCaseLogEntry` objects for a case sorted ascending by `log_index`.
  Supports JSON (default) and NDJSON via `Accept: application/x-ndjson`
  header or `?format=ndjson` query param.
- `GET /actors/{actor_id}/demo/cases/{case_id:path}/log/{index}` — returns
  the single entry at the given zero-based index. Returns HTTP 404 if absent;
  validates `index >= 0` (HTTP 422 otherwise).

Both routes use `{case_id:path}` to support HTTP URL case IDs containing
slashes. Serialisation uses the wire-layer `CaseLogEntry` class (auto-registered
in `VOCABULARY`) with `by_alias=True` so all fields use camelCase (`logIndex`,
`caseId`, `eventType`, `logObjectId`, etc.).

Key lesson: the DataLayer reconstructs objects via the wire vocabulary, so
`list_objects("CaseLogEntry")` returns wire `CaseLogEntry` instances, not core
`VultronCaseLogEntry` instances. Endpoints must isinstance-check against both
classes (or the wire class alone).

Also marked `_get_log_entries_for_case()` in `sync.py` as deprecated.

21 tests added covering: empty list, sorted order, case isolation, NDJSON via
header and query param, HTTP URL case IDs, 404, 422, and camelCase alias
verification.

Implements: TRIG-09-001, SYNC-01-002, SYNC-02-003.

PR: [#678](https://github.com/CERTCC/Vultron/pull/678).
