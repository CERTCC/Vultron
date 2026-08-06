---
title: Embargo Default Semantics — Implementation Notes
status: active
description: >
  Design decisions for embargo policy EP-04 requirements; default embargo
  duration and expiry semantics; and the published-default / tacit-acceptance
  model that explains why the happy-path embargo requires no explicit
  negotiation exchange.
related_specs:
  - specs/case-management.yaml
  - specs/embargo-policy.yaml
relevant_packages:
  - transitions
  - vultron/bt/embargo_management
  - vultron/core/use_cases/triggers
---

# Embargo Default Semantics — Implementation Notes

Design decisions, implementation patterns, and known gaps for
`specs/embargo-policy.yaml` EP-04 requirements.

---

## The Published-Default / Tacit-Acceptance Model

### What it is

The Vultron protocol uses a **published-default / tacit-acceptance** model
for embargo establishment on the happy path:

1. The **receiver** (typically a Vendor or Coordinator) publishes a default
   embargo period as part of their Vulnerability Disclosure Policy.
2. When a **reporter** submits a report *without* including a counter-proposal,
   that silence constitutes **tacit acceptance** of the receiver's published
   default.
3. Because both parties have effectively agreed — the receiver by publishing
   the policy, the reporter by not objecting — the embargo transitions directly
   to `EM.ACTIVE` without an explicit `EP` (Embargo Proposal) / `EA` (Embargo
   Accept) exchange.

This is defined in `specs/embargo-policy.yaml` EP-04-001 and derives from the
protocol guidance in `docs/topics/process_models/em/defaults.md`.

### Why no EP/EA exchange appears on the happy path

A reader of a demo scenario or protocol trace may notice that `EM.ACTIVE` is
reached with no visible `ProposeEmbargo` or `AcceptEmbargo` activity. This is
**intentional and correct**, not a missing step. The implicit agreement is:

- The receiver's published policy is the standing proposal.
- The reporter's submission without objection is the acceptance.
- The protocol machinery (`InitializeDefaultEmbargoNode`) converts this
  implicit agreement into a concrete `EM.ACTIVE` state atomically — it applies
  the PROPOSE and ACCEPT state-machine transitions internally without emitting
  them as protocol messages, because no message exchange between the parties
  is required.

### Default path vs. negotiated path

| Scenario | Protocol path | EM outcome |
|---|---|---|
| Receiver has default, reporter proposes nothing | Default path (tacit acceptance) | `EM.ACTIVE` immediately (EP-04-001) |
| Receiver has default, reporter proposes *shorter* | Negotiated path | Shorter → `EM.ACTIVE`; receiver default → `EM.REVISE` (EP-04-003) |
| Receiver has default, reporter proposes *longer* | Negotiated path | Receiver default → `EM.ACTIVE`; longer → `EM.REVISE` (EP-04-003) |
| Neither party has a default or proposal | No embargo | `EM.NONE` remains |

The **default path** is the common happy-path scenario. No EP or EA message
is emitted; no per-participant acceptance round-trip occurs. The demo
scenarios all use this path because no reporter-side embargo proposal
mechanism yet exists in the implementation (see "Known Gap" below).

The **negotiated path** requires a reporter-proposal mechanism that is not
yet implemented (EP-04-003 / EP-04-004). When it is, it will involve an
explicit message exchange before `EM.ACTIVE` is reached.

### Implications for demos and implementers

- A demo that reaches `EM.ACTIVE` after `reporter_submits_report()` with no
  intervening embargo-negotiation steps is exercising the default path
  correctly. The absence of `ProposeEmbargo` / `AcceptEmbargo` activities is
  **not a gap** in the demo — it reflects the protocol rule.
- Future demos that implement the negotiated path MUST document clearly that
  they are doing so, so readers can distinguish the two paths.
- Implementers who add a UI or agent integration at the `EvaluateEmbargoProposal`
  call-out point are adding the *negotiated path* seam. The default path will
  still apply when that seam is not triggered.

---

## Decision Table

