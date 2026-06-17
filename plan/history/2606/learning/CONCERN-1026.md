---
source: CONCERN-1026
timestamp: '2026-06-17T19:40:49.456633+00:00'
title: CaseActor inbox routing as sole canonical ledger path
type: learning
---

## Summary

Most vendor-side trigger use cases and received use cases do not emit an
outbound activity addressed to the CaseActor, so the CaseActor's canonical
ledger never receives those events. The CASE_MANAGER gate added in #1021
(PR #1024) correctly enforces single-writer authority — but this exposed that
the delivery mechanism was never wired for most event types.

## Root Cause

The two-actor demo uses ASGI self-delivery: when the vendor creates a
per-case `VultronCaseActor` sub-actor, activities addressed to that CaseActor
ID are delivered via ASGI to the same vendor container's inbox, where they are
dispatched with `actor_id = case_actor_id`. This mechanism works correctly —
but only when vendor code explicitly emits an outbound activity addressed to
`case_manager_id`.

Before PR #1021, vendor code called `CommitCaseLedgerEntryNode` without a
gate. It broadcast `Announce(CaseLedgerEntry)` to all participants including
the CaseActor sub-actor. The CaseActor's local replica stored those received
entries and the devlog appeared complete. The test was passing for the wrong
reason. PR #1021's gate correctly blocked vendor commits — which correctly
revealed that most events never actually reach the CaseActor's inbox at all.

A subtler violation was found in `note.py` and `embargo.py`: both resolved
`case_actor_id` from the DataLayer and passed it as `actor_id` to
`BTBridge.execute_with_setup` even when the active DataLayer belonged to the
vendor actor. This is identity spoofing — executing the guarded-commit BT
with a foreign identity from the wrong DataLayer context.

## Resolution

ADR-0021 establishes that the CaseActor's inbox is the **only** correct path
to a canonical ledger entry. The end-to-end routing contract is: trigger tree
emits to `case_manager_id` → ASGI delivers to CaseActor inbox → received use
case checks `receiving_actor_id == case_actor_id` pre-flight guard → guarded
commit BT executes as the CaseActor. Received-side use cases that run in a
non-CaseActor inbox skip the commit entirely.

`announce_case_ledger_entry` is removed from `EXPECTED_EVENT_TYPES` because
it is the replication envelope, not a canonical entry type — it cannot be its
own payload.

**Resolved**: 2026-06-17 — implementation tracked in #1029 (pilot: validate_report
end-to-end + test parameterization) and #1030 (remaining event types + flip all
xfails). #1030 blocked by #1029.
Docs PR: [PR #1028](https://github.com/CERTCC/Vultron/pull/1028).
Spec: `specs/case-ledger-processing.yaml` CLP-10-001 through CLP-10-004.
Notes: `notes/case-communication-model.md` § "Antipattern: Received-Side Guarded Commit with Foreign CaseActor ID".
