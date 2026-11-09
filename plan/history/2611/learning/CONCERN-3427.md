---
source: CONCERN-3427
timestamp: '2026-11-09T18:31:08.915291+00:00'
title: Cross-shape capability semantics
type: learning
---

Theme: theme:capability-architecture — settles cross-shape capability semantics for ledger, failure, and caching.

## Summary

Holds the genuine remainders from the four shape Ideas (#1144 Evaluator, #1145
Retriever, #1146 Composer, #2451 Actuator) that ADR-0097 did **not** answer. Those
Ideas close because the contract, the calling convention, and the declaration
format are now settled; these questions are cross-cutting semantics that the
capability layer still owes, and are recorded here so they are not lost.

Filed per the G07 planning protocol rule 5 ("lose nothing") and rule 4 ("a member
with a real remainder ... is re-scoped").

## The five open questions

### 1. Is a capability's output recorded in the canonical case ledger?

Asked by #1144 ("Should the Evaluator output be recorded in the canonical case
ledger?") and #2451 ("Should Actuator side effects be recorded?"). It applies to
every data-producing capability, not just Evaluators.

The tension to resolve: a capability's verdict is a **local operational decision**,
and `notes/call-out-configuration.md` classifies most call-outs that way — no
mechanism to impose canonical state on another party. But CLP-07 says the ledger is
not a process log, so a per-actor verdict arguably does not belong in it at all,
while `CLP-07-004` reserves per-actor observability content. A decision that
*causes* a protocol-visible transition already reaches the ledger through the
transition itself; the question is whether the *rationale* does, and whether
recording it would make an actor's private triage replicate to every participant.

Compare the parallel already decided for asks: the *fact* of an ask is protocol
history, the *diagnosis* is not (ASK-07-008, ADR-0080).

### 2. Actuator failure and partial-success semantics

Asked by #2451. An Actuator returns SUCCESS when a side effect is confirmed and
FAILURE otherwise, but nothing specifies:

- What the tree does on FAILURE — retry, log and continue, or halt. Note
  BT-14-001 already forbids masking delivery failure in peer broadcast paths, and
  OX-13 caps retries that compose to `4 x infinity`; an Actuator retry policy must
  not reintroduce either hazard.
- How partial success is reported (some recipients notified, others not). A single
  SUCCESS/FAILURE cannot express it, and ADR-0086 ("report every violation, reject
  the batch") is the nearest precedent for the shape of the answer.

### 3. Retriever caching and staleness

Asked by #1145 and flagged in `notes/coordination-agents.md`: "the same external
fact may be queried multiple times across a case lifetime; the Retriever should not
be called redundantly if the answer is already in the DataLayer." Unspecified:
whether caching is the capability's responsibility or the layer's, where a cached
fact lives, and what invalidates it. Interacts with the BT-18-015 latency budget —
caching is one of the few ways a slow external lookup can meet it.

### 4. What authentication and authorization model does an Actuator use?

Asked by #2451 ("What authentication/authorization model do Actuators use to call
external systems?" and "What external systems are Actuators expected to integrate
with?"). Added on PR #3420 review: these were the two questions #2451 carried that
neither ADR-0097 nor the original scope of this Concern accounted for.

An Actuator is the only one of the four shapes that **writes** to a foreign system,
so it is the only one that needs outbound credentials. Unspecified: where those
credentials live, whether they are per-actor or per-capability, what happens when
they are rejected (a credential failure is not the same signal as a refused side
effect, but a single FAILURE cannot distinguish them — which ties this to question
2), and whether the set of reachable target systems is constrained at all or is
purely a deployment matter. Note the constraint the latency bound imposes: an
integration that cannot confirm its side effect inside the BT-18-015 budget is a
protocol ask or a call-in monitor, not an Actuator.

### 5. Where does a Composer sit relative to the existing Note and advisory behaviours?

Asked by #1146 ("At which specific BT nodes / use cases should a Composer be
called?", "How does a Composer relate to existing Note/advisory workflows in
`vultron/core/behaviors/note/`?", "Can a Composer reuse prior advisory text?").
Added on PR #3420 review.

ADR-0097 settles *how* a Composer's artifact is delivered — the declared output port
— but not *where* one is consulted. `vultron/core/behaviors/note/` already composes
and attaches content without a call-out seam, so the boundary between "the protocol
writes this" and "a capability drafts this" is undrawn, and #1146's own note records
that no current fuzzer node is a Composer call-out point. Reusing prior advisory
text would additionally make the capability a **composite** with a Retriever phase
(the #3426 pattern), which is a shape question rather than a content one.

## Not in scope

These were asked in the same Ideas and **are** answered; do not reopen them:

- Calling convention, async suspension, timeouts — ADR-0097, BT-18-011, BT-18-015.
- Input/output schema and its declaration — BT-18-012 (typed ports).
- Advisory versus auto-execute trust mode — orthogonal to shape and a deployment
  configuration question (`notes/coordination-agents.md` § Trust / Execution
  Authority).
- Human review before a Composer artifact is sent — per-deployment policy, not a
  protocol question (same note).
- SSVC as the Evaluator schema for prioritization — tracked as PROTO-05-001 via
  `evaluate_priority_factory`.
- Where a Composer's artifact is attached — the declared output port (BT-18-012).
  (*Which node consults a Composer* is question 5 above, and is in scope.)

## Reference

Source: #2835 (planning group G07); carries remainders from #1144, #1145, #1146, #2451.
Questions 4 and 5 were added during the #3420 review, which found them uncarried
against G07 protocol rule 5 ("lose nothing").
Docs PR: https://github.com/CERTCC/Vultron/pull/3420
ADR: `docs/adr/0097-capability-layer-four-shapes-and-core-declared-contracts.md`
Notes: `notes/coordination-agents.md`, `notes/call-out-configuration.md`

**Resolved**: 2026-11-09 — implementation tracked in #6147.
Questions 2 and 4 were answered earlier by ADR-0183. Question 1: a capability's
output never enters the case ledger as itself; only the act or case-file change it
leads to does, and the reasoning stays in the actor's own store. Question 3: a
Retriever is skipped when the case or actor store holds the fact (#6147); any
external cache belongs to the implementation (BT-18-029). Question 5: a tree that
carries caller-supplied content consults no Composer (BT-18-030).
Docs PR: https://github.com/CERTCC/Vultron/pull/6149.
Spec: `specs/behavior-tree-integration.yaml` (BT-18-029, BT-18-030).
Notes: `notes/coordination-agents.md`.
