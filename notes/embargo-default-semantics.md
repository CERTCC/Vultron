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
  earliest-expiration ordering for N open proposals; why the creation-time
  revision's registration order no longer touches consent (ADR-0093); how
  the creation-time revision is relayed to the other party after
  initialization and indexed only once sent (EP-04-011, CM-14-007, ADR-0113);
  why creation-time initialization runs once per case with the EM state, not
  the active-embargo reference, as the evidence (EP-04-012); why a rerun on a
  half-built case reuses the minted event's case-derived id; and why the actor
  default is the CASE_OWNER's profile policy, carried inline on the case proposal
  (CP-01-009, CP-01-010).
related_specs:
  - specs/case-management.yaml
  - specs/case-proposal.yaml
  - specs/embargo-policy.yaml
  - specs/message-semantics-mapping.yaml
  - specs/vultron-as2-mapping.yaml
related_notes:
  - notes/participant-embargo-consent.md
  - notes/embargo-lifecycle.md
  - notes/case-communication-model.md
  - notes/case-proposal.md
  - notes/configuration.md
  - notes/bt-pitfalls.md
relevant_packages:
  - transitions
  - vultron/bt/embargo_management
  - vultron/config
  - vultron/core/behaviors/case
  - vultron/core/behaviors/embargo
  - vultron/core/models
  - vultron/core/services
  - vultron/core/use_cases/triggers
  - vultron/wire/as2/extractor
  - vultron/wire/as2/factories
  - vultron/wire/as2/parser.py
  - vultron/adapters/driven/trigger_activity_adapter
  - vultron/adapters/driving/fastapi/routers/actors
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
is emitted; no per-participant acceptance round-trip occurs. Every
multi-actor scenario uses this path: `reporter_submits_report()` states no
terms unless a caller passes `proposed_embargo_end_time`.

