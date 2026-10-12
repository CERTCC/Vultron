---
title: Embargo Default Semantics — Implementation Notes
status: active
kind: guidance
description: >
  Rules for the creation-time embargo (EP-04): the published-default /
  tacit-acceptance path; actor default versus protocol default and why only
  the actor default competes under shortest-wins; whose policy the actor
  default is and how it reaches creation (CP-01-010); the creation-time
  revision, its durable relay marker and retry (EP-04-011); why
  initialization runs once per case keyed on EM state and commits in one
  write (EP-04-012); and why an RSVP deadline may not outlive its embargo
  (EP-07-006).
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
  - vultron/config
  - vultron/core/behaviors/case
  - vultron/core/behaviors/embargo
  - vultron/core/models
  - vultron/core/services
  - vultron/core/use_cases/triggers
  - vultron/wire/as2/extractor
  - vultron/wire/as2/factories
  - vultron/adapters/driving/fastapi
---

# Embargo Default Semantics — Implementation Notes

Rules for the `specs/embargo-policy.yaml` EP-04 creation-time embargo. The
protocol source is `docs/topics/process_models/em/defaults.md`.

---

## The Published-Default / Tacit-Acceptance Model

The receiver's published default embargo is a standing proposal; a reporter
who submits without stating terms tacitly accepts it, so the case goes straight
to `EM.ACTIVE` with no `EP`/`EA` exchange (EP-04-001). The intermediate
`PROPOSED` is never persisted or observable (EP-04-002).

| Scenario | EM outcome |
|---|---|
| Receiver has actor default, reporter states no terms | `EM.ACTIVE` at the default (EP-04-001) |
| Reporter's terms shorter than the default | Reporter's → `ACTIVE`; default → `REVISE` (EP-04-003) |
| Reporter's terms longer than the default | Default → `ACTIVE`; reporter's → `REVISE` (EP-04-003) |
| Neither party has terms | `ACTIVE` at the protocol default (EP-04-005, ADR-0096) |
| Neither has terms and P/X/A is set | `EM.NONE` (EP-04-008) |

- **A demo that reaches `EM.ACTIVE` with no proposal activity is correct**, not
  missing a step. A demo of the negotiated path (terms stated on the report
  Offer, EP-04-004) MUST say so; `report-with-embargo` does.
- **EP-04-003 is the two-party case of EP-08-001.** Use the one comparator,
  `earliest_ending` (`vultron/core/services/embargo_ordering.py`), for both
  shortest-wins and earliest-expiring selection; never grow a second one. There
  is no multi-candidate poll (ADR-0100): send one `Invite` per candidate.
- **Reporter terms ride the report Offer.** See § "Reporter Embargo Proposal
  Mechanism (EP-04-004)".

## Two Kinds of Default — Do Not Conflate Them

| Term | What it is | Competes under shortest-wins |
|---|---|---|
| **Actor default** | The `embargo_policy` on the CASE_OWNER's actor profile | **Yes** |
| **Protocol default** | `ActorConfig.protocol_default_embargo_duration`, used only when no candidate exists | **No** |

- **The protocol default is the value of an empty candidate set, never a
  candidate** (EP-04-006): a short default that competed would cap every
  embargo at its own length. It is **not a minimum** either (EP-04-007): agreed
  12-hour terms give 12 hours. `resolve_initial_embargo_duration()` owns this.
