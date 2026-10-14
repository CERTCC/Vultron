---
source: NOTES-embargo-default-semantics--how-the-conflation-hid-a-defect
timestamp: '2026-10-12T19:33:14.124558+00:00'
title: 'How the conflation hid a defect (resolved, #3390)'
type: note
---

**Archived:** 2026-10-12
**Reason:** defect story and where-it-lives table for delivered work (#3390, #4027, #3392, #3863, #4121); live rules restated as short guidance items
**Superseded by:** vultron/core/services/embargo_duration.py; EP-04-003..012, CP-01-010, EP-04-011; notes/embargo-default-semantics.md

---

## How the conflation hid a defect (resolved, #3390)

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
case-proposal tree seeds the report receiver and the reporter as signatories. So a
contested creation leaves the case at `EM.REVISE` with two signatory participants
who never saw the revision. That is correct: CM-14-005 seeds consent to the
*active* embargo, whose terms are still in force under REVISE, and under ADR-0093
a proposal changes nobody's consent, so the order of registration and seeding no
longer affects the consent record (it once did — the superseded lapse-on-propose
cascade would have lapsed both seeds had the revision been registered after them).

The registration alone was not enough, for two reasons #3863 surfaced (ADR-0113,
EP-04-011): `propose_embargo` added an open proposal but never wrote
`pending_embargo_proposal_index`, so the owner's default earliest-expiring
selection (EP-08-002) could not name the revision, and nobody but the CASE_MANAGER
knew it existed. The creation-time revision is now a revision like any other and
follows the relay in `embargo-lifecycle.md` § "Embargo Negotiation Relays Through
the CASE_MANAGER", in two steps that sit at two different places in the tree:

