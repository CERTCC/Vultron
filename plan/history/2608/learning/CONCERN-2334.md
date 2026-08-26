---
source: CONCERN-2334
timestamp: '2026-08-26T18:29:57.233400+00:00'
title: CaseLedger causal ordering — CaseActor observation order is canonical
type: learning
---

## Outcome

Concern #2334 identified that DEMOMA-22-005 cited ADR-0041 for a causal-ordering
property that ADR-0041 does not establish. The solution was to write a normative
decision record (ADR-0076) and two new spec groups.

## Decision

**CaseActor observation order = canonical causal order.** The `log_index` sequence
assigned by the CaseActor's single authoritative write path is the causal order.
Three options were evaluated:

- **A (chosen): CaseActor observation order** — postal cancellation stamp model;
  single-writer regime already resolves ordering without distributed consensus.
- B (rejected): Vector clock causal tracking — too complex for a federated protocol.
- C (rejected): Pure wall-clock ordering — unreliable due to clock skew.

## Key field disambiguation

- `entry.published` (from `CoreObject`) — the CaseActor's own commit post-mark;
  the authoritative ordering field.
- `entry.received_at` — when the inbound activity arrived at the inbox.
- `payloadSnapshot.published` — the participant's claimed timestamp (may be out of
  order or clock-skewed; preserved in the snapshot but does not determine ledger order).

## Artefacts produced

- `docs/adr/0076-case-ledger-causal-ordering.md` — normative decision record
- `specs/case-ledger-processing.yaml` (v1.2.0 → v1.3.0): CLP-14 (9 entries) and
  CLP-15 (5 entries)
- `specs/multi-actor-demo.yaml`: DEMOMA-22-005 mis-citation fixed (ADR-0041 → ADR-0076)
- `notes/case-ledger-authority.md`: forward reference to ADR-0076 added
- Docs PR: <https://github.com/CERTCC/Vultron/pull/2678>
- Implementation issue: #2679 (runtime enforcement + conformance tests)

## Lessons

- ADR citations in spec `rationale:` fields are load-bearing — a wrong ADR number
  misleads future agents who validate the claim against the cited record.
- When field names in an issue body diverge from actual model fields, ignore the
  issue body and follow the object classes (`entry.published` not `entry.timestamp`).
- The single-writer regime (CaseActor is the only appender) makes deterministic
  causal ordering feasible without distributed consensus — lean on this invariant
  when reasoning about ledger correctness.
- New `protocol`+`MUST` spec entries require a `stories:` field or
  `lint_suppress: [missing_story_reference]`; missing it causes spec-lint ERROR
  (SR-11-003), not just a warning.
