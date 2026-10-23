---
title: "spec-gap: read_case() added to CasePersistence port — no spec entry"
type: learning
timestamp: 2026-08-31T18:00:00Z
source: ISSUE-2490
signal: spec-gap
---

Issue #2490 added `read_case(case_id: str, raise_on_missing: bool = False) -> VulnerabilityCase | None`
to `CasePersistence` (and narrowed `find_case_by_report_id`/`find_case_by_short_id` return
types to `VulnerabilityCase | None`).

These are protocol-visible port method changes with no corresponding spec entry in
`specs/datalayer.yaml` or `specs/ports.yaml`. The existing DL-03-001 / DL-03-002
spec entries cover `read()` (returns `PersistableModel | None`) but not the new typed
variant.

A spec entry should be added to document `read_case()` as the canonical typed accessor
for `VulnerabilityCase` retrieval from `CasePersistence`.

---

**Archived**: 2026-09-03 — already captured. `read_case` is documented as the canonical typed `VulnerabilityCase` accessor in `specs/datalayer.yaml` DL-04-002. No new promotion needed.
