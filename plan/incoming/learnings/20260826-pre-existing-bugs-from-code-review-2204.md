---
title: "5 pre-existing bugs surfaced by code review on PR #2726"
type: learning
timestamp: "2026-08-26T00:00:00Z"
source: ISSUE-2204
signal: concern
---

The code reviewer on PR #2726 identified 5 bugs in files outside the PR diff.
None were introduced by the PR. Each should be tracked as a Bug issue:

1. `vultron/demo/scenario/fcvcv_demo.py:287` — `invite_v1_id`/`invite_c2_id`
   escapes its `demo_gate`, causing secondary failures when the gate fires.

2. `vultron/core/behaviors/status/nodes/cs_dimension_filter.py:226` —
   `FilterCsPxaDimensionNode` logs a status URI where a case ID is expected
   (wrong format placeholder in the warning log line).

3. `vultron/core/behaviors/embargo/nodes/teardown.py:137` — double PEC reset:
   `ClearActiveEmbargoNode` calls `_cascade_pec_reset` internally via
   `terminate_active_embargo`, then `ResetParticipantConsentNode` repeats it.
   Docstring for `reset_case_participant_embargo_consent` falsely claims
   `_cascade_pec_reset` was removed.

4. `vultron/core/use_cases/received/case_proposal.py:488` — lost
   `request.actor_id` fallback in `AcceptCaseProposalReceivedUseCase`; now uses
   `dl.actor_id` unconditionally, breaking replay/CLI paths where
   `receiving_actor_id=None` and the sender differs from the store owner.

5. `vultron/core/use_cases/triggers/actor.py:757` — `_record_named_peer`
   creates a `CoreActor` stub unconditionally regardless of backend result; the
   backend is never told which `actor_id` to resolve, making the call-out seam
   non-functional for real directory-service backends.

ADVISORY comment posted at: <https://github.com/CERTCC/Vultron/pull/2726#issuecomment-5431265046>