The **negotiated path** is EP-04-004's mechanism — a proposed `EmbargoEvent`
embedded on the report Offer (#3392) — which makes EP-04-003's shortest-wins
comparison reachable. Its demonstration is the `report-with-embargo` exchange
demo (`vultron/demo/exchange/report_with_embargo_demo.py`, #3393): the
Reporter's `submit-report` trigger carries `proposed_embargo_end_time`, the
Receiver publishes its actor default through `PUT
/actors/{actor_id}/embargo-policy` (EP-02, #3972), and three runs show the
Reporter's shorter terms winning, the Receiver's shorter default winning, and
a Receiver with no default at all. No proposal exchange precedes the case: the
comparison is settled at case creation, so a reader distinguishes the two
paths by whether terms were stated on the Offer. What follows creation is
EP-04-011's relay of the losing terms to the winner — so when the Receiver's
default wins, the Receiver (the CASE_OWNER) is invited to the Reporter's
longer terms, its default response decision accepts, and an owner's
acceptance activates them: that run settles at `EM.ACTIVE` on the Reporter's
terms. When the Reporter's terms win, the Reporter's acceptance only records
consent, and the case stays at `EM.REVISE`.

**EP-04-003 is the two-party instance of a general rule.** Shortest-wins at case
creation is the same comparison **EP-08-001** states for *N* simultaneously open
proposals: resolve earliest `end_time` first and handle the remainder as
revisions (ADR-0100). EP-04-003 `refines` EP-08-001 accordingly. Two consequences
for implementers:

- **One comparator, not two.** `earliest_ending` in
  `vultron/core/services/embargo_ordering.py` (#3470) is the comparator:
  `resolve_initial_embargo_duration` uses it for EP-04-003's shortest-wins and
  `find_embargo_proposal_id` uses it for EP-08's earliest-expiring selection. #3392 extends the case-creation input; it MUST NOT
  grow a second comparator.
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
- A demo that implements the negotiated path MUST document clearly that it is
  doing so, so readers can distinguish the two paths. `report-with-embargo`
  does, in its module docstring and in the how-to page's "Try it" block.
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
the leaf nodes it composes live in
`vultron/core/behaviors/case/nodes/embargo_resolution.py` and `embargo.py`)
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
| Deterministic actor default (EP-04-010) | `actor_default_duration()` (same module) reads the one `embargo_policy` field of the CASE_OWNER's profile (EP-01-001), so there is never a choice among records |
| Actor default is the CASE_OWNER's own policy (EP-04-003, CP-01-010) | `ResolveEmbargoDurationNode` reads the inline profile on the blackboard (`owner_profile`) and fails unless its id is `case.attributed_to`, which names the CASE_OWNER on every creation path (CM-02-008, CP-09-001) |
| Distinct blackboard names (EP-04-010) | `actor_default_embargo_duration`, `protocol_default_embargo_duration`, and the resolved `initial_embargo_duration` (duration plus source) |
| Initialization runs once per case (EP-04-012) | `CaseEmbargoAlreadyInitializedNode`, the first arm of the `InitializeDefaultEmbargoNode` Selector — see "Initialization Runs Once Per Case" below |
| P/X/A refusal before anything is created (EP-04-008) | `CaseNotEmbargoEligibleNode`, the second arm of the `InitializeDefaultEmbargoNode` Selector |

**Whose policy is the actor default.** At creation the case has two actors with
terms: the CASE_OWNER and the reporter. The CASE_OWNER is the actor that received
the `Offer(VulnerabilityReport)` and caused the case to be created, whatever
other roles it holds, and `case.attributed_to` names it on every creation path
(CM-02-008, CP-09-001). The reporter's terms arrive as the sender proposal, so the
actor default is the policy on the CASE_OWNER's actor profile and no one else's.
The creation tree runs as the CASE_MANAGER, but the CASE_MANAGER contributes no
terms of its own: a policy the CASE_MANAGER, or anyone else, published is never a
candidate.

**How the CASE_OWNER's policy reaches creation.** When the CASE_MANAGER creates
the case, the CASE_OWNER's profile lives in the CASE_OWNER's own store, which the
CASE_MANAGER cannot read (PCR-01-003). So the policy travels the way the
reporter's terms do (CP-01-008): the proposing actor sends its full profile
inline as the `actor` of `Create(as_CaseProposal)`, carrying its `embargoPolicy`
(CP-01-010). The CASE_MANAGER reads the default from that profile only, never
fetches it, and keeps it for no other case, so a stale copy can never win a
later shortest-wins. The protocol also permits a profile reference that the
CASE_MANAGER dereferences (CP-01-009); this prototype requires the inline form.
A profile with no policy means no actor default.

**How the prototype implements it (#4027).** The policy is a field of the
actor's profile record (`CoreActor.embargo_policy`, EP-01-001), which the
`PUT /actors/{id}/embargo-policy` endpoint writes; no free-standing
`EmbargoPolicy` record is read by anything. The sending adapter puts the
proposer's stored profile inline as the Create's `actor`
(`create_case_proposal_activity`). The parser refuses a bare-URI actor or a
profile whose id differs from `attributedTo`
(`refuse_malformed_case_proposal_envelope`), and the profile's own validator
refuses a policy naming another actor. The extractor carries the profile on the
event as `proposer_profile`; the use case hands it to the tree as
`owner_profile`, which `BTBridge.execute_with_setup` restores after the run, so a
profile seen on one proposal is never the default for another (CP-01-010). The
store-wide scan the tree used to run (`owner_embargo_policies`) is gone, and the
demo seeder reads the owner's own record from the owner's store instead.

**Stored records from before #4027 are refused, not converted.** The old PUT
kept the policy as a free-standing record and stored its URL in the actor's
`embargo_policy`. `CoreActor` now refuses a string there with a message naming
the pre-#4027 shape and the remedy, so such an actor row reads as absent and the
datalayer's warning says why. There is no silent coercion, because the URL no
longer names anything a reader may follow (EP-01-001). An operator with a
file-backed store from before the change resets it (`docker compose down -v`);
in-memory stores are unaffected. An inbound inline actor carrying a URL-string
`embargoPolicy` is refused at the parse edge on every activity type, for the
same reason.

**The P/X/A refusal arm.** `CaseNotEmbargoEligibleNode` is a *negative*
condition — SUCCESS means "not eligible, stop" — rather than a Success
fallback after the creation sequence. A fallback would turn
any failure in creation into a silent "no embargo"; with the refusal arm first,
creation failures still propagate. The refusal arm itself returns FAILURE only
for "eligible": a missing case or unreadable store *raises*, because FAILURE
there would run creation, which persists an `EmbargoEvent` before anything
re-checks P/X/A (`notes/bt-pitfalls.md` § "A Refusal Arm in a Selector Fails
Toward 'Admit'"). The sender-proposal input
(`sender_proposed_embargo_duration`) is written by the case-proposal use case from
the `EmbargoEvent` the Reporter embedded on the report Offer, which the report
receiver's `CaseProposal` carries whole as `inReplyTo` (#3392, CP-01-008); the
winning sender event keeps its identity with its context rewritten to the case,
and the loser is registered as a pending revision. Keeping the identity means one
URI denotes a report-scoped event on the Reporter's side and a case-scoped one on
the case-actor's side; a replica holding both sees a `context` that changed, which
is the rewrite EP-04-004 prescribes, not a conflict to reconcile. An exact tie
between the sender's terms and the actor default registers no revision — there is
nothing contested.

The revision is registered inside `InitializeDefaultEmbargoNode`, *before* the
case-proposal tree seeds the report receiver and the reporter as SIGNATORY. So a
contested creation leaves the case at `EM.REVISE` with two SIGNATORY participants
who never saw the revision. That is correct: CM-14-005 seeds consent to the
*active* embargo, whose terms are still in force under REVISE, and under ADR-0093
a proposal changes nobody's consent, so the order of registration and seeding no
longer affects the consent record (it once did — the superseded lapse-on-propose
cascade would have lapsed both seeds had the revision been registered after them).

The registration alone was not enough, for two reasons #3863 surfaced (ADR-0113,
EP-04-011): `propose_embargo` appends to `proposed_embargoes` but never to
`pending_embargo_proposal_index`, so the owner's default earliest-expiring
selection (EP-08-002) could not name the revision, and nobody but the CASE_MANAGER
knew it existed. The creation-time revision is now a revision like any other and
follows the relay in `embargo-lifecycle.md` § "Embargo Negotiation Relays Through
the CASE_MANAGER", in two steps that sit at two different places in the tree:

- **Registered, not indexed.** `RegisterLongerProposalAsRevisionNode` mints the
  id the relayed `Invite` will carry but writes no
  `pending_embargo_proposal_index` entry: the bootstrap `Create(VulnerabilityCase)`
  is rendered later in the tree with the case whole, and an entry already naming
  the Invite would make the winner's idempotency guard
  (`EmbargoProposalNotYetRecordedNode`) read the Invite as already answered and
  skip it. It publishes a `CreationTimeRevision` — case, embargo, that id, and whose terms lost
  (`initial_embargo_duration.source`) — on `creation_time_revision`. It writes
  `None` first whenever it ticks, and `BTBridge` scopes the key to one execution
  (as it does `ledger_payload_object_override`, #3101), because the registration
  ticks only on the creation arm: a redelivery that finds the case already
  initialized never reaches it, and would otherwise hand the relay the previous
  execution's revision.
- **Relayed after initialization.** `RelayCreationTimeRevisionNode` sits in the
  case-proposal tree after `CommitNativeLedgerEntriesNode`, not inside
  `InitializeDefaultEmbargoNode`, because no modification may be initiated before
  the initialization sequence is complete (CM-14-007). It subclasses the #3913
  relay emit (`RelayEmbargoInviteToEachNode`): the CASE_MANAGER emits
  `Invite(EmbargoEvent)` as `actor` with the losing party in `attributedTo`
  (CM-24-001/002), under the pre-minted id, and commits it in this tree before
  the outbox write, and only then indexes it (`record_embargo_proposal_index`,
  shared with the received-proposal handler) for the owner's default selection
  (EP-08-002). No proposal activity exists at creation, so the committed relayed
  Invite *is* the revision's proposal entry (EP-04-011).

The loser is the proposer and is not invited: when the reporter's longer terms
lost (the reporter is the report's `attributedTo`), the owner is invited; when the
owner's longer default lost, the reporter is. Both were just seeded SIGNATORY, so
the relay's PEC `INVITE` is not legal for the invitee and changes no consent
(EP-09-004). A tie registers nothing and relays nothing. The relay also sends
nothing when the published revision names another case, when the embargo is no
longer an open proposal, or when an entry for that id is already in the ledger —
the last two read from the store, so a retry after a completed relay sends no
second Invite. A report naming no reporter, a case naming no CASE_OWNER, or a
winner who is not an invitation recipient (CM-10-007) raises: the relay is a MUST,
so a registered revision whose Invite cannot be sent is never a silent SUCCESS,
and the proposal was already accepted and the case announced, so it is the
manager's internal error, never a REFUSED verdict on the sender (ADR-0095). A
reporter that is itself the CASE_OWNER has nobody to invite, so nothing is relayed
or indexed. A failed relay is not retried: the redelivery takes the
already-initialized arm and publishes no revision (#4121); because the index is
written only after sending, it never names an Invite that was not emitted.

The owner may then accept or reject as with any revision (EP-09-005). Each replica
learns the revision from two sources. The `Create(VulnerabilityCase)` snapshot
carries it in `proposed_embargoes`. The index entry comes from elsewhere: the
winner indexes the Invite when it receives and answers it, and the loser — the
proposer, not invited — indexes it when `ApplyEmbargoInviteFromLedgerNode`
replays the committed Invite attributed to it (#4099). That replay writes no index
for any other actor, for the same idempotency reason the registration does not.

The sender's event arrives under the sender's id, and an id is a sender-supplied
value. `persist_creation_time_embargo` (`nodes/embargo.py`) therefore refuses a
stored twin under that id that is not this embargo — about this case, ending when
this one ends — instead of swallowing `VultronAlreadyExistsError` as a replay the
way a freshly minted id allowed; otherwise a colliding id would bind the case to a
foreign embargo while shortest-wins compared the terms the sender stated. On the
receive side a proposal whose `context` is not the proposal's report is read as no
proposal (EP-04-009), the same way an expired one is.

### There was a third implicit duration, and it was the quietest

The 90-day constant and the shared key went first; one unchosen number outlived
them. `EmbargoEvent.end_time` (`vultron/core/models/embargo_event.py`) carried
`default_factory=_45_days_hence`, so **any** `EmbargoEvent` constructed without an
explicit `end_time` silently acquired 45 days — nine times the 5-day ceiling
EP-04-005 sets, and reachable from any construction site that forgot the argument.

It hid differently from the 90-day fallback. That fallback was at least reachable
by reading one function that everyone knew resolved the default. A field default
applies wherever the object is built, with no call site to inspect. EP-04-010
requires the protocol default be the *single* source of the fallback duration.

Resolved in #3404 by making `end_time` **required** rather than by pointing the
default at the protocol default: a model cannot see the actor's configuration, and
ARCH-10-001's fail-fast rule already says a required invariant is asserted at
construction. The two trigger use cases that built an event conditionally already
required `end_time` on their requests, so the only production site that leaned on
the default was the demo's replica seeding, which now resolves its duration the way
`InitializeDefaultEmbargoNode` does. Test builders state `days_from_now_utc(45)`
explicitly — the same window, now visible at every site.

## Initialization Runs Once Per Case — the EM State Is the Evidence

`InitializeDefaultEmbargoNode` is reached from the case-proposal tree on *both*
branches of `ResolveCaseIdSelector`: after `CreateCaseFromProposalNode` on a
fresh case, and after `LoadExistingCaseNode` when a redelivered
`Create(CaseProposal)` reuses a case (CP-05-006). The reuse branch is a
lost-reply recovery: it answers an exact redelivery of the same proposal and lets
a redelivery *finish* a case whose first attempt died between creation and the
`Accept`. "Duplicate" here means the same proposal arriving twice, never a second
report that describes the same vulnerability — that is report management
(RMB-11-002), not case creation. CP-05-006's *statement* still keys the duplicate
on the report ("a proposal for the same report"); the rationale is the lost-reply
recovery, and amending the statement's key is #3977's question.

So the subtree needs a guard that answers "did creation-time initialization
already run on this case?" — `CaseEmbargoAlreadyInitializedNode`, the first arm
of `InitializeDefaultEmbargoNode`. Without it the creation arm re-ran on the
reused case: the default path stored an orphan `EmbargoEvent`, and the contested
path registered the losing candidate as a *second* pending revision, one per
delivery (#3393). The vendor side stopped feeding it duplicates at the same
time: `CheckProposalAlreadySentForReport` treats an *answered* `ReportCaseLink`
(case linked) as "already proposed", not only a pending one, so a re-delivered
Offer no longer re-proposes.

EP-04-012 fixes what the guard's evidence is:

| Evidence | Reads an exited embargo as | Reads a half-built case as |
|---|---|---|
| `case.active_embargo` is set | **uninitialized** (termination clears it) | uninitialized ✓ |
| EM state has left `NONE` | initialized ✓ | uninitialized ✓ |

The reference is wrong in the first column. After `terminate_active_embargo`
the reference is `None` and the state is `EXITED`; a guard keyed on the
reference falls through to the creation arm, which stores a fresh `EmbargoEvent`
*before* `InitializeCreationEmbargoNode` asks the EM machine for a `PROPOSE` it has
no transition for from `EXITED` — an orphan write, a failed tree, and a proposal
that is never answered (#3986). The EM state is right in both columns because
the machine never returns to `NONE` once it has left it and `PROPOSED` is never
persisted at creation (EP-04-002), so "has left `NONE`" is exactly
"initialization has run".

Consequences for the guard arm:

- It reads the state through `ReadEmStateNode`
  (`vultron/core/behaviors/AGENTS.md` § "EM State Reads Must Use
  ReadEmStateNode"), not from the case field.
- It is a refusal arm ahead of a write, so an unreadable case or store *raises*
  (`bt-pitfalls.md` § "A Refusal Arm in a Selector Fails Toward 'Admit'").
  The two rules do not compose for free: `ReadEmStateNode` never raises — it
  returns FAILURE, with the cause in `result_out["error"]` (or nothing at all
  when the datalayer is missing) — and a bare FAILURE as the arm's first child
  falls through the Selector into the creation arm, which is admit. The arm must
  therefore convert the read's FAILURE into a raise itself: after the read, a
  missing `result_out["em_before"]` is an error to raise (carrying
  `result_out["error"]` when present), never a status to return. Only the
  `em_before == EM.NONE` outcome may return FAILURE, because that is the one
  case where falling through to the creation arm is the correct answer.
- Skipping the whole creation arm is what makes the proposal's embargo terms
  irrelevant on a reused case: shortest-wins and the pending-revision
  registration both live inside it. The embargo is the case's, not the
  report's; terms on a redelivered proposal that conflict with the case lose
  to the case.
- The per-node skip in `InitializeCreationEmbargoNode` stays. It is the node
  validating its own transition (CSB-16), not the idempotency guard.

"`PROPOSED` is never persisted at creation" is a property of one write, not of
the order of two. `InitializeCreationEmbargoNode` calls
`EmbargoLifecycle.initialize_creation_embargo`, which applies `PROPOSE` and
`ACCEPT` in memory, attaches the embargo and saves the case once; every check
(P/X/A, the event's record, both transitions) runs before that save. The
creation arm used to call `propose_embargo` and then, in a second node,
`activate_embargo`: a failure between the two saves left the case at
`PROPOSED`, which this guard reads as initialized, so the case never got an
active embargo (#4123). A failure in a node *after* the activation write
(signatory seeding, revision registration), or in the participant consent
writes that follow the case save, still leaves the case past `NONE` with the
rest of the arm undone; that is tracked in #4142.

A rerun at `NONE` must also not store a *second* creation-time event (#4117).
A run can stop after `CreateEmbargoEventNode` stored its event and before EM
leaves `NONE`; the guard rightly admits the rerun, and a minted event with a
fresh random id would leave the first one an orphan. So the minted event's id
is derived from the case (`creation_time_embargo_id`, a uuid5 of the case id),
and a rerun that finds this case's own event under that id overwrites it in
place with the terms the rerun resolved — nothing references it yet, because
the case is still at `NONE`. The node checks that for itself rather than
trusting the guard (CSB-16): it re-stamps only while the case is at `NONE`, has
no active embargo and does not list the id as a proposal. Any other object
under that id, or this case's event once something references it, is refused
by `persist_creation_time_embargo`. The sender branch needs none of this: the
Reporter's event keeps the Reporter's id, and the stored twin is accepted.

Known limit: a redelivery that resolves to a different *branch* than the first
attempt — the first minted a default, the rerun adopts the sender's event —
still leaves the first default unreferenced. An exact redelivery (CP-05-006)
resolves the same way, so this needs a changed proposal for the same report.

A run that stops *after* the PROPOSE trigger and before activation is a
different gap: `propose_embargo` persists `PROPOSED`, which EP-04-002 forbids,
and the guard then reads the case as initialized and never finishes it (#4123).

The report-keyed `LoadExistingCaseNode` itself is suspect for a different
reason — CBT-06-002 expects a second recipient of the same report to get its own
case, and the proposal id is the key both of the reuse branch's jobs actually
need — but that is #3977's question, not this section's.

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
| `propose_embargo(case_id=…)` raises `VultronNotFoundError` when the case does not resolve | `vultron/core/services/embargo_lifecycle/proposals.py` |

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