- **Keep the three durations under distinct names** (EP-04-010):
  `actor_default_embargo_duration`, `protocol_default_embargo_duration`, and the
  resolved `initial_embargo_duration` (duration plus source). A shared key
  cannot tell "published 90 days" from "published nothing" (#3390).
- **No model field may default a duration.** `EmbargoEvent.end_time` is
  required; a field default applies at every construction site with no call
  site to inspect, so the protocol default would stop being the single source
  (EP-04-010, #3404).
- **The actor default is the CASE_OWNER's policy and no one else's.** The
  CASE_OWNER is the actor the report was offered to, named by
  `case.attributed_to` on every creation path (CM-02-008). The CASE_MANAGER,
  which runs the creation tree, contributes no terms; `ResolveEmbargoDurationNode`
  fails unless the profile's id is `case.attributed_to`.
- **The policy travels inline, never fetched or kept.** The CASE_MANAGER cannot
  read the owner's store (PCR-01-003), so the owner's full profile is the `actor`
  of `Create(as_CaseProposal)` (CP-01-010). It reaches the tree as
  `owner_profile`, which `BTBridge` restores after the run, so one proposal's
  profile is never another's default. A profile with no policy means no actor
  default. The parser refuses a bare-URI actor or one that differs from
  `attributedTo`, and a URL-string `embargoPolicy` on any inbound actor.
- **The policy is a field of the profile** (`CoreActor.embargo_policy`,
  EP-01-001). A stored actor whose `embargo_policy` is a URL string (the old
  free-standing record) is refused, not converted: the URL names nothing a
  reader may follow, and the remedy is a store reset (#4027).
- **The P/X/A refusal arm is a negative condition.** `CaseNotEmbargoEligibleNode`
  returns SUCCESS for "not eligible, stop" and FAILURE only for "eligible"; an
  unreadable case or store raises, because FAILURE would run creation
  (`notes/bt-pitfalls.md` § "A Refusal Arm in a Selector Fails Toward 'Admit'").
- **The sender's event keeps its id, with `context` rewritten to the case**
  (EP-04-004). An id is sender-supplied, so `persist_creation_time_embargo`
  refuses a stored twin that is not the same embargo (same case, same
  `end_time`) rather than treating it as a replay. A proposal whose `context` is
  not its report is read as no proposal (EP-04-009). An exact tie registers no
  revision.

## The Creation-Time Revision (EP-04-011)

The losing terms are a revision like any other and follow the relay in
`embargo-lifecycle.md` § "Embargo Negotiation Relays Through the CASE_MANAGER".

- **Registered and owed in one commit, not indexed.**
  `InitializeCreationEmbargoNode` registers the revision in the activation's
  `save_many` together with a `PendingCreationTimeRevisionRelay` marker (the
  pre-minted Invite id, the report, the losing source, the owing
  CASE_MANAGER). A failure leaves neither, never a revision with nothing to
  retry (#4156). Nothing writes `pending_embargo_proposal_index` here: an entry
  naming the Invite would make the winner's `EmbargoProposalNotYetRecordedNode`
  skip it as already answered.
- **Relayed after initialization.** `RelayCreationTimeRevisionNode` runs after
  `CommitNativeLedgerEntriesNode`, because no modification may start before the
  creation sequence completes (CM-14-007). It commits the relayed Invite before
  the outbox write and only then indexes it, so the index never names an Invite
  that was not emitted. It reads what to relay from the marker, never the
  blackboard.
- **The loser is the proposer and is not invited**; proposing is consenting
  (MSM-07-005), so the proposer's row, not the executing actor's, gains the
  revision (`creation_revision_parties`). A reporter that is the CASE_OWNER has
  nobody to invite: nothing is relayed. A missing reporter, a missing
  CASE_OWNER, or a winner who is not an invitation recipient (CM-10-007) raises
  as the manager's internal error, never a REFUSED verdict (ADR-0095).
- **A failed relay is retried from the marker** (#4121), by a redelivered
  proposal or by the startup runner `retry_pending_creation_time_revision_relays`
  (`vultron/adapters/driving/fastapi/pending_retry.py`). The runner is
  CASE_MANAGER-gated (BT-17-001) and skips, at WARNING, a marker whose
  `case_actor_id` is not the store's actor (DL-07-004). The node classifies the
  marker first: no genesis entry yet → keep it; proposal closed → delete it;
  Invite already committed → re-apply, index, and queue again only if the
  `invite_queued` receipt is missing (the outbox empties on delivery, so it
  cannot answer); otherwise send.
- **Replicas learn the revision from two places**: the `Create(VulnerabilityCase)`
  snapshot carries it as a `PROPOSED` register entry (ADR-0122), and only the
  proposer indexes it, when `ApplyEmbargoInviteFromLedgerNode` replays the
  Invite attributed to it (#4099).

## Initialization Runs Once Per Case — the EM State Is the Evidence

`InitializeDefaultEmbargoNode` is reached on both branches of
`ResolveCaseIdSelector`, including a redelivered `Create(CaseProposal)` that
reuses a case (CP-05-006). Its first arm, `CaseEmbargoAlreadyInitializedNode`,
skips creation when EM has left `NONE` (EP-04-012).

- **Key on EM state, never on `case.active_embargo`.** Termination clears the
  reference but leaves EM `EXITED`, so a reference-keyed guard re-runs creation
  on an exited case (#3986). EM never returns to `NONE`, and `PROPOSED` is never
  persisted at creation, so "left `NONE`" is exactly "initialized".
- **The guard arm must turn a failed read into a raise.** It reads through
  `ReadEmStateNode`, which returns FAILURE rather than raising; a bare FAILURE
  falls through the Selector into creation. Only `em_before == EM.NONE` may
  return FAILURE.
- **Everything creation writes commits in one `save_many`.**
  `initialize_creation_embargo` applies `PROPOSE` and `ACTIVATE` in memory, then
  writes the embargo event, consent rows, the owner's signatory seed
  (CM-14-003) and any revision through `StagedCasePersistence`, which answers
  reads from what it staged and refuses queries it cannot answer faithfully. A
  failure leaves the case at `NONE`, which the guard admits for a rerun
  (#4142). `CreateEmbargoEventNode` only builds the event, so an aborted run
  leaves no orphan to clean up.
- **The minted default's id is a uuid5 of the case id**
  (`creation_time_embargo_id`), so a case always names the same default.
- **Terms on a redelivered proposal lose to the case**: skipping the creation
  arm skips shortest-wins and the revision registration with it.
- The per-node skip in `InitializeCreationEmbargoNode` is the node validating
  its own transition (CSB-16), not the idempotency guard; keep both.

## Reporter Embargo Proposal Mechanism (EP-04-004)

A reporter states terms by embedding a proposed `EmbargoEvent` in the
`Offer(VulnerabilityReport)`; its `context` is the report until case creation
rewrites it to the case (ADR-0096, EP-04-009). **Do not revive the proto-case**
(reporter-owned case, then ownership transfer): ADR-0041 and ADR-0089 rejected
it.

## An RSVP Deadline May Not Outlive Its Embargo

An RSVP deadline is clamped **down** to the embargo's `end_time` (EP-07-006,
CM-28-011), so the minimum window is "72 hours, or the remaining embargo,
whichever is shorter" (EP-07-002). Otherwise a 24-hour embargo would carry a
7-day pocket veto that fires long after the embargo ended.

- **One function computes it for both sides**: `resolve_rsvp_deadline()`
  (`vultron/core/models/rsvp_deadline.py`), measured from the Invite's
  `published`. The sender (`em_propose_embargo_activity`) refuses a deadline the
  function would move; the receiver (`extract_intent`) applies the moved value,
  logs each clamp at INFO (EP-07-005), and never rejects the invitation
  (EP-07-004).
- The protocol-default floor equals the configured minimum RSVP window on
  purpose, so the clamp never fires on the protocol-default path; a shorter
  agreed embargo still needs the computed minimum.