| Question | Decision | Rationale |
|---|---|---|
| Default embargo → `EM.PROPOSED` or `EM.ACTIVE`? | `EM.ACTIVE` | Report submission without counter-proposal = tacit acceptance per `docs/topics/process_models/em/defaults.md`. |
| Transition path: set directly or go through SM? | Apply PROPOSE+ACCEPT atomically in `InitializeDefaultEmbargoNode` | Keeps SM definition unchanged, preserves all state-machine invariants. |
| Intermediate `PROPOSED` persisted? | No | Atomic transitions; PROPOSED must not be visible externally. |
| What if sender proposes shorter embargo? | Sender's duration → ACTIVE; receiver's default → REVISE | "Shortest embargo wins" rule. |
| What if sender proposes longer embargo? | Receiver's default → ACTIVE; sender's longer → REVISE | Same shortest-wins rule from the other direction. |
| Does the SM need a new NONE→ACTIVE transition? | No | Atomic PROPOSE+ACCEPT inside the node is sufficient. |

---

## Implementation: `InitializeDefaultEmbargoNode`

`InitializeDefaultEmbargoNode` (in `vultron/core/behaviors/case/nodes/embargo.py`)
implements the default path by delegating to `EmbargoLifecycle.propose_embargo()`
followed by an internal accept, landing the case at `EM.ACTIVE` atomically. The
intermediate `EM.PROPOSED` state is never persisted or externally observable
(EP-04-002).

The case owner is seeded as a `SIGNATORY` in the same BT subtree immediately
after the embargo is activated (see "Case Owner Initial Embargo Consent" below).

---

## Known Gap: No Reporter Embargo Proposal Mechanism

The current protocol implementation has no mechanism for a reporter to
include an embargo proposal with (or before) a report submission. Until
that mechanism is implemented:

- EP-04-003 cannot be exercised; only EP-04-001 applies at case creation.

Two design paths exist for closing this gap (for future consideration):

1. **Inline proposal**: Reporter includes an embargo duration in the
   `Offer(Report)` payload. This requires a wire-format extension to allow
   an embargo policy or duration field on the offer object.

2. **Pre-negotiation flow**: Reporter creates a case with themselves as the
   sole participant, proposes an embargo to the receiver via the existing
   accept-embargo-before-case-share mechanics, then (optionally) transfers
   case ownership to the receiver upon acceptance. This uses existing
   machinery but is not yet documented as a standard flow.

---

## Protocol Source

The rules specified in EP-04 derive directly from
`docs/topics/process_models/em/defaults.md`:

| Protocol scenario | em_state outcome |
|---|---|
| Receiver has default; sender proposes nothing | `EM.ACTIVE` (EP-04-001) |
| Sender shorter, receiver longer | `EM.ACTIVE` at sender's duration; `EM.REVISE` for receiver's longer (EP-04-003) |
| Sender longer, receiver shorter | `EM.ACTIVE` at receiver's default; `EM.REVISE` for sender's longer (EP-04-003) |

---

## Cross-references

- `specs/embargo-policy.yaml` EP-04-001 through EP-04-004
- `specs/case-management.yaml` CM-12-004 (default embargo at case creation)
- `specs/duration.yaml` DUR-07-003 (default embargo logging)
- `docs/topics/process_models/em/defaults.md` (authoritative protocol source)

---

## Case Owner Initial Embargo Consent (BUG-26042204, 2026-04-22)

When a case is created with an active embargo (i.e., after the
`InitializeDefaultEmbargoNode` runs and the case reaches `EM.ACTIVE`), the
**case owner** MUST also be seeded as a `SIGNATORY` on the embargo at case
creation.

**Rationale**: The case creator is the case owner by default. It makes no
sense for the case owner to create an active embargo and then be locked out of
their own embargo as a non-signatory until a separate accept step occurs.

**Implementation**: After the default embargo is initialized (EM reaches
`ACTIVE` via the atomic PROPOSE+ACCEPT sequence in `InitializeDefaultEmbargoNode`),
the case owner's `CaseParticipant.embargo_adherence` consent state MUST be
transitioned to `SIGNATORY`. The PROPOSE+ACCEPT transition is an **internal**
atomic operation — it does not go through the receive-side `AcceptEmbargoReceivedUseCase`
path. The participant consent update MUST be applied in the same BT node or an
immediately following sibling node in the same subtree.

**Spec reference**: See `specs/case-management.yaml` CM-13 for the formal
requirement.
