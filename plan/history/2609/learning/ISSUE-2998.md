---
title: "Pre-existing bugs found during #2998 code review"
type: learning
source: ISSUE-2998
timestamp: "2026-09-02T00:00:00Z"
---

Code review during #2998 surfaced two pre-existing bugs unrelated to the PR:

- #3096: `vultron/wire/as2/vocab/examples/_base.py` — `case()` raises `TypeError` when `kwargs` contains `name`, `id_`, or `attributed_to` (positional field collision).
- #3097: `test/core/behaviors/bt_harness.py:189` — `assert_failure(allow_internal=True)` never asserts `result.internal_error is True`, so crash-path classification tests give false confidence.

Both filed under Epic #607, milestone 26, size:S.

---

**Archived**: 2026-09-03 — already tracked and now closed: #3096 (CLOSED) and #3097 (CLOSED). No new promotion needed.
