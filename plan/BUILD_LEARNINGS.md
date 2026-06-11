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
