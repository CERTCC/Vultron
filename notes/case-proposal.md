---
title: CaseProposal Protocol
status: active
kind: guidance
description: >
  Rules for changing the CaseProposal implementation: who may answer a
  proposal, the admission-gate invariants, the proposer profile on the envelope,
  native case initialization by the CASE_MANAGER, the CaseActor identity and the
  dedicated case-actor container, case creation as one act,
  duplicate-proposal handling, and finding the
  canonical case in exchange demos.
related_specs:
  - specs/case-proposal.yaml
  - specs/multi-actor-demo.yaml
  - specs/configuration.yaml
  - specs/case-management.yaml
  - specs/embargo-policy.yaml
  - specs/semantic-extraction.yaml
  - specs/case-ledger-processing.yaml
  - specs/handler-protocol.yaml
  - specs/object-ids.yaml
related_notes:
  - notes/activitystreams-semantics.md
  - notes/case-communication-model.md
  - notes/bt-integration.md
  - notes/embargo-default-semantics.md
  - notes/bt-pitfalls.md
  - notes/call-out-configuration.md
  - notes/demo-scenario-authoring.md
  - notes/case-ledger-authority.md
  - notes/datalayer-design.md
  - notes/case-bootstrap-trust.md
  - notes/configuration.md
relevant_packages:
  - vultron/wire/as2/vocab/objects
  - vultron/wire/as2/extractor
  - vultron/core/models/events
  - vultron/core/use_cases/received
  - vultron/core/behaviors/case
---

# CaseProposal Protocol

Requirements: `specs/case-proposal.yaml` (CP-01 to CP-09). Decisions: ADR-0023, ADR-0041
(the CASE_MANAGER creates the case natively on accept). The flow and wire shapes are
documented in `docs/reference/messages/case_proposal.md` and
`docs/topics/behavior_logic/use-cases/propose-case.md`; this note holds only the rules
for changing the implementation.

---

## Who May Answer (CP-06-005)

The vendor records the actor it addressed the proposal to on
`VultronReportCaseLink.case_creator_id` and acts on an `Accept` or `Reject` only from
that actor (`SenderIsProposalAddresseeNode`, `NAMED_ACTOR` per ADR-0115). A reply from
anyone else ends `REFUSED` with the link unchanged. Once `case_id` is set, no reply
replaces `case_manager_id`, and a late `Reject` does not set `proposal_rejected`. A
reply for a report never proposed (no link) is `SKIPPED`.

---

## Admission Decision (CP-05-002)

The service decides at one call-out point, `EvaluateCaseProposal` (Evaluator,
`CaseProposalCallOutBundle`). The DETERMINISTIC default admits (BT-23-011). The adapter
injects the bundle in `inbox_port_factories._case_proposal_port_factory`, so the seam
is reachable in production, not only in tests. Three invariants keep a refusal safe;
the general form of each is in [bt-pitfalls](bt-pitfalls.md).

1. **A failed refusal fails the tree.** `RecordProposalDeclineNode` and
   `EmitRejectCaseProposalNode` run in one `RefusalActTransaction`, which rolls both
   back and raises when either fails, so the Selector never reaches the accept arm.
   Everything in the refusal arm ahead of the decision raises rather than returning
   `FAILURE` too, because in a refusal arm either status can hand control to the
   accept branch.
2. **Key every guard on the proposal, never the report.** `report_id` is
   sender-chosen and two proposals may name one report, so a report-keyed guard
   admits an unjudged proposal as a duplicate. `CaseProposalAdmissionRecord`, written
   as the accept flow's first step, is the proposal-keyed evidence.
3. **"Already declined" comes from the record, not the outbox.** `outbox_pop` removes
   a delivered `Reject`, so an outbox check re-emits on every delivery. The record
   commits with its `Reject`, so `CheckDeclineRecordExistsNode` alone answers a
   redelivery, and no state "declined, nothing queued" exists (CLP-07-015).

