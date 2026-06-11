## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Append new items below any existing ones, marking them with the date and a
header.

### 2026-06-11 OUTBOX-873-TEST-COVERAGE — make acceptance criteria explicit in one file

Issue #873 found that most delivery-path coverage already existed but was split
across sections/files. Adding explicit tests in
`test/adapters/driving/fastapi/test_outbox.py` for direct `to` extraction and
malformed bare-string `object_` integrity checks keeps OX-08/OX-09 validation
discoverable in the canonical outbox test module and reduces ambiguity during
future outbox refactors.

### 2026-06-11 OUTBOX-874-HELPER-EXTRACTION — split protocol invariants from flow wiring

The outbox handler became easier to reason about after extracting nested
protocol checks into explicit helper functions (`_coerce_reference_value`,
`_prepare_activity_object_for_delivery`, `_recover_typed_inline_object_from_dict`,
etc.). Keeping the main delivery function focused on sequence-level orchestration
reduces churn risk when adding future outbox requirements while preserving
existing OX/MV invariants.

### 2026-06-11 SYNC — Isolated two-app replication harness for CaseLogEntry

For SYNC happy-path replication integration coverage (#901), the most stable
test seam is two isolated FastAPI apps created with `create_isolated_actor_app`
plus a shared `_TestASGIRouter` wired as each app's emitter fallback and as the
module-level default emitter. This setup exercises outbox -> ASGI delivery ->
inbox processing with distinct actor-scoped DataLayers and avoids real HTTP
retry delays.
