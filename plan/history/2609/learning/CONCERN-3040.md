---
source: CONCERN-3040
timestamp: '2026-09-14T17:55:41.458046+00:00'
title: Receive path stays liberal — CONCERN-3040 settled
type: learning
---

## Outcome

The receive path for `Add(ParticipantStatus)` stays liberal (per-dimension
partial accept). The open question in `notes/domain-validation.md` is closed.

## Decision rationale

Two arguments settled it:

1. **RM is self-declaratory (ADR-0084).** The CaseActor has no independent
   knowledge of a participant's RM state. If a sender asserts `rm=VALID` while
   the ledger records `ACCEPTED`, the ledger is merely stale — the participant
   is the authority on their own state. The CaseActor cannot correct a
   self-report.

2. **PXA dimensions are time-sensitive external observational facts.** A threat
   sentinel may correctly observe `exploit=public` while carrying a stale RM
   value. Refusing the whole message means the embargo continues past the point
   of public exploit code — a protocol safety failure.

Impossible dimension combinations (RM↔VF, RM↔D, VF↔D) are already refused
outright by RSH-05-020; partial-accept does not let them through.

## Open work

- **#3199 AC-1**: Add emit-side object-level validators that prevent
  constructing a `ParticipantStatus` with a backward RM step (Postel's: be
  strict in what you emit).
- **#3199 AC-2**: Fix sender-feedback diagnostics — fully-refused receive BT
  must return `rejected` in `InboxOutcome` rather than `202 processed`
  (extends #2255).

## References

- Docs PR: <https://github.com/CERTCC/Vultron/pull/3198>
- Impl task: #3199
- Related: #2255 (sender-feedback bug)
- ADR-0061, ADR-0084, ADR-0086, RSH-05-020
