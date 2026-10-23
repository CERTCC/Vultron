---
title: 2 pre-existing bugs surfaced by code review on PR for #2780
type: learning
timestamp: "2026-08-27T00:00:00Z"
source: ISSUE-2780
signal: concern
---

Code review of the docs/skill-only PR for #2780 surfaced 2 bugs in files
outside the PR diff. Neither was introduced by this PR. Tracking for filing.

1. **`vultron/core/behaviors/sync/nodes/invite_accept_effect.py:105`** —
   `except (ValueError, KeyError)` does not catch `TypeError`. If `raw_roles`
   (derived from wire JSON) is a non-iterable (e.g., an integer in a malformed
   message), `validate_roles(raw_roles)` raises `TypeError`, which propagates
   uncaught out of `update()`, aborting the entire `AnnounceLogEntryReceivedBT`
   sequence. The log entry is permanently skipped.

2. **`vultron/core/behaviors/case/accept_invite_tree.py:387`** —
   `_read_invite_roles` returns `[]` silently when `object_` is `None` or the
   Invite's `roles` field is absent. Per the `datalayer-fallback-is-a-smell.md`
   learning, a missing roles field is a protocol violation and SHOULD be logged
   as such. No `WARNING` is emitted, so operators cannot distinguish
   "roles gracefully absent" from "roles extraction quietly failed."

Already tracked (not re-filed):

- `sync.py:234` auth_entries empty guard → `20260827-pre-existing-bugs-from-code-review-2757.md`
- `test/ci/invariants/common.py:941` partial ordering gap → Bug #2764
- `vultron/core/behaviors/case/nodes/participant/common.py:357` misleading warning → Bug #2763
- `vultron/core/behaviors/status/nodes/cs_dimension_filter.py:211` in-place mutation → Bug #2706
- `vultron/core/use_cases/received/case_proposal.py:255` new VultronValidationError path → tracked
- `vultron/core/use_cases/triggers/actor.py:224` backend.update() without setup() → tracked

## Audit disposition (2026-09-02)

Discharged: #2706, #2763, #2764.
