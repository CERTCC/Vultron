---
title: "Emit/receive asymmetry is a discoverable bug class: diff which invariants each path enforces"
type: learning
timestamp: "2026-09-01T00:00:00Z"
source: ISSUE-2906
signal: spec-gap
---

Bug #2906 turned out to be an instance of a general shape worth hunting for
deliberately: **the same protocol invariant enforced on the emit path and not on
the receive path.**

`vultron/core/states/cross_machine_invariants.py` exported three participant
entailment checks. The emit path
(`ValidateTriggerTransitionsNode._validate_entailments`) called all three.
The receive path (`_adjudicate_dimensions`) called one. Nothing flagged the
gap, because each path independently looked complete — the asymmetry is only
visible when you diff the two call sites against the module's exports.

Consequence: an actor refused to *emit* an impossible RM/VF pair but accepted,
hash-chained and replicated the same pair when a peer sent it. A validation
asymmetry in this direction is strictly worse than a missing check on both
sides, because the local actor's own behaviour looks correct.

**How to find more of these:** for each invariant module in
`vultron/core/states/`, grep every exported `violation_*` / `is_valid_*` /
`is_monotonic_*` predicate for its call sites and sort them by emit path vs.
receive path vs. replica-apply path. A predicate with callers on only one path
is either a deliberate scoping decision (which should be stated in the
predicate's docstring or a spec `note:`) or a gap. `violation_pxa_em_entailment`
has *zero* production callers today; `ApplyParticipantStatusFromLedgerNode`
enforces only the RM ratchet.

**Structural fix applied:** the three rules are now composed once, in
`cross_machine_violations()`, and both paths call that. A ratchet test asserts
the emit path does not call the individual predicates directly. Composing the
rule set — not just sharing the individual predicates — is what makes the
divergence impossible rather than merely fixed. Recorded as RSH-05-020.
