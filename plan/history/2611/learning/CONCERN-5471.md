---
source: CONCERN-5471
timestamp: '2026-11-03T18:50:45.274066+00:00'
title: A case's current status should follow append order, as a participant's does
type: learning
---

Theme: theme:requirements-traceability — decide whether one current-status rule can serve both case and participant statuses.

## Summary

The code picks "current" two ways. `CaseParticipant.participant_status` returns the last status appended. `VulnerabilityCase.current_status` returns the latest by `updated` then `published`, ties to the last appended (CM-29-001, `most_recent_status` in `vultron/core/models/_helpers.py`). On 2026-10-29 (#5374 item 2) the maintainer kept both and had SM-05-002 name both (#5469), with this follow-up to check whether the case status should also move to append order.

## Surface Symptom vs. Underlying Problem

Surface: two rules for one idea. Underlying: append order is only safe where each appended entry was accepted as a valid next step from the one before. The participant status meets that, because the transition guards judge an update against `history[-1]` (`RecordedBaseline.from_history`). Whether case statuses meet it is unknown. If they do not, append order could make an out-of-order entry current, and the timestamp rule is the better one there. The participant rule is correct and stays.

## Category

Spec and code consistency.

## Severity

Low. Both rules work today; this is about whether one rule is enough.

## Evidence

- ADR-0103: a received time is the sender's claim and is never set by the receiver, so timestamp order across senders is skew-prone (`most_recent_status` docstring, ISSUE-3257).
- `CaseParticipant.participant_status` docstring cites clock skew (bug #659) for using append order.

## Impact if Ignored

Two rules stay, and each new reader of a status history must know which one applies.

## Suggested Action

List every writer of `VulnerabilityCase.case_statuses` (CASE_MANAGER commits, replica copies, bootstrap seeding) and check whether each append is guarded as a valid next step and whether the entries come from more than one sender's clock. If every append is guarded, move `current_status` to append order and retire CM-29-001's timestamp rule (and the earliest-time fallback). If not, keep the timestamp rule and record why in CM-29-001's rationale.

Governing specs: CM-29-001, SM-05-002, ADR-0103

**Resolved**: 2026-11-03 — implementation tracked in #5749.
Docs PR: <https://github.com/CERTCC/Vultron/pull/5751>.

Finding: every append to `VulnerabilityCase.case_statuses` is the CASE_MANAGER's,
each a valid next step on its own clock (genesis seeding on both creation paths,
`EmitCaseStatusUpdateNode`), and replicas copy the list and append in ledger
order. So append order is safe, and it is the stronger key: the snapshot node
already measures change against the ledger's last status, plain `now_utc()`
stamps lose to a clock step back, and role delegation can move the CASE_MANAGER
role to another clock. Decision: `current_status` becomes the last appended;
the CASE_MANAGER stamps each status's `published` strictly after the previous
one's; a replica given an out-of-order time appends it anyway and warns.

The spec amendments were drafted but carried into #5749 rather than a docs-only
PR, because their `verification:` names tests that do not exist yet (MS-10-010)
and would put the specs at odds with the code on `main`.