- **Owed and registered in one commit, not indexed.**
  `ResolveCreationTimeRevisionNode` selects the longer proposal before anything
  is written and publishes it as `creation_time_revision_candidate`;
  `InitializeCreationEmbargoNode` registers it in the activation's commit and, in
  that same `save_many`, writes a `PendingCreationTimeRevisionRelay` record keyed
  on the case — the freshly minted id the relayed `Invite` will carry, the report
  the reporter is resolved from, whose terms lost
  (`initial_embargo_duration.source`), and the CASE_MANAGER that owes the relay.
  It is the `PendingCreateCaseActivity` shape (CP-05-005), committed with the
  effect it guards rather than ahead of it: a failure leaves neither, never a
  registered revision with nothing to retry (#4156), and the once-per-case guard
  lets a redelivery finish both (#4142). A contest whose case names no report
  fails before the commit. Writing a record initiates no modification, so it does
  not run ahead of CM-14-007's sequence. `BTBridge` scopes the candidate key to
  one execution (as it does `ledger_payload_object_override`, #3101), because the
  selection ticks only on the creation arm. Nothing writes a
  `pending_embargo_proposal_index` entry: the bootstrap
  `Create(VulnerabilityCase)` is rendered later in the tree with the case whole,
  and an entry already naming the Invite would make the winner's idempotency guard
  (`EmbargoProposalNotYetRecordedNode`) read the Invite as already answered and
  skip it.
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
  Invite *is* the revision's proposal entry (EP-04-011). It reads what to relay
  from the marker, never from the blackboard, and deletes the marker when done.

The loser is the proposer and is not invited: when the reporter's longer terms
lost (the reporter is the report's `attributedTo`), the owner is invited; when the
owner's longer default lost, the reporter is. Proposing is consenting
(MSM-07-005), so the proposer's record, not the executing actor's, gains the
revision id: on the CASE_MANAGER's creation path the executor is neither party
(#4152). `creation_revision_parties` (`nodes/embargo_revision.py`) resolves both
parties from the case owner and the report's author, for the registration and the
relay alike. Both were just seeded as signatories, so
the relay's PEC `INVITE` is not legal for the invitee and changes no consent
(EP-09-004). A tie registers nothing and relays nothing. A report naming no
reporter, a case naming no CASE_OWNER, or a winner who is not an invitation recipient (CM-10-007) raises: the relay is a MUST,
so a registered revision whose Invite cannot be sent is never a silent SUCCESS,
and the proposal was already accepted and the case announced, so it is the
manager's internal error, never a REFUSED verdict on the sender (ADR-0095). A
reporter that is itself the CASE_OWNER has nobody to invite, so nothing is relayed
or indexed, and the marker is deleted.

**A failed relay is retried, from the marker (#4121).** Initialization runs once
per case (EP-04-012), so a redelivered proposal takes the already-initialized arm
and registers nothing; without a durable record the revision would stay open with
an Invite nobody sent and nobody could answer. Once the marker is written, a
failure after it — a missing factory, an unresolvable party, a fault mid-relay, a
crash — keeps it. Two runs find it. One is a later delivery of a proposal for the
case, whose accept arm reruns the creation sequence and so reaches the relay
again; that path is closed while a `PendingCreateCaseActivity` marker exists,
because `CheckMarkerExistsNode` short-circuits the redelivery. The other is the
startup runner `retry_pending_creation_time_revision_relays` in
`vultron/adapters/driving/fastapi/pending_retry.py`, beside the
`Create(VulnerabilityCase)` retry. The runner wraps the relay node in
`create_case_manager_gated_tree` (BT-17-001), so an actor that no longer holds
CASE_MANAGER relays nothing and the marker is kept for the role holder. A tree
runs against the store of the actor it executes as (BT-05-005, DL-07-004), so the
runner skips, at WARNING, a marker whose `case_actor_id` is not the store's actor
rather than relay as one actor against another's store; a marker held by a former
CASE_MANAGER stays in that actor's store.

The relay node classifies the marker before acting:

- **Not yet.** With no genesis `create_case` entry in the case's ledger, the
  creation sequence is not complete (CM-14-007, CM-14-011): nothing is sent and
  the marker is kept. Only a run outside the case tree can see this — inside it,
  `CommitNativeLedgerEntriesNode` has already committed the genesis entry.
- **Closed.** The embargo is no longer an open proposal: nothing is sent and the
  marker is deleted.
- **Committed.** An entry for the pre-minted Invite id is already in the ledger:
  the relay committed and then failed. The node re-applies PEC `INVITE` where
  legal (EP-09-004), writes the index, and deletes the marker. Whether it queues
  the Invite again is decided by the marker's `invite_queued` receipt, which the
  relay saves right after `outbox_append`: the outbox cannot answer it, because
  `outbox_pop` empties the outbox on delivery and so a delivered Invite looks like
  a lost one. With no receipt the outbox write never happened, so the node
  appends the committed id — the sealed body stored under it is what is
  delivered — and records the receipt (#4156). A crash between the append and the
  receipt write sends the same Invite, under the same id, twice: at-least-once,
  which the winner's idempotency guard absorbs.
- **Send.** Otherwise it sends the Invite under the id the marker carries,
  indexes it, and deletes the marker.

When the `Create` runner recovered the announcement but the native entries were
never committed, nothing at startup commits them, so the relay waits for a
redelivered proposal; the runner logs that wait at WARNING on every start, so it
is never silent. Because the index is written only after the Invite is committed,
it never names an Invite that was not emitted.

The owner may then accept or reject as with any revision (EP-09-005). Each replica
learns the revision from two sources. The `Create(VulnerabilityCase)` snapshot
carries it as a `PROPOSED` entry of its `embargoRegister` (ADR-0122). The index entry comes from elsewhere: the
winner indexes the Invite when it receives and answers it, and the loser — the
proposer, not invited — indexes it when `ApplyEmbargoInviteFromLedgerNode`
replays the committed Invite attributed to it (#4099). That replay writes no index
for any other actor, for the same idempotency reason the registration does not.

The sender's event arrives under the sender's id, and an id is a sender-supplied
value. `persist_creation_time_embargo` (`embargo_lifecycle/creation.py`) refuses a
stored twin under that id that is not this embargo — about this case, ending when
this one ends — instead of swallowing `VultronAlreadyExistsError` as a replay the
way a freshly minted id allowed; otherwise a colliding id would bind the case to a
foreign embargo while shortest-wins compared the terms the sender stated. On the
receive side a proposal whose `context` is not the proposal's report is read as no
proposal (EP-04-009), the same way an expired one is.
