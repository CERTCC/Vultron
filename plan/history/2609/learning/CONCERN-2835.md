---
source: CONCERN-2835
timestamp: '2026-09-18T20:13:59.256419+00:00'
title: 'G07: capability layer foundations'
type: learning
---

Planning group G07 of 19 — the capability layer. Batched #2452 (what must a
capability define), #2453 (how are implementations invoked), #2454 (rename the
shape classes), the five shape Ideas (#1143, #1144, #1145, #1146, #2451), #1142
(Participant Discovery), #1980 (decompose #441), and #2798 (docs page).

**Resolved**: 2026-09-18 — implementation tracked in issues #3421, #3422, #3423,
and #3424, plus #3425, #3426, and #3427.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3420>.
ADR: `docs/adr/0097-capability-layer-four-shapes-and-core-declared-contracts.md`.
Spec: `specs/behavior-tree-integration.yaml` (BT-18-012 through BT-18-015,
BT-23-013; rewordings to BT-18-001, BT-18-005, BT-18-006, BT-20-003).
Notes: `notes/coordination-agents.md`, `notes/call-out-configuration.md`.

## What the session actually found

Two of the three cross-cutting questions were already answered, and reading the
code first is what revealed it.

**#2453 was answered by G01.** ADR-0080 established that nothing in Vultron
suspends, and BT-18-011 turned that into an enforced contract at the call-out seam
— `SynchronousCallOut` wraps every factory a bundle hands out, raising
`CallOutContractError` as an *internal* error on a `RUNNING` return. So of #2453's
four candidate conventions, "async callback with the BT suspended" was already
ruled out and guarded. The convention is uniform, synchronous, in-process. The
per-shape variation #2453 anticipated survived only for Sentinel, which turned out
not to be a call-out shape at all.

**#2452's gap was an unadopted decision, not a missing artifact.** ADR-0044 had
already mandated py_trees typed ports as the standard base for every node in
`vultron/core/behaviors/`, with runtime type checks on read and write. Core files
had adopted it; no call-out backend had. The answer was to use it rather than to
design a capability registry.

## The defect that reframed the session

BT-18-002 (MUST) forbids returning SUCCESS without writing the declared output
keys. `AlwaysSucceed` returns SUCCESS and writes nothing — and it is the
DETERMINISTIC default that BT-23-001 makes the default for every tree builder,
test, and demo, and that BT-23-008's rationale calls the production-usable
happy-path backend.

It could not comply. The only machine-readable form of the contract was an
`output_keys` dict on a mixin in `vultron/demo/fuzzer/`, which core must not import
(BT-16-001); the rest was docstring prose. Measured at planning time: 64 core
DETERMINISTIC factory fields — 49 on a bare `_always_succeed`, 13 on `_always_fail`,
and exactly **one** resolving to a contract-honouring backend
(`_DeterministicPrioritizePublicationIntents`), against 59 capabilities declaring
non-empty output keys.

Three things about the shape of this failure are worth carrying forward:

1. **It was silent, and silence is why it survived.** Downstream gates declare the
   key `required=False`, so a missing output yields FAILURE and the arm becomes a
   graceful no-op. The tree goes green and the protocol makes no progress — the
   exact opposite of the ceiling rule's stated purpose.
2. **The test suite compensated instead of catching.**
   `test_publication_tree.py` writes `publication_intent_decision` by hand before
   ticking, with the comment "Without this write, all three arms…". A test that
   supplies what production cannot is documenting a defect as a fixture.
3. **A rule written for one case was silently generalised to another.**
   BT-23-002/006/007 pick the deterministic backend from the stochastic
   probability. For a boolean call-out, direction *is* the whole contract. Extended
   to a data-producing capability, the same sentence drops half of it. Nothing
   announced the generalisation.

## Decisions

1. A capability declares its blackboard contract as ADR-0044 typed ports on a
   core-owned declaration (BT-18-012). Structural discovery, not a registry.
2. The calling convention is uniform, synchronous, in-process — adopting ADR-0080
   rather than defining a parallel primitive.
3. Call-out point versus protocol ask is a normative classification rule
   (BT-18-014). It had existed as prose in `docs/topics/capability_model/index.md`
   and was normative nowhere, so it could only be rediscovered by audit — which is
   how ADR-0080 found it, in ADR-0076's Case Owner gates.
4. A call-out answer is time-bounded, with the bound as per-actor configuration
   rather than a spec constant (BT-18-015). The duration is local to one actor and
   observable by no peer, so deployments differing is not divergence — the opposite
   of an ask deadline, which travels on the wire in `end_time` so both parties read
   the same number.
5. Sentinel is demoted out of the capability-shape taxonomy (BT-18-013).
6. The four shape base classes move to core and are renamed to the capability
   vocabulary — answering #2454 "rename now".
7. Requirements extend BT-18/BT-23 in place; no new spec file or prefix.

## Why Sentinel was demoted, and the better reason found mid-interview

The first argument was that Sentinel shares none of the capability machinery — no
factory, no bundle field, no blackboard contract, no synchronous guard, no
ceiling/floor default — and that BT-18-006 exists solely to stop authors
misclassifying call-outs as Sentinels. The code agreed: `SentinelCallOutPoint` and
its three subclasses were py_trees Behaviours carrying a `success_rate`, wired into
no bundle and instantiated nowhere, while `CheckNoNewDeploymentInfoNode` read a
blackboard flag attributed to a Sentinel that never ran. The class hierarchy
asserted "this is a BT node" and the docstring asserted the opposite in the same
file.

The better argument came from the maintainer during the interview: **a Sentinel may
be a case participant.** Admitted through the ordinary Invite/Accept path — most
naturally holding `CVDRole.OBSERVER` (ADR-0057, CM-25) — it receives
`Announce(CaseLedgerEntry)` like any participant, so what it monitors can be the
case's *own* state, and it can act by emitting ordinary protocol messages. #1856
observes case state; #1845's title has its monitor posting `Add(ParticipantStatus)`
into the case.

That correction matters twice over:

- **The discriminator is who initiates, not information provenance.** "Sentinel
  reads external data" is wrong and would misclassify a participant monitor. A
  capability is *consulted*; a Sentinel decides for itself that the moment has come.
- **It is the stronger basis for demotion.** A thing holding protocol identity, a
  roster seat, a role, and a case replica, acting by emitting protocol messages, is
  a *peer* — not an interface contract at a BT seam. That is the Agentic
  Participants concept, which is why #2450 is the right home.

ADR-0097 records two deployment shapes — participant and operator-side — that
differ in protocol visibility, so the choice is owed per monitor rather than once
for all of them.

## Process notes

- **The planning protocol in #2828 corrected the plan mid-session.** The intent had
  been to reparent #1143 and G14's four Sentinel Ideas onto #2450. Rule "No member
  issues are reparented" forbids it, to preserve board tiers and avoid re-shaping
  frozen epics. They were annotated instead and G14 (#2842) was notified of its
  shifted premise.
- **Specs describe what is, not what changed.** A first draft of the new
  requirements carried before/after narrative and measured counts in their
  rationales. Counts in a long-lived doc violate MS-16-001, and evolution history
  belongs in the ADR (a point-in-time record) rather than in a declarative
  requirement. The spec entries were rewritten declaratively and BT-18-001 was
  reworded so it no longer contradicts BT-18-012 — the fix for a stale statement is
  to correct the statement, not to add a "refines" note explaining the conflict.
- **The docs catalog is the next instance of a known failure mode.**
  `docs/topics/capability_model/index.md` hand-maintains ~44 named capabilities and
  still states the invocation model is "blocked on a broader async delivery design
  that has not been written yet" — contradicting `docs/howto/wire_capability.md` in
  the same tree. Once capabilities declare their contracts in core the catalog
  becomes derivable, so #3425 generates or ratchets it rather than resyncing it.
- **#2798's AC-7 was already satisfied** before the session started (closed
  COMPLETED 2026-08-28). The umbrella did not know. Checking member state early is
  cheap and changed the deliverable.
- **Deviation from the umbrella's AC-4**: one Task (#3421) covers all four shape
  base classes rather than five thin per-shape Tasks, since with Sentinel demoted
  and the declaration shared, separate Tasks would touch the same module four times.