A refusal has no channel for a reason or cause, so the `Reject` carries no `summary`
and an unreachable backend reads as a permanent decline (#3446).

The decision records name the actor owed the answer `proposer_uri`. A row
carrying the retired `vendor_uri` key is refused
([datalayer-design](datalayer-design.md) § "Retiring a Stored Field").

Guards live in `vultron/core/behaviors/case/nodes/proposal_admission_conditions.py`;
writes and the emit in `proposal_admission_actions.py` (BTND-07-003).

---

## Wire Vocabulary: `as_CaseProposal`

- The `actor` of `Create(as_CaseProposal)` is the proposer's full profile inline,
  carrying its `embargoPolicy` when published (CP-01-010). The protocol also allows a
  reference (CP-01-009); this prototype requires the inline form so case creation
  never fetches. `refuse_malformed_case_proposal_envelope`
  (`vultron/wire/as2/case_proposal_envelope.py`) refuses a bare-URI `actor` or a
  profile whose `id` is not the proposal's `attributed_to`. The extractor hands it to
  core as `proposer_profile`; [embargo-default-semantics](embargo-default-semantics.md)
  covers how the default embargo is read from it.
- `in_reply_to` carries the whole `Offer(VulnerabilityReport)` (CP-01-008) so a
  Reporter's `proposedEmbargo` reaches the case-actor, which never saw the Offer.
- The three case-proposal patterns MUST be registered before more-general patterns
  sharing the outer Activity type (SE-03-002).

---

## CaseActor Native Initialization (ADR-0041)

On accept, `case_proposal_received_tree.py` creates the case, its participants, the
default embargo and the canonical ledger entries natively — no back-fill, no prologue.

- The case's `attributed_to` is the proposer, the CASE_OWNER (CP-09-001); the
  CASE_MANAGER is the `actor` of `Create(VulnerabilityCase)`. The genesis hash follows
  `attributed_to`, so the CASE_MANAGER passes none (CLP-08-002, ADR-0117).
- `Create(VulnerabilityCase)` embeds participants inline, so
  `store_embedded_participants` seeds the receiver's replica without a round-trip.
- The receiver's `receive_report_case_tree.py` creates no case, participants or
  embargo: it writes a pending `VultronReportCaseLink` and sends the proposal. Do not
  re-add the receiver-side creation nodes ADR-0041 removed.

---

## CaseActor Service URL Configuration

The CaseActor identity is `{case_actor_service_url}/actors/case-actor`: one per
container, no per-case slug. Compute it only with `case_actor_identity()`
(`vultron/core/behaviors/case/case_actor_identity.py`), sourced from
`ActorConfig.case_actor_service_url` (CP-08-001 to CP-08-003).

- **Never derive it from `server_base_url`.** That works in single-container demos and
  mis-routes in multi-container topologies, where the receiver proposes to itself.
- **Never add a per-case slug.** It depends on a report the receiver has not seen, so
  nothing can host it before the proposal arrives and the inbox answers 404. Which case
  a message concerns travels in `activity.context` (CP-04-003, BT-10-002).
- **`None` means fail.** `case_actor_identity()` returns `None` when unconfigured;
  callers fail rather than guess a default.
- **Write the record to the CaseActor's own store.** The inbox resolves the actor from
  the store its slug names (ADR-0073); a copy in the sender's store publishes no
  endpoint (CP-04-004).

Docker Compose actors that create cases set
`VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL`; the per-actor field is temporary pending an
actor-ID-to-endpoint resolver (#1189).

### The Dedicated Case-Actor Container (#1876)

In `docker/docker-compose-multi-actor.yml` every container, `case-actor`
included, sets `VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL=http://case-actor:7999/api/v2`
(CP-08-003, CP-08-008, DEMOMA-06-004), so every proposal goes to the one
identity `http://case-actor:7999/api/v2/actors/case-actor`.

- **The demo runner seeds it.** Reset clears every node and no container seeds
  itself, so `reset_containers` (`vultron/demo/helpers/seeding.py`) re-seeds the
  identity via `seed_case_actor_identity` when given the `case_actor_client`;
  without it every proposal answers 404.
- **Canonical records live in the case-actor container.** Its store holds the
  case, ledger and participant records, with the CaseActor as the `CASE_MANAGER`
  participant; each participant container holds a replica plus an address-book
  copy of the CaseActor (`EnsureCaseActorHostedNode`), a plain `VultronService`
  whose inbox and outbox derive from its id (ARCH-12-006).
- **Read the CaseActor's state through its own client**, never a participant's
  replica: some participant RM transitions are applied without a ledger entry,
  so a replica can lag them indefinitely (DEMOMA-06-005).
- **Facts about the proposer travel on the proposal** (ADR-0133, CP-01-011):
  the receiver copies its roles onto `proposerCaseRoles`, the CaseActor seats it
  with those plus `CASE_OWNER`, and the parse edge refuses a `CASE_MANAGER`
  claim (CP-01-012). No CaseActor config or store holds a proposer's facts.
- **Do not build on the singleton as permanent.** One pre-provisioned CaseActor
  for every case is a stepping stone to CaseActor Spawning (#1092).

---

## Case Creation Is One Act (CP-05-005, CLP-07-015)

The accept arm, from the admission record to the creation-time revision relay, is
one `ActTransaction` (`CreateCaseFromProposalAct`). Rules:

- **Keep every write of the creation inside the act**, the `Accept`, the `Create`,
  the ledger commits and the relay included. A failure then rolls back the case and
  everything queued, so no `Accept` is sent without its `Create` and the inbox's
  redelivery processes the proposal fresh. Do not add a stored marker or a startup
  runner to finish a creation later: the durable outbox retries delivery (OX-13).
- **Derive the `Create` id** from the proposal (`create_case_activity_id()` in
  `proposal_announcement.py`), never mint it, so a redelivery names the activity its
  first delivery queued (OX-06-002, #4146). `announced_case_id()` checks the stored
  activity is a `Create` for *this* case, because the proposal id is sender-chosen.
- **The relay reads what to relay from this act**, not from the store:
  `RelayCreationTimeRevisionNode` acts only when this execution's
  `InitializeCreationEmbargoNode` registered a revision, and reads that revision from
  the case. See [embargo-default-semantics](embargo-default-semantics.md).

Rows of the retired marker types are refused at load like any deleted stored type
([datalayer-design](datalayer-design.md) § "Retiring a Stored Field").

---

## Duplicate-Proposal Handling (CP-05-006)

`create_case_proposal_received_tree` is a four-arm Selector, in order:
already-declined answer, closed-case decline, admission decision, accept flow.

- **Same proposal id** (CP-05-006): re-send the stored `Accept` unchanged under its
  proposal-derived id, unless still pending in the outbox; create no second case.
  "Duplicate" means only this — an exact redelivery. A second report about the same
  vulnerability is a report-management question (RMB-11-002). The case is found
  through the stored `Accept`'s `result`, not only by owner: after an ownership
  transfer the former owner owns nothing, and an owner-only lookup made a second
  case (#4650). Gate that `Accept` scan on whether the admission record pre-dated
  this delivery (`RecordProposalAdmissionNode`'s `admission_record_was_prior`), not
  on the report: the report id is sender-chosen, so a redelivery may name a report
  with no case.
- **Same proposal id, another sender** (CP-05-010): the proposal id is
  sender-chosen, so the use case declares `SenderRule.before_case(AUTHOR)` and the
  factory composes `SenderIsProposalAuthorNode` ahead of every arm. A proposal id
  whose admission record, decline record or stored proposal (`attributed_to`) names
  another proposer is `REFUSED` before any proposal-keyed record is read or written
  (HP-01-008, #4719); CP-05-010 counts all three as recording the proposal. Add any
  new proposal-keyed record that names the
  proposer to that node. `LoadExistingCaseNode`'s `accepted_for_proposer_only`
  (#4650) is not a second defense: it reads the admission record, which the accept
  arm writes for the current sender when none exists.
- **One proposer identity** (CP-05-006, CP-05-010): the guard compares the sender with
  `same_actor_id`, so every later proposer comparison must agree with it. The tree
  factory normalises `proposer_uri` with `normalise_actor_id`, and `report_author_id`
  does the same for the reporter, so the records, participant keys and ledger
  snapshots the tree writes hold one spelling. Compare an id written elsewhere (the
  inline profile, a proposal-keyed record the guard also reads) with
  `same_actor_id`, and look up `actor_participant_index` with
  `participant_id_for_actor`, never `==` or `in`: a trailing-slash redelivery
  otherwise re-runs native initialization (#4772). The event's sender id is
  already normalised by the extractor, and the event refuses one with a trailing
  slash (OID-01-007), but the activity snapshot keeps the sender's spelling. A
  store written in the slash spelling before #4772 is unsupported: keep the
  tree's existing tolerant checks, but add none for it.
- **New proposal id, same report** (CP-05-008): a new request, adjudicated and
  answered with its own `Accept` or `Reject`, never the earlier stored `Accept`.
  For a new proposal id, `LoadExistingCaseNode` reuses the case only when its
  `attributed_to` is the proposer; another proposer gets a case of its own
  (CBT-06-002), because the report id is sender-chosen. `find_case_by_report_id` is
  only the fast path; on another proposer's case the node scans for the proposer's
  own.
- **Fully closed case** (CP-05-006, CP-05-008): a proposal that resolves to a case
  whose ledger holds the CASE_MANAGER's own `RM.CLOSED` status entry gets
  `Reject(CaseProposal)`, and nothing is
  written for the case (CM-23-013). The factory's post-close guard cannot see it,
  because the proposal names a report, not a case. `CheckProposalCaseFullyClosedNode`
  and `LoadExistingCaseNode` both resolve the case with `proposal_case_ids`
  (`proposal_case_lookup.py`): the proposer's own case for the report, then the case
  the proposal's stored `Accept` names. Add any new way to find a case there, so
  the closed-case check and the accept arm cannot resolve different cases.
- The `Accept`'s `result` always names the case the proposal produced or reused, so
  the requester correlates it without a second `Create`, which is not sent again.
  `CheckCaseAlreadyAnnouncedNode` skips the `Create` step, and
  `CommitNativeLedgerEntriesNode` skips entries already recorded; without that skip
  the reused entries fan out again.
- **Every native-initialization node must be a no-op on a case that already has what it
  creates**, embargo included, whatever its EM state. A node that names the proposer
  as owner also skips a proposer that is not the case's `attributed_to`: a former
  owner's redelivery must not make it CASE_OWNER again (CM-21-001, #4650).
  `CaseEmbargoAlreadyInitializedNode` is the embargo subtree's first arm and keys on EM
  ≠ `NONE`, not the active-embargo reference, which termination clears (EP-04-012,
  #3393).
- The receiver does not re-propose: `CheckProposalAlreadySentForReport` treats a
  linked `ReportCaseLink` as already proposed.

---

## Exchange Demo: Discovering the Canonical Case

After `validate-report`, the CaseActor creates the canonical case on its own. Find it
with `wait_for_initialized_case(client, report.id_)`
(`vultron/demo/helpers/polling.py`), which matches on the report
(`case_references_report`): the CaseActor's store holds many cases, so "first case
with participants" can return another report's case.

Never call `create_case_activity` to make a receiver-local case. It has no
`ReportCaseLink`, gets no participants, and is distinct from the canonical case, and
none of that raises. In single-backend tests the CaseActor's `Create` delivery is
dropped, but the case is still in its store (#1994).
