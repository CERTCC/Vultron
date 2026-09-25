---
title: Embargo Default Semantics — Implementation Notes
status: active
description: >
  Design decisions for embargo policy EP-04 requirements; the actor-default
  versus protocol-default distinction and why the protocol default never
  competes under shortest-wins; default embargo duration and expiry semantics;
  the published-default / tacit-acceptance model that explains why the
  happy-path embargo requires no explicit negotiation exchange; why there is no
  pre-case embargo phase; why an RSVP deadline may not outlive its embargo; and
  how EP-04-003's two-party shortest-wins relates to EP-08's general
  earliest-expiration ordering for N open proposals.
related_specs:
  - specs/case-management.yaml
  - specs/embargo-policy.yaml
  - specs/vultron-as2-mapping.yaml
related_notes:
  - notes/participant-embargo-consent.md
  - notes/embargo-lifecycle.md
  - notes/configuration.md
  - notes/bt-pitfalls.md
relevant_packages:
  - transitions
  - vultron/bt/embargo_management
  - vultron/config
  - vultron/core/behaviors/case
  - vultron/core/models
  - vultron/core/services
  - vultron/core/use_cases/triggers
  - vultron/wire/as2/extractor
  - vultron/wire/as2/factories
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
| Receiver has actor default, reporter proposes nothing | Default path (tacit acceptance) | `EM.ACTIVE` immediately (EP-04-001) |
| Receiver has actor default, reporter proposes *shorter* | Negotiated path | Shorter → `EM.ACTIVE`; receiver default → `EM.REVISE` (EP-04-003) |
| Receiver has actor default, reporter proposes *longer* | Negotiated path | Receiver default → `EM.ACTIVE`; longer → `EM.REVISE` (EP-04-003) |
| Neither party has a default or proposal | **Protocol default** | `EM.ACTIVE` at the protocol default (EP-04-005) |
| Neither party has a default or proposal, and P/X/A is set | No embargo | `EM.NONE` remains (EP-04-008) |

The **default path** is the common happy-path scenario. No EP or EA message
is emitted; no per-participant acceptance round-trip occurs. The demo
scenarios all use this path because the reporter-side embargo proposal
mechanism is specified but not yet built — see
"Resolved: Reporter Embargo Proposal Mechanism" below.

The **negotiated path** requires that mechanism. EP-04-004 now specifies it
(a proposed `EmbargoEvent` embedded on the report offer), which makes
EP-04-003's shortest-wins comparison reachable; until the Tasks land, only
EP-04-001 and EP-04-005 apply at case creation.

**EP-04-003 is the two-party instance of a general rule.** Shortest-wins at case
creation is the same comparison **EP-08-001** states for *N* simultaneously open
proposals: resolve earliest `end_time` first and handle the remainder as
revisions (ADR-0100). EP-04-003 `refines` EP-08-001 accordingly. Two consequences
for implementers:

- **One comparator, not two.** #3392 builds EP-04-003's comparison and #3470
  builds EP-08's; they MUST share a single earliest-end-date comparator rather
  than growing separate ones that can disagree.
