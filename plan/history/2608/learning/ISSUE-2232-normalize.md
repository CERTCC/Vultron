---
title: Design choice — normalise wire→core at the persistence boundary, not at wire ingress
type: learning
timestamp: 2026-08-12T00:00:00Z
source: ISSUE-2232-normalize
signal: design-question
---

Issue #2232 prescribed: *"Normalize at the boundary (wire -> core on ingress) so no
wire-shaped row is ever persisted."*  The fix normalises at the **persistence**
boundary (`Record.from_obj`) rather than at **wire ingress**, and scopes it to
2 of the 15 shadowing types.  Both departures were deliberate.

**Why persistence rather than ingress.** Wire ingress is not a single chokepoint
— wire objects are constructed in-process by BT nodes, trigger factories, and
test fixtures, not only parsed from inbound AS2.  Measured during analysis:
~63 files import `as_CaseParticipant`/`as_ParticipantStatus` *and* call
`.save(`/`.create(`.  `Record.from_obj` is the one place every persisted object
passes through, so a guard there is total; a guard at ingress would have been
partial while looking complete.  The issue's "Done when" clause — *"a
wire-shaped ParticipantStatus cannot be persisted"* — is a statement about
persistence, and that is where it is now enforced.

**Why normalise rather than reject.** The first attempt rejected all 15
shadowing types outright.  That is the stronger invariant, but it turned ~63
test files into `size:L` churn unrelated to the defect.  Normalising via the
existing `to_core()` projections satisfies both "Done when" clauses (no
wire-shaped row is stored; a shape mismatch raises) without that churn.

**Why 2 types and not 15.** `CaseParticipant` and `ParticipantStatus` differ
*structurally* between the two shapes — core nests `rm: RmDimension`, wire
carries a flat `rm_state` — so a wire row silently yields `None`.  The other 13
currently differ only by key spelling, which is a coincidence rather than an
invariant.  `_NORMALIZE_WIRE_TO_CORE` is documented as shrink-only (may grow,
never shrink) and the remaining 13 are tracked in #2268.

**Cost paid for the narrow scope:** the write path now has a *second*
exemption set to keep honest, alongside read-side `KNOWN_WIRE_ESCAPES`.  Two
ratchets for one underlying problem is a smell; #2268 records the structural
alternative (disjoint `type_` namespaces between the two vocabularies), which
would delete both.

**Promoted**: 2026-08-17 — captured in GitHub #2320 (Concern: wire-shape convergence — design rationale context).
Docs PR: <https://github.com/CERTCC/Vultron/pull/2330>.
