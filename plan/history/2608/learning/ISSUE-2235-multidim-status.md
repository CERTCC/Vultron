---
title: "RSH-01 specified who may update status, never what happens to the other dimensions when one is refused"
type: learning
timestamp: "2026-08-12T00:00:00Z"
source: ISSUE-2235-multidim-status
signal: spec-gap
---

`specs/received-status-handling.yaml` RSH-01-001..004 fully specified the
*authorization* half of StatusAdoptionGate — who may assert a `ParticipantStatus`, and that
the assertion must be adjudicated before the canonical write. It said nothing
about the fact that a `ParticipantStatus` is a snapshot of **five independent
state machines** (`rm`, `vfd`, `em`, `pxa`, `consent`), and therefore nothing
about what happens to the other four when one of them is unacceptable.

With no requirement to point at, the implementation defaulted to the shape the
BT gives you for free: a condition node returning FAILURE, which discards the
whole snapshot and aborts the enclosing Sequence. That silently dropped accepted
`vfd`/`pxa` values *and* skipped the StatusAdoptionGate → EmbargoTeardownAuthorizationGate emit, killing embargo
teardown. Nothing in the spec was violated, because nothing in the spec covered
it.

Filled by RSH-05-001..008 and ADR-0061. The generalizable lesson: whenever a
spec group governs a **composite** object, it needs an explicit statement of
whether the object is adjudicated as a unit or per component. "Validate X" is
ambiguous for any X that is a tuple of independent values, and the BT node
vocabulary biases the ambiguity toward all-or-nothing.

Other composites in the codebase worth auditing for the same silent
all-or-nothing default: `CaseStatus` (`em` + `pxa`) at EmbargoTeardownAuthorizationGate — already tracked
as ISSUE-2256 — and `VulnerabilityCase` field updates on
`Announce(VulnerabilityCase)`.

**Promoted**: 2026-08-17 — captured in specs/ RSH-05 (already written in prior session).
Docs PR: <https://github.com/CERTCC/Vultron/pull/2330>.