- There is **no multi-candidate poll** to reach for when more than two sets of
  terms are on the table — ADR-0100 retired `ChoosePreferredEmbargo` (#3469).
  Send one `Invite` per candidate and answer each on its own.

Mechanics of the N-proposal case, including why neither record of open proposals
is currently pruned, are in
[`embargo-lifecycle.md`](embargo-lifecycle.md) § "Open Proposals Resolve
Earliest-Expiration First (EP-08)".

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
| What if *nobody* has a default or proposal? | Protocol default → ACTIVE (EP-04-005) | A case with no embargo is what the EM process exists to avoid; reaching it by mutual silence is the least deliberate route there. ADR-0096. |
| Does the protocol default take part in shortest-wins? | **No** (EP-04-006) | A short default that competed would beat every longer proposal and cap every embargo at its own length. |
| Is the protocol default a minimum on agreed terms? | No (EP-04-007) | It bounds the fallback, not what parties may agree. A 12-hour proposal yields 12 hours. |
| What if the vulnerability is already public? | No embargo; `EM.NONE` (EP-04-008) | VP-06-001 already forbids proposing *or accepting* once P/X/A is set (EMB-01-002 is the accept half). An embargo on a public vulnerability protects nothing. |

---

## Implementation: `InitializeDefaultEmbargoNode`

`InitializeDefaultEmbargoNode` (in `vultron/core/behaviors/case/embargo_tree.py`;
the leaf nodes it composes live in `vultron/core/behaviors/case/nodes/embargo.py`)
implements the default path by delegating to `EmbargoLifecycle.propose_embargo()`
followed by an internal accept, landing the case at `EM.ACTIVE` atomically. The
intermediate `EM.PROPOSED` state is never persisted or externally observable
(EP-04-002).

The case owner is seeded as a `SIGNATORY` in the same BT subtree immediately
after the embargo is activated (see "Case Owner Initial Embargo Consent" below).

---

## Two Kinds of Default — Do Not Conflate Them

This is the single most important distinction in this file, and the codebase got
it wrong for a long time.

| Term | What it is | Competes under shortest-wins |
|---|---|---|
| **Actor default** | A duration from a published `EmbargoPolicy`; what `em/defaults.md` calls a *standing proposal* | **Yes** |
| **Protocol default** | The fallback applied when no proposal and no actor default applies | **No** |

The protocol default is **the value when the candidate set is empty, never a
member of the candidate set** (EP-04-006). A 72-hour protocol default that
competed under shortest-wins would beat every longer proposal and cap every
embargo in the system at 72 hours; no longer embargo could ever be agreed.

It is also **not a minimum** (EP-04-007). A reporter who proposes 12 hours gets
12 hours. EP-04-005's `[72 hours, 5 days]` range bounds what the *fallback* may be
configured to, not what parties may agree.

### How the conflation hid a defect (resolved, #3390)

`_preferred_embargo_duration()` (formerly in
`vultron/core/behaviors/case/nodes/embargo.py`) returned a hardcoded 90-day
fallback into the *same* blackboard key (`default_embargo_duration`) that a
published `EmbargoPolicy` filled. Downstream, nothing could distinguish "the
receiver published 90 days" from "the receiver published nothing". That is how a
silent 90-day embargo survived in contradiction of three documents —
`em/defaults.md` ("no embargo SHALL exist"), this file's own decision table, and
`em/principles.md` ("shortest duration possible").

It also inverted the incentive the protocol depends on: a receiver who published
*nothing* got a longer embargo than one who published a considered 30 days. The
short protocol default exists to reverse that — publishing must be the rewarded
behavior. The same function also selected `policies[0]` from an unordered
`list_objects()` result, so which policy applied was arbitrary.

What replaced it:

| Concern | Where it lives now |
|---|---|
| Configured fallback, refused outside `[72h, 5d]` (EP-04-005) | `ActorConfig.protocol_default_embargo_duration` (`vultron/config/actor.py`) |
| Shortest-wins over candidates only, fallback when none (EP-04-006/007) | `resolve_initial_embargo_duration()` (`vultron/core/services/embargo_duration.py`) |
| Deterministic actor default: shortest, ties by policy id (EP-04-010) | `select_actor_default()` (same module) |
| Distinct blackboard names (EP-04-010) | `actor_default_embargo_duration`, `protocol_default_embargo_duration`, and the resolved `initial_embargo_duration` (duration plus source) |
| P/X/A refusal before anything is created (EP-04-008) | `CaseNotEmbargoEligibleNode`, the first arm of the `InitializeDefaultEmbargoNode` Selector |

The refusal arm is a *negative* condition — SUCCESS means "not eligible, stop" —
rather than a Success fallback after the creation sequence. A fallback would turn
any failure in creation into a silent "no embargo"; with the refusal arm first,
creation failures still propagate. The refusal arm itself returns FAILURE only
for "eligible": a missing case or unreadable store *raises*, because FAILURE
there would run creation, which persists an `EmbargoEvent` before anything
re-checks P/X/A (`notes/bt-pitfalls.md` § "A Refusal Arm in a Selector Fails
Toward 'Admit'"). The sender-proposal input
(`sender_proposed_embargo_duration`) is wired but unwritten until the embedded
proposal lands (#3392).

### There is a third implicit duration, and it is the quietest

The 90-day constant and the shared key are gone; one unchosen number remains.
`EmbargoEvent.end_time` (`vultron/core/models/embargo_event.py`) carries
`default_factory=_45_days_hence`, so **any** `EmbargoEvent` constructed without an
explicit `end_time` silently acquires 45 days — nine times the 5-day ceiling
EP-04-005 sets, and reachable from any construction site that forgets the argument.

It hides differently from the 90-day fallback did. That fallback was at least
reachable by reading one function that everyone knew resolved the default. A field
default applies wherever the object is built, with no call site to inspect.
EP-04-010 requires the protocol default be the *single* source of the fallback
duration, so this field default must resolve to it or be made explicit at
construction. Tracked as #3404.

## Resolved: Reporter Embargo Proposal Mechanism (EP-04-004)

**This gap is closed by ADR-0096.** A reporter states terms by embedding a
proposed `EmbargoEvent` in the `Offer(VulnerabilityReport)` activity.
`EmbargoEvent.context` carries the report URI before a case exists and is
rewritten to the case URI at case creation (EP-04-009). That discharges
EP-04-004's contingency and makes EP-04-003 reachable for the first time.

Two alternatives were rejected. An activity-level `end_time` on the `Offer`
would add a third meaning to a field CM-28-001 already calls a critical naming
hazard. Inlining the reporter's own `EmbargoPolicy` states a standing preference,
not terms for this report.

### Do not revive the proto-case

An earlier version of this section proposed a second design path: the reporter
creates a case with themselves as sole participant, negotiates, then transfers
ownership on acceptance. **Do not build this.** ADR-0041 supersedes ADR-0015 for
precisely this window, and ADR-0089 re-rejected the proto-case when deciding where
pre-case RM state lives. The path was recorded here before either decision landed,
which is why it read as a live option for so long.

## No Pre-Case Embargo Phase

CONCERN-2215 asked whether Vultron gets a protocol phase before a case exists, on
the strength of `model_interactions/rm_em.md` stating that the EM process MAY begin
before the report is sent. **ADR-0096 answered no**, and the reason is stronger
than "not implemented":

| Fact | Where |
|---|---|
| EM is defined as a global **per-case** state machine | `docs/reference/glossary.md` |
| EM state exists only as `CaseStatus.em` (an `EmDimension`) | `vultron/core/models/dimensions.py` |
| `EmbargoEvent.context` is required, and every core construction site set it to `case_id` | `case/nodes/embargo.py`, `triggers/embargo/{propose,revise}.py` |
| `propose_embargo(case_id=…)` raises `VultronNotFoundError` when the case does not resolve | `vultron/core/services/embargo_lifecycle.py` |

So the documented $q^{em} \in N \xrightarrow{p} P$ before any case exists named a
machine instance that could not exist. `rm_em.md` has been corrected: its
*motivation* survives (a sender may want terms fixed before disclosing), its
*mechanism claim* is withdrawn.

What replaces the phase is two rules, both above: the protocol default means a
reporter never faces "no embargo at all", and the embedded proposal means they can
always state the terms they want. Shortest-wins settles any disagreement at case
creation.

Note that EP-04-009's context widening does give pre-case embargo terms a
legitimate home. What ADR-0096 declines is the *phase*, not the *representation* —
so if a genuine pre-submission negotiation is ever wanted, the object it would
negotiate over already exists.

## An RSVP Deadline May Not Outlive Its Embargo

EP-07-006 and CM-28-011, added by ADR-0096, close a defect that is independent of
everything else in this file.

Nothing previously compared the RSVP deadline against the embargo's own
`end_time`. EP-07-003 clamped a sub-minimum deadline **up** to a 72-hour floor,
with no upper bound at all. So:

> Invite a participant to a 24-hour embargo. The `Invite(EmbargoEvent)` carries no
> `end_time`, so the CM-18-002 policy window applies: 7 days. The pocket veto fires
> on day 7. The embargo ended at hour 24.

The participant is asked to consent to an embargo that is already over, and their
inaction is recorded as a decline six days after it stopped mattering. The same
thing happened on day 28 of a 30-day embargo with an ordinary published actor
default — without any protocol default in the picture.

The rule is now: an RSVP deadline is clamped **down** to the embargo's `end_time`.
Consequently EP-07-002's minimum became "72 hours, **or the remaining embargo,
whichever is shorter**" — otherwise the floor and the new ceiling would contradict
each other whenever the remaining embargo is under 72 hours, which EP-04-007 makes
reachable by permitting a 12-hour agreed embargo.

An invitee to a 12-hour embargo therefore gets a 12-hour window. That is
principled: the floor exists to stop an *unreasonably* short deadline, and a
deadline equal to the whole embargo is not unreasonable.

Why the protocol default floor is 72 hours and not 24: it is set equal to
EP-07-002's *configured* minimum RSVP window on purpose, so the shortest embargo the
protocol produces is exactly as long as the shortest answer window it grants by
default. The two configured numbers move together instead of needing to be
reconciled.

Note what that alignment does **not** buy. Because a stated proposal may be shorter
than the protocol default, EP-07-002's *effective* minimum still has to be computed
as the lesser of the configured window and the time remaining in the embargo. The
arithmetic relating the RSVP floor to the embargo duration exists either way; the
alignment only guarantees it never fires on the protocol-default path.

### Where the rule lives (#3391)

One pure function, `resolve_rsvp_deadline()` (`vultron/core/models/rsvp_deadline.py`),
computes the effective deadline for both sides, which is what makes the clamp up
and the clamp down agree. Every window is measured from the invite's `published`
time:

1. Computed deadline: the explicit `Invite.end_time`, else `published` plus the
   policy window (EP-07-001, CM-18-002).
2. Minimum: `published` plus the minimum window, or the embargo's end, whichever
   is earlier (EP-07-002).
3. Raise to the minimum (EP-07-003), then lower to the embargo's end (EP-07-006).

The sender side (`em_propose_embargo_activity`) refuses a deadline the function
would move. The receiver side (`extract_intent`) applies the moved value, logs
each clamp at INFO with the requested and effective values (EP-07-005), and never
rejects the invitation (EP-07-004). Because the policy window is now applied at
extraction, an invite without `end_time` carries a concrete `rsvp_deadline` into
core rather than `None`.

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

- `specs/embargo-policy.yaml` EP-04-001 through EP-04-010, EP-07-002/003/005/006
- `specs/case-management.yaml` CM-12-004 and CM-14-010 (default embargo at case
  creation, no longer conditional on a configured policy), CM-14-006 (reporter
  proposal reconciliation, now reachable), CM-18-002 (pocket-veto policy window),
  CM-28-002 (explicit `Invite.end_time` precedence, bounded by EP-07-006),
  CM-28-011 (window bounded by the embargo)
- `specs/vultron-protocol-spec.yaml` VP-07-001 (the "no embargo SHALL exist" rule
  the protocol default replaces), VP-06-001 (propose/accept forbidden once P/X/A is set)
- `specs/vultron-as2-mapping.yaml` VAM-05-001 (`Create(Event)` context may be a report)
- `specs/duration.yaml` DUR-07-003 (default embargo logging)
- `docs/topics/process_models/em/defaults.md` (authoritative protocol source)
- `docs/topics/process_models/model_interactions/rm_em.md` (pre-case guidance, corrected)
- ADR-0096 (protocol default embargo; no pre-case phase), ADR-0065 (RSVP deadline
  and pocket veto as one mechanism), ADR-0041 / ADR-0089 (why not a proto-case)
