---
title: PXA→EM entailment is causal — not enforced on emit path
type: learning
timestamp: '2026-08-19T00:00:00+00:00'
source: ISSUE-2236-pxa
signal: design-question
---

Issue #2236 asked for a "pre-emit guard" on cross-machine entailments.
The initial implementation included both RM↔VFD and PXA→EM checks on the
emit path. The PXA→EM check was removed after it broke the FV demo: in the
FV scenario, an actor intentionally asserts P (public disclosure) WHILE an
embargo is active — this is the causal act that terminates the embargo,
not a logical contradiction from the emitter's perspective.

Decision: only RM↔VFD is enforced at emit time (both are per-actor attributes;
a contradictory combination is an error at the source). PXA→EM constraints
belong on the receive path and are provided in `violation_pxa_em_entailment()`
for future use but not called in `ValidateTriggerTransitionsNode`.

This distinction (per-actor contradiction vs. cross-level causal trigger)
should be documented in `rm_em_cs.md` and/or the spec entries for
CSB-18-002..004 when they are written.

**Promoted**: 2026-08-24 — captured in specs/cs-behavior.yaml (CSB-18 rationale).
Docs PR: [PR URL TBD].
