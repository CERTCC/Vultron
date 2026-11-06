---
source: CONCERN-5730
timestamp: '2026-11-06T19:05:59.780217+00:00'
title: Processing-fault rules disagree on ledgering and can answer a fault with a
  fault
type: learning
---

Theme: theme:requirements-traceability — the processing-fault requirements agree with each other on whether a fault is ledgered and on when a fault may be answered.

## Summary

Two gaps in the processing-fault requirements surfaced while restating RE/EE/CE as `Create(ProcessingFault)` in #5299:

1. ASK-07-008 says a processing fault that can be attributed to a case MUST be recorded as a canonical `CaseLedgerEntry`. CLP-02-013 says a `Create(ProcessingFault)` NACK is not a case event, because it changes nothing in the case. They cannot both hold.
2. RMB-07-002 (restated from "answer RE with RE+GI") tells a participant in RM Start to answer a fault about an RM activity with another fault. If both sides are in Start, each fault prompts another. ASK-07-015 stops a repeat for the *same* failed activity only, and each answering fault is a new activity.

## Surface Symptom vs. Underlying Problem

On the surface, these are two wording slips. Underneath, nothing in the protocol says whether a fault is a case event, or whether a fault is itself something that can be answered with a fault. Both rules were carried over from the 2022 RE/EE/CE model, where errors were peer messages, and were never checked against the ledger model. The partition of failures into fault, `Reject` and `Add(Note)` (MSM-05-001) is correct and should stay.

## Category

Specification consistency.

## Severity

Low today: CE/EE/RE have no dedicated receive paths, so no code path loops. It becomes real when fault handling is built.

## Evidence

- `specs/protocol-asks.yaml` ASK-07-008; `specs/case-ledger-processing.yaml` CLP-02-013.
- `specs/rm-behavior.yaml` RMB-07-002 after #5299.
- #5299 removed the "its acknowledgment is the CASE_MANAGER's ledger entry" clause from VP-03-011 and VP-11-005, because of item 1.

## Impact if Ignored

An implementer picks one of ASK-07-008 or CLP-02-013 at random, and replicas disagree on whether faults appear in the ledger. Two actors that do not know a case can exchange faults without end.

## Suggested Action

Decide whether a case-attributable fault is ledgered, then amend whichever of ASK-07-008 and CLP-02-013 loses. Add a rule that a fault is never answered with a fault (or bound RMB-07-002 some other way).

**Resolved**: 2026-11-06 — implementation tracked in #6057.

Docs PR: https://github.com/CERTCC/Vultron/pull/6056.

Notes: `notes/protocol-asks.md`.

Decision: a processing fault is never ledgered (ASK-07-008 now MUST NOT; CLP-02-013 unchanged; SYNC-16-002 refines it), and a received fault is never answered with a fault (new ASK-07-019; RMB-07-002 and VP-03-010 bounded; ADR-0080 amended). Answers #4800.
