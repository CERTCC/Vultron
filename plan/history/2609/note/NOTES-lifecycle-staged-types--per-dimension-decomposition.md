---
source: NOTES-lifecycle-staged-types--per-dimension-decomposition
timestamp: '2026-09-17T17:22:58.229218+00:00'
title: 'Future Direction: Per-Dimension Status Decomposition'
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,b) self-marked Resolved; delivered
**Superseded by:** docs/adr/0036-status-dimension-objects.md; specs/status-dimension-objects.yaml; notes/status-dimension-objects.md

---

## Future Direction: Per-Dimension Status Decomposition

A natural next layer — **not** part of ADR-0033 — is decomposing
`CaseStatus`/`ParticipantStatus` into per-machine dimension objects (each state
machine its own small object with its own `transition()`/guard method), e.g.
`ParticipantStatus` → `{report: RmState, vf: VfState, d: DState, consent: PecState}`.

Where it helps: it gives the scattered EM/RM transition logic (see
`notes/embargo-lifecycle.md`, #538) one home, models the genuinely independent
dimensions faithfully, and composes with staged types (the `is_rm_validated()`
predicates become methods on the RM dimension). Staged types make illegal
*shapes* unrepresentable; dimension objects make illegal *transitions*
unrepresentable.

Where it gets messier: it is a wire- and persistence-visible schema change
(rehydration, `CORE_VOCABULARY`, AS2 projection, and the append-only
history model all interact), so it deserves its **own ADR** and must not be
folded into the staged-types work. Tracked as a separate Idea issue.

**Resolved**: ADR-0036 and `specs/status-dimension-objects.yaml` capture the
design and normative requirements. See `notes/status-dimension-objects.md`
for implementation guidance.
