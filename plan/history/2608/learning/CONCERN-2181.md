---
source: CONCERN-2181
timestamp: '2026-08-11T20:32:27.108509+00:00'
title: Demo harness confuses temporal sequence for causal sequence
type: learning
---

## Summary

The demo's control flow is structured as a temporal sequence of events ("A
happens, then B, then C") rather than a causal chain ("A happens, *therefore* B,
*therefore* C"). This distinction causes race conditions, timeout failures, and
ordering bugs — the harness waits for effects that haven't been triggered because
their causes were never processed.

## Surface Symptom vs. Underlying Problem

**Surface symptom:** The demo is flaky — it times out waiting for events, actors
reply before receiving the messages they'd need to reply to, and messages are sent
without the required addressing step having occurred first.

**Underlying problem:** The demo is designed around *temporal* sequencing rather
than *causal* sequencing. A sound demo should enforce invariants such as "B cannot
reply until B has received and processed A's activity". The current approach
instead relies on timing assumptions that race against asynchronous execution.

## What the investigation found

Of the 19 sub-issues of Epic #2136, **7 were this same defect** in a different
scenario (#2120, #2135, #2141, #2169, #2178, #2180, #2186) and 2 more were
partially attributable (#2134 leg b, #2193). Bug #2178's own triage comment states
the thesis independently: *"the demo treated async causal steps as sequential
(x then y) rather than causally linked (x therefore y)."*

Three structural findings beyond the original report:

1. **The spec corpus duplicated the workaround instead of stating the rule.**
   Seven scenario-specific requirements each said "poll here before proceeding"
   for one scenario. DEMOMA-11-009 stated the general rule correctly but was
   scoped to FVCV-handoff alone.

2. **The existing gates did not gate.** `demo_step` and `demo_check` both record
   a failure and continue, so a precondition written with `demo_check` is
   advisory — the dependent step runs anyway on state that was never established.
   Seven demo test modules patch these context managers out with
   `contextlib.nullcontext`, so no test exercised their real control flow. This
   is why the `RM.VALID`-before-`engage-case` gate went unnoticed.

3. **Which observable proves the cause landed was guesswork.** The gate before
   `validate-report` was re-picked three times in one week.

## Correction to the original concern

The concern asserted that "the underlying protocol state machines and BT nodes
... are likely already correct. The gap is in the *demo harness* ... not in the
actor logic itself." The evidence contradicts this and the correction is recorded
in ADR-0058 so it is not inherited: #2169's race is server-side fan-out that a
client-side wait cannot prevent, #2186 was consequently fixed in the protocol
(ADR-0037/0055 lineage), and #2194 — a bare-string `Accept.object_` tripping the
MV-09-001 outbox gate — is squarely an actor-logic bug. The pattern is real and
well-attested, but it is not exclusively a harness problem.

A rival recurring class also surfaced: outbound activities carrying bare URN
references where fully inline typed objects are required (#2134 leg a violating
CBT-01-007, #2194 violating MV-09-001). It is comparable in frequency among
post-concern bugs and is tracked separately.

Causal gating does **not** green Epic #2136 on its own — #2194 and #2195 are
delivery and serialization defects it would not have prevented.

## Resolution

**Resolved**: 2026-08-11 — implementation tracked in #2201, #2202, #2203, #2204.

Docs PR: <https://github.com/CERTCC/Vultron/pull/2200>.

Decision: harness-side causal gating plus domain narratives as a conformance
oracle, chosen over per-scenario tuned timeouts, pushing all ordering into
actor-side buffering, and a declarative dependency graph with static validation.
Recorded as ADR-0058 with status `accepted-provisional` — the gating primitive
shape and causal-edge schema are expected to converge after the first migrations.

Spec: `specs/event-driven-control-flow.yaml` EDF-06-001 through EDF-06-007;
`specs/multi-actor-demo.yaml` DEMOMA-22-001 through DEMOMA-22-006 (generalizing
DEMOMA-11-009 to all scenarios); `specs/demo-ci.yaml` DEMOCI-01-007 (`demo_gate`).

Notes: `notes/event-driven-control-flow.md` § "Temporal Sequence vs. Causal
Sequence"; `notes/protocol-event-cascades.md` (actor-side vs harness-side
causality); `AGENTS.md` and `vultron/demo/AGENTS.md` pitfall entries, including a
correction to the CONCERN-1635 guidance "the demo just needs to wait long enough",
which embodied the very framing this concern identifies as the defect.
