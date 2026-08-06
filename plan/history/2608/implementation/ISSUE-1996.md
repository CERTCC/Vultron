---
source: ISSUE-1996
timestamp: '2026-08-06T14:51:42.136878+00:00'
title: Demo CI scenario coverage analysis and minimum PR validation set
type: implementation
---

## Issue #1996 — Demo CI: scenario coverage analysis and minimum PR validation set (DEMOCI-06)

Implemented all 7 acceptance criteria. PR: <https://github.com/CERTCC/Vultron/pull/2030>

### What was done

**AC-2 — Fix invariant constants**: Added `accept_invite_actor_to_case` to `_EXPECTED_EVENT_TYPES` in `test_fvv_invariants.py`, `test_fcv_invariants.py`, and `test_fvcv_extension_invariants.py`. All three scenarios call `accept-case-invite` triggers in their scenario scripts but the event type was missing from Invariant 5.

**AC-2 spec**: Updated DEMOMA-16-003, 16-004, 16-007 to require `accept_invite_actor_to_case`. Added DEMOMA-16-010 for `fccv-extension` (test was correct, spec entry was missing).

**AC-3/AC-6 — Coverage notes**: Created `notes/demo-ci-scenario-coverage.md` with 8-scenario coverage matrix, correction log, minimum-set coverage proof, and workflow notes.

**AC-4 — Minimum PR set**: `fv` + `fvcv-handoff` + `fcvcv` covers all 7 distinct protocol event types. The 5 remaining scenarios exercise no event type not already covered.

**AC-5 — Workflow split**: Added `push: branches: ["main"]` trigger (implements DEMOCI-05-001, previously unimplemented). Added `full_suite_only` boolean matrix field with job-level `if:` gates. PR runs 3-scenario minimum set; push/dispatch runs all 8.

**AC-7 — DEMOCI-06 spec**: Updated DEMOCI-06-001/002/003 with validated minimum set, corrected scenario count (7→8), and push trigger requirement.

### Key findings

- Ownership transfer is NOT a `CaseLedgerEntry` event_type — it is verified by `demo_check` assertions in the scenario scripts. It is covered by `fvcv-handoff` in the minimum PR set without needing a separate event-type entry.
- DEMOCI-05-001 (push-to-main trigger) was not implemented in the workflow prior to this PR. DEMOCI-06 depended on it and this PR implements both together.
- `fccv-extension` test file (`test_fccv_extension_invariants.py`) was already correct — only the spec entry was missing.
