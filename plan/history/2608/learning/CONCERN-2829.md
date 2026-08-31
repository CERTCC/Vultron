---
source: CONCERN-2829
timestamp: '2026-08-31T17:27:14.107908+00:00'
title: 'G01: async round-trip and delivery-confirmation primitive'
type: learning
---

Planning group **G01** of 19 (parent umbrella #2828), covering members #2657, #1880, #2367, #2369, #2812, #2809 and #2796.

## Original concern

Six issues filed independently across six Epics all bottomed out on the same missing
mechanism: core had no way to (a) suspend a behavior and resume it when a delayed
external response arrives, and (b) get delivery confirmation back from the wire into a
commit decision. The umbrella asked for one ADR establishing the async-response /
delivery-confirmation model, a yes/no verdict on the NACK question (not another
deferral), spec amendments, a docs page, and Tasks sequenced primitive-first.

## What the investigation found

Three findings reframed the session.

**1. The framework could never host suspension, and the requirement mandating it had
zero implementations.** `BTBridge.execute_tree()` busy-loops on root `RUNNING` for 100
ticks, logs `ERROR`, returns `FAILURE`, then discards the tree in
`finally: bt.shutdown()`. Meanwhile `grep -r "return Status.RUNNING" vultron/` returns
nothing — EDF-04-002 required an external decision node to return `RUNNING` while
awaiting input, and no node in the codebase had ever complied. Any node that had would
have busy-looped and then failed.

**2. The mechanism was already in production, hand-built, once.**
`create_recommend_actor_to_case_received_tree` (`suggest_actor_tree.py`, ADR-0026 /
CM-16) records receipt then routes through disjoint branches — already a participant /
invite in flight / owner asked and unanswered / fresh — reading open-closed state from
the ledger via `find_protocol_pair`, with sibling trees for the `Accept` and `Reject`.

**3. The durable per-ask record was too.** `VultronOfferRecord` is DataLayer-backed,
keyed by `build_id(offer_id)`, written by the adapter that calls the factory, and works
**before a case exists**.

So the question was never how to host an asynchronous exchange. It was why each
instance cost a bespoke implementation. `RequireCaseOwnerApprovalNode` is a
deny-always stub because nobody generalised the first instance — not because the design
was unknown.

## Decision recorded (ADR-0080)

An actor that cannot act on its own authority **emits a request and terminates
successfully** — `SUCCESS` means *I asked*. The reply starts new work. Nothing
suspends, because the work is divided at the question rather than paused there.

Each gated interaction is one tree that routes on conversation state before acting,
with disjoint branches (reply in hand / asked and waiting / asked and expired / never
asked). Replaying the original message was rejected: CLP-13-001 requires an idempotency
guard that detects a duplicate to return FAILURE and write nothing, so a replayed tree
dies before reaching the gate. Splitting each tree into ask and act halves was rejected
because two halves drift.

Authority comes from the stored ask, never the reply — ADR-0026's trust rule
generalised, plus its time dimension. Expiry consequence is fixed per ask kind in the
spec; only the duration is configurable, and that is safe because the deadline travels
on the wire in `end_time`. One register class implements the create / close / time-out
lifecycle and is instantiated twice: the durable two-directional ask register (may
block) and the existing in-memory suppressor (never blocks, forgotten on restart by
design). The register never authorises — a gate always reads the ledger. Expiry is
noticed opportunistically plus via a `reap-expired-asks` trigger for an external
Sentinel, which is also what makes expiry testable causally rather than by elapsed
time.

**NACK verdict: yes, narrowly.** `Create(ProcessingFault)` — one dedicated object type,
`Create` rather than `Reject` (which presupposes something rejectable), pointer never
echo (an invalid payload cannot be re-typed), authenticated senders only (a parser
oracle otherwise), RFC 9457 Problem Details with failure classes as namespace URIs.
This **discharges** the deferral ADR-0049 recorded rather than overturning it: that ADR
explicitly asked for sender notification to be "designed on its own merits" later, and
its own decision (no RE/EE/CE/GE/GI message family) stands.

**#2657 reframed.** Gating the ledger commit on delivery is declined: the ledger records
what an actor decided and observed at the time it happened, gating it would make an
actor's history hostage to the network, it inverts CLP-10-006's ordering, and it raises
an unanswerable partial-delivery question. The real defect is that nothing links a
dead-lettered activity to the entry claiming its event happened.

## Specs found to be wrong

- **EDF-04-002** — mandated a mechanism the executor cannot host, with zero
  implementations. Reversed.
- **CLP-11-001** — over-reached from "don't infer protocol state from the outbox" into
  "the ledger is the only source", which contradicted DL-06-002 and forbade a
  working-set register. Narrowed to the authorization question.
- **ADR-0076's capability-shape assignment** — an Evaluator asked "is this approved?"
  when no answer yet exists can only answer no, which is precisely the stub's
  behaviour. The conservative default it establishes is unaffected.
- **CP-05-006** — said to answer a duplicate proposal with a *new* Accept, which the
  vendor cannot distinguish from a second decision. Corrected to re-send the stored
  original, and raised SHOULD → MUST.

## Prerequisite discovered

There is **no shared emit path**. `outbox_append` is called from ~20 modules and at
least four private `_emit` helpers exist independently, so "built into the thing that
emits an Offer" had nowhere to live. It cannot be the AS2 factory (wire layer, no
DataLayer). This blocks the whole chain — and #2657's premise assumed a shared path
that is in fact copy-pasted.

**Resolved**: 2026-08-31 — implementation tracked in #2881, #2883, #2884, #2885, #2886, #2887, #2889, #2890, #2891.
Docs PR: <https://github.com/CERTCC/Vultron/pull/2880>.
Spec: `specs/protocol-asks.yaml`, plus amendments to CLP-11, EDF-04, RSH-07, CP-05,
OX-14 and TRIG-04.
Notes: `notes/protocol-asks.md`.
ADR: ADR-0080 (amends ADR-0076, ADR-0046, ADR-0026; discharges ADR-0049's deferral).
Docs: `docs/topics/protocol_flow.md` (for #2796).
Remaining open: #2369 stays open, re-scoped to outcome observability for behaviours
that fail without asking.
