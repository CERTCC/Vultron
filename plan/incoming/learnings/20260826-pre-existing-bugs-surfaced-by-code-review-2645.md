---
title: Pre-existing Python bugs surfaced by code review during #2645/#2646 session
type: learning
timestamp: 2026-08-26
source: ISSUE-2645
signal: concern
---

During the code review for PR #2660 (issues #2645 and #2646, skill-file-only
changes), the review agent scanned beyond the diff and surfaced pre-existing
bugs in core Python files. These are not caused by or related to the skill
edits in that PR. All require separate follow-up issues.

**CONFIRMED bugs:**

1. `vultron/core/use_cases/received/case_proposal.py:255,319` —
   `AcceptCaseProposalReceivedUseCase` and `RejectCaseProposalReceivedUseCase`
   fall back to `request.actor_id` (the CaseActor sender) instead of
   `dl.actor_id` (the receiving vendor). `CreateCaseProposalReceivedUseCase`
   in the same file was correctly fixed to use `resolve_receiving_actor_id`,
   making the inconsistency visible. When `receiving_actor_id` is absent,
   the BT runs in the wrong store partition; the `VultronReportCaseLink` write
   is silently lost or misrouted.

2. `vultron/adapters/driving/fastapi/inbox_pipeline.py:132` — bare
   `except Exception:` catches `VultronValidationError` raised by
   `resolve_receiving_actor_id` and re-queues the item, creating an
   infinite retry loop with no dead-letter path.

**PLAUSIBLE bugs (warrant investigation):**

1. `vultron/core/use_cases/received/embargo.py:266,288` — `invitee_id` is
   always set equal to `receiving_actor_id`; the comment at lines 301–306
   documents a CaseActor-forwarding path where these differ, but that path
   is unreachable as written. PXA-rejection ER is also attributed to the
   wrong actor in the same code path.

2. `vultron/core/use_cases/received/report.py:250,258,423` —
   `_store_submit_report_dependencies` writes before `resolve_receiving_actor_id`
   raises (partial write); `_is_primary_submit_report_recipient` may silently
   drop case creation on IRI vs. bare-ID format mismatch; `AckReportReceivedUseCase`
   has no routing gate and may advance the wrong actor's RM state machine.

3. `vultron/core/use_cases/_helpers.py:326` — `getattr(dl, 'actor_id', None)`
   suppresses only `AttributeError`; a property getter raising
   `NotImplementedError` propagates past `resolve_receiving_actor_id` callers
   that catch only `VultronValidationError`.

**Action required:** File separate Bug issues for items 1 and 2 (confirmed,
high severity). Items 3–5 should be investigated and filed if confirmed.
