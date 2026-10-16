---
stakeholder_type: [platform-developer, project-contributor]
level: 400
description: >
  Case lifecycle, participant roster, and ownership transfer activities.
---

# Case Management Messages

These messages drive the lifecycle of a `VulnerabilityCase`, the record of one Coordinated Vulnerability Disclosure (CVD) case, and its roster of participants.
They have no formal-protocol shorthand — the 28-symbol formal message set addresses state-machine transitions, not the case-infrastructure layer that supports them (see [ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)).

All messages on this page operate on a case that already exists. For the
pre-existence bootstrap (vendor → case-actor service) see
[Case Proposal](case_proposal.md). For the ledger mechanism that replicates
these activities to all participants see
[Ledger Replication](ledger_replication.md).

Two authorities appear below, and they are distinct roles rather than one actor.
The **Case Owner** decides for the case: who is admitted, which roles they hold, and whether an ownership transfer is offered.
The **CASE_MANAGER** is the case's single-writer authority: it mints and updates the `VulnerabilityCase` object, records every case-scoped message in the ledger, and delivers case snapshots to participants (spec [§5.4.1 Single-Writer Authority](../vultron-spec/layers.md#541-single-writer-authority), [ADR-0088](../../adr/0088-consolidate-case-authority-determination.md)).
The CASE_MANAGER acts on the Case Owner's behalf; the two roles are often held by the same actor but need not be.
The 300-level introduction is [The Case Manager and the Case Ledger](../../topics/case_lifecycle/case_manager_and_ledger.md).

## Occasions

{% include-markdown "./_occasions/lookup-case_management.md" %}

{% include-markdown "./_occasions/sections/create-case.md" %}

- **Recipients:** the CASE_MANAGER sends the completed case to the report receiver (the Case Owner) only ([CBT-01-010](../specs/protocol.md#cbt-01-010), [CM-22-001](../specs/protocol.md#cm-22-001), [CM-22-002](../specs/protocol.md#cm-22-002)).
  The report receiver then sends the report submitter a `Create(VulnerabilityCase)` as itself, which names the CASE_MANAGER and is the trust bootstrap (spec [§4.5 Trust and Bootstrap Semantics](../vultron-spec/layers.md#45-trust-and-bootstrap-semantics); [CBT-01-001](../specs/protocol.md#cbt-01-001), [ADR-0132](../../adr/0132-the-report-receiver-introduces-the-case-manager-to-the-reporter.md)).
- **Who is named where:** the `actor` of the `Create` is the CASE_MANAGER that mints the case, and the case's `attributedTo` is the Case Owner ([CP-09-001](../specs/protocol.md#cp-09-001), [CM-02-008](../specs/protocol.md#cm-02-008)).
  The two coincide when the Case Owner creates its own case, as in the example above.
  When a case-actor service creates the case from a [Case Proposal](case_proposal.md), the service is the `actor` and `attributedTo` names the proposing actor, never the service itself.
  Every owner check reads `attributedTo`, and an ownership transfer rewrites it ([CM-21-002](../specs/protocol.md#cm-21-002)).
- **Triggering transition:** none — object construction precedes protocol state.
- **Example artifact:** [create_case.json](../examples/create_case.json).

{% include-markdown "./_occasions/sections/add-report-to-case.md" %}

- **Triggering transition:** none — a report can be added at any Report Management (RM) state.
- **Who may send:** the CASE_MANAGER accepts it only from the Case Owner, and a participant replica accepts it only from the CASE_MANAGER.
  Any other sender is refused and the report is not attached.
- **Example artifact:** [add_report_to_case.json](../examples/add_report_to_case.json).

{% include-markdown "./_occasions/sections/offer-case-participant-role.md" %}

- **Object type:** the object type alone identifies the activity as a role offer rather than an ownership-transfer offer (ADR-0039).
  Roles are granted through the case's authority chain ([§11.1 Role Assignment](../vultron-spec/interactions.md#111-role-assignment-n)).
- **Target:** the Actor receiving the role; the `context` is the case.
- **Triggering transition:** none — roster action, not a state-machine event.
- **Example artifact:** [offer_case_participant_role.json](../examples/offer_case_participant_role.json).

The [`CaseParticipantRole`](../activitypub/objects.md#caseparticipantrole) object carries the role.
This offer is distinct from `Offer(CaseParticipant)`, which forwards an actor recommendation to the Case Owner and is covered under [Offer case participant](general.md#offer-case-participant).

{% include-markdown "./_occasions/sections/accept-case-participant-role.md" %}

- **Triggering transition:** none — roster action.
- **Example artifact:** [accept_case_participant_role.json](../examples/accept_case_participant_role.json).

{% include-markdown "./_occasions/sections/reject-case-participant-role.md" %}

- **Triggering transition:** none — roster action.
- **Example artifact:** [reject_case_participant_role.json](../examples/reject_case_participant_role.json).

The dedicated object type is preferred over a `target`-field discriminator ([SE-08-003](../specs/protocol.md#se-08-003)), and the earlier wire format `Offer(VulnerabilityCase, target=CaseParticipant)` for offering a role has been removed.

{% include-markdown "./_occasions/sections/offer-case-ownership-transfer.md" %}

- **Routing:** the offer is routed through the CASE_MANAGER, which records it in the ledger ([§11.3 Case Ownership Transfer](../vultron-spec/interactions.md#113-case-ownership-transfer-n)); see [Case Ownership Transfer](../../topics/case_lifecycle/ownership_transfer.md).
- **Target:** the recipient's URI.
- **Triggering transition:** none — ownership transfer is a roster operation.
- **Example artifact:** [offer_case_ownership_transfer.json](../examples/offer_case_ownership_transfer.json).

{% include-markdown "./_occasions/sections/accept-case-ownership-transfer.md" %}

- **Triggering transition:** none — roster operation.
- **Example artifact:** [accept_case_ownership_transfer.json](../examples/accept_case_ownership_transfer.json).

{% include-markdown "./_occasions/sections/reject-case-ownership-transfer.md" %}

- **Routing:** the `Reject` is addressed to the CASE_MANAGER, not to the actor that made the offer ([CM-21-010](../specs/protocol.md#cm-21-010)).
  The CASE_MANAGER acts on it only when it comes from the proposed owner of an open offer it recorded ([CM-21-013](../specs/protocol.md#cm-21-013)).
  It records the `Reject` in the ledger and sends the entry to every participant, which closes the offer ([CM-21-012](../specs/protocol.md#cm-21-012)).
- **Trigger:** the recipient sends it with `POST /actors/{actor_id}/trigger/reject-case-ownership-transfer`, whose body names the `offer_id` it declines ([TRIG-11-005](../specs/protocol.md#trig-11-005), [Trigger API Reference](../trigger-api.md#actor-participation)).
- **Triggering transition:** none — roster operation.
- **Example artifact:** [reject_case_ownership_transfer.json](../examples/reject_case_ownership_transfer.json).

{% include-markdown "./_occasions/sections/withdraw-case-ownership-transfer.md" %}

- **Routing:** the withdrawal is addressed to the CASE_MANAGER ([CM-21-015](../specs/protocol.md#cm-21-015)).
  The CASE_MANAGER acts on it only when it comes from the Case Owner that made an open offer it recorded.
  It records the withdrawal in the ledger and sends the entry to every participant, which closes the offer: the proposed owner can no longer accept it, and the case may be offered again ([CM-21-014](../specs/protocol.md#cm-21-014)).
  A withdrawal from anyone else, or of an offer already answered or withdrawn, is refused with nothing recorded and nothing sent.
- **Trigger:** the Case Owner sends it with `POST /actors/{actor_id}/trigger/withdraw-case-ownership-transfer`, whose body names the `offer_id` it withdraws ([TRIG-11-006](../specs/protocol.md#trig-11-006), [Trigger API Reference](../trigger-api.md#actor-participation)).
- **Triggering transition:** none — roster operation.
- **Example artifact:** [undo_case_ownership_transfer.json](../examples/undo_case_ownership_transfer.json).

{% include-markdown "./_occasions/sections/invite-actor-to-case.md" %}

- **Who decides:** the Case Owner decides whom to invite; a participant that wants a third party brought in sends a recommendation instead ([Suggest actor to case](general.md#suggest-actor-to-case)).
  See [§11.2 Invitation and Acceptance](../vultron-spec/interactions.md#112-invitation-and-acceptance-n).
- **Triggering transition:** none — roster action.
- **Object and target:** the `object` is the actor being invited, and the `target` is the case stub, of type `VulnerabilityCaseStub`.
  The stub carries the case identifier in its `caseId` and a required `summary` field: the owner-chosen description the invitee reads before deciding whether to accept ([CM-11-013](../specs/protocol.md#cm-11-013), [CM-17-010](../specs/protocol.md#cm-17-010), [MV-10-001](../specs/protocol.md#mv-10-001)).
  The factory raises `VultronActivityConstructionError` when `VulnerabilityCase.stub_summary` is not set, and the receiver refuses a stub with an absent or blank `summary`.
  The Invite names at least one CVD role for the invitee, and the CASE_MANAGER refuses to send one with an empty role list ([CM-11-019](../specs/protocol.md#cm-11-019)).
  The Invite carries its reply deadline in `endTime`, which the CASE_MANAGER sets the way it sets an embargo Invite's deadline: the Invite's `published` time plus the configured RSVP window, capped at the end of the active embargo ([CM-11-014](../specs/protocol.md#cm-11-014), [CM-28-012](../specs/protocol.md#cm-28-012)).
  When the deadline passes, the Invite closes and the invitee's record does not change.
  A reply after the deadline is still processed: an `Accept` joins the invitee and a `Reject` closes the record.
  The CASE_MANAGER can re-invite an actor with a fresh stub Invite on the same record and a new deadline, and the fresh Invite's `inReplyTo` names the earlier one ([CM-11-015](../specs/protocol.md#cm-11-015)).
  A re-invite of a participant that has closed is refused.
  When the active embargo is activated, revised or terminated while a stub Invite is outstanding, the CASE_MANAGER sends a replacement with the current terms and a new deadline.
  The replacement names the Invite it supersedes in the standard AS2 `inReplyTo` property.
  The replacement is also an invitation to the embargo now in force: the CASE_MANAGER marks the invitee's consent row for that embargo `INVITED` with the replacement's deadline, and records the row as its own ledger entry after the replacement's.
  With no embargo in force, no consent row changes.
  An `Accept` of the superseded Invite is refused, naming the replacement, and a `Reject` of it is honored ([CM-11-016](../specs/protocol.md#cm-11-016)).
- **Ask kind:** the Invite closes on `Accept` or `Reject` of it (`INVITE_ACTOR_TO_CASE_REPLY_TYPES`), and its expiry is stale: a late reply is still processed ([ASK-03-008](../specs/protocol.md#ask-03-008)).
- **Example artifact:** [invite_to_case.json](../examples/invite_to_case.json).

{% include-markdown "./_occasions/sections/accept-invite-to-case.md" %}

- **Effects:** the CASE_MANAGER records the acceptance in the ledger, marks the participant's existing record joined, and then sends `Announce(VulnerabilityCase)` to seed the new participant's replica ([CM-17-004](../specs/protocol.md#cm-17-004)).
  An Accept from an invitee with no participant record is refused with a reported reason and writes nothing, because an Accept never creates a participant ([CM-11-021](../specs/protocol.md#cm-11-021)).
  The Accept is the ledger entry for its own effects (the consent row and `joined`), which a replica applies; the record's creation and a vendor's VF status have their own entries; the CASE_MANAGER sends no `Add(CaseParticipant)` for it ([CM-31-012](../specs/protocol.md#cm-31-012)).
- **What it does not do:** it joins the case and consents to the active embargo; it does not judge the case.
  The participant judges the case by answering the [Full-Case Invite](#invite-actor-to-full-case) that follows.
- **Example artifact:** [accept_invite_to_case.json](../examples/accept_invite_to_case.json).

{% include-markdown "./_occasions/sections/reject-invite-to-case.md" %}

- **Effects:** the CASE_MANAGER moves the invitee's record to RM Closed and keeps it, and the participant stays inert ([CM-11-007](../specs/protocol.md#cm-11-007)).
  A `Reject` from an invitee that has no participant record is refused with a reported reason, not ignored ([CM-11-018](../specs/protocol.md#cm-11-018)).
- **Triggering transition:** none — roster action.
- **Example artifact:** [reject_invite_to_case.json](../examples/reject_invite_to_case.json).

{% include-markdown "./_occasions/sections/invite-actor-to-full-case.md" %}

- **Sequence:** after a participant joins, the CASE_MANAGER sends `Announce(VulnerabilityCase)`, starts the ledger replay, and then asks the participant to judge the case with the full-case Invite ([CM-11-010](../specs/protocol.md#cm-11-010), [ADR-0121](../../adr/0121-joined-participant-judges-the-case-by-full-case-invite.md)).
  The participant already holds the case, so the Invite names it by URI and asks one question: is this case valid?
- **Triggering transition:** none — the Invite asks; the reply moves RM.
- **Object and target:** the `object` is the participant, and the `target` is the plain case URI ([AKM-02-003](../specs/protocol.md#akm-02-003)).
  The CASE_MANAGER's ledger position when it issued the Invite travels in the standard AS2 `content` field, as the JSON dump of the `LedgerPosition` model, for example `{"logIndex":3,"entryHash":"<hash>"}`.
  It is a floor: the participant's reply must reach at least this point in the ledger ([VAM-04-011](../specs/protocol.md#vam-04-011)).
  An empty ledger is `logIndex` -1 with the case's `genesisHash` as `entryHash` ([CLP-08-004](../specs/protocol.md#clp-08-004)).
- **Ask kind:** the Invite closes on `Accept`, `TentativeReject` or `Reject` of it (`INVITE_ACTOR_TO_FULL_CASE_REPLY_TYPES`).

{% include-markdown "./_occasions/sections/accept-full-case-invite.md" %}

- **Effects:** the participant judges the case valid ([Validate report](rm.md#report-valid)), and the CASE_MANAGER records RM Received → Valid ([CM-11-011](../specs/protocol.md#cm-11-011)).
- **Ledger position:** the reply carries the participant's own ledger position in `content`, in the same form as the Invite ([VAM-04-012](../specs/protocol.md#vam-04-012)).
  The CASE_MANAGER refuses a reply whose position is behind the Invite's, or names an entry its ledger does not hold, and writes nothing ([CM-11-012](../specs/protocol.md#cm-11-012)).
  It also refuses, and writes nothing for, a reply from an inert participant that has not joined the case (CM-11-012).

{% include-markdown "./_occasions/sections/tentatively-reject-full-case-invite.md" %}

- **Effects:** the participant judges the case invalid ([Invalidate report](rm.md#report-invalid)), and the CASE_MANAGER records RM Received → Invalid.
  The stub Invite has no `TentativeReject`, because accepting a stub judges nothing ([CM-11-007](../specs/protocol.md#cm-11-007)).
- **Ledger position:** the reply carries the participant's ledger position in `content` ([VAM-04-013](../specs/protocol.md#vam-04-013)).

{% include-markdown "./_occasions/sections/reject-full-case-invite.md" %}

- **Effects:** the participant closes the case ([Close report](rm.md#report-closed)), and the CASE_MANAGER records RM Received → Closed; the participant stops receiving case content.
- **Ledger position:** the reply carries the participant's ledger position in `content` ([VAM-04-014](../specs/protocol.md#vam-04-014)).

{% include-markdown "./_occasions/sections/announce-vulnerability-case.md" %}

- **Contents:** the full `VulnerabilityCase` object is delivered inline so the recipient can seed its local replica ([PCR-02-002](../specs/protocol.md#pcr-02-002)).
  The same activity delivers a full case snapshot at every later lifecycle stage ([PCR-02-001](../specs/protocol.md#pcr-02-001)).
- **Triggering transition:** none — roster action following invite acceptance.
- **Example artifact:** [announce_case.json](../examples/announce_case.json).

{% include-markdown "./_occasions/sections/close-case.md" %}

- **Triggering transition:** RM: A → C.
- **Example artifact:** [close_case.json](../examples/close_case.json).

{% include-markdown "./_occasions/sections/add-case-participant-to-case.md" %}

- **Reinstatement:** it clears the participant's removal fact, so it is entitled to case content again; it does not ask the participant to accept again.
  `Add(CaseParticipant)` does not seat a new member: an actor joins a case by accepting its stub Invite (see [Accept Invite to Case](#accept-invite-to-case)).
- **Triggering transition:** none — the participant's record loses its removal fact.
- **Who may send:**
  The CASE_MANAGER accepts it only from the Case Owner.
  It refuses an `Add` that names a participant that is not removed, a participant that never joined the case, or no participant of the case.
  It also refuses an `Add` whose participant gives an `attributedTo` other than the actor of the record it names, because each replica finds its own copy of the record by that actor.
  A participant replica accepts it only from the CASE_MANAGER, as the direct notice below, and writes nothing from it.
- **Ledger:** the Case Owner's received `Add` is the one ledger entry for the reinstatement.
  Every replica applies the reinstatement from that entry, the reinstated participant's own included.
- **Catch-up:** once the participant is active again, the CASE_MANAGER sends it every ledger entry committed after its removal entry, in log order, so its copy of the ledger has no gap.
  A participant that is not a signatory to the active embargo stays inert: the CASE_MANAGER sends it that embargo's Invite instead, and the catch-up waits until it accepts.
- **Notice:** the CASE_MANAGER also sends the reinstated participant a direct `Add(CaseParticipant)` naming it, with `actor` set to the CASE_MANAGER and `attributedTo` set to the Case Owner.
  The notice is not ledgered.
- **Spec:** [Participant Removal](../vultron-spec/interactions.md#114-participant-removal-n).

The example above shows a Vendor that holds the Case Owner role reinstating a Coordinator.
The wire shape is the same whatever roles the participant holds; only `caseRoles` on the attached object differs.

{% include-markdown "./_occasions/sections/remove-case-participant-from-case.md" %}

- **Removal:** it withdraws the participant's entitlement to case content; the participant's record stays on the case roster.
- **Triggering transition:** none — the participant's record gains a removal fact.
- **Target:** the case MUST be named in `target`; a `Remove` that names the case only in `origin` is not recognized as this message.
- **Who may send:**
  The CASE_MANAGER accepts it only from the Case Owner.
  It refuses a removal of the CASE_MANAGER's or the Case Owner's participant, and a removal that names no participant of the case.
  It also refuses a removal whose participant gives an `attributedTo` other than the actor of the record it names, because each replica finds its own copy of the record by that actor.
  A participant replica accepts it only from the CASE_MANAGER, as the direct notice below, and writes nothing from it.
- **Ledger:** the Case Owner's received `Remove` is the one ledger entry for the removal.
  Every replica applies the removal from that entry, the removed participant's own included.
- **Notice:** the CASE_MANAGER then sends the removed participant a direct `Remove(CaseParticipant)` naming it, with `actor` set to the CASE_MANAGER and `attributedTo` set to the Case Owner.
  The notice is not ledgered.
- **Spec:** [Participant Removal](../vultron-spec/interactions.md#114-participant-removal-n).
- **Example artifact:** [remove_participant_from_case.json](../examples/remove_participant_from_case.json).

## Update Case { #update-case }

`Update(VulnerabilityCase)` is not an occasion: it is not a message any actor sends.

- **Protocol role:** it is reserved as the snapshot shape of a ledger entry.
  Every change the CASE_MANAGER makes to the case file must be its own ledger entry ([CLP-07-013](../specs/protocol.md#clp-07-013)), and an `Update` carrying the case in full is the shape such an entry takes for a change to a case field.
  The prototype does not yet commit an `Update(VulnerabilityCase)` entry: the canonical-entry check does not yet admit that signature.
  Once it does, replicas copy the entry from the ledger fan-out ([§5.4.2 Routing Topology](../vultron-spec/layers.md#542-routing-topology)).
  A participant that wants a change made asks the CASE_MANAGER; it does not send `Update` to the CASE_MANAGER or to its peers.
- **On receipt:** an inbox refuses a direct `Update(VulnerabilityCase)` as an unrecognized activity and changes nothing.
- **Triggering transition:** none — metadata change, not a state transition.
- **Example artifact:** [update_case.json](../examples/update_case.json), the snapshot shape as the case actor would author it.

## Create Case Participant { #create-case-participant }

`Create(CaseParticipant)` is not an occasion: this implementation does not support it as a message an actor sends.

- **Protocol role:** it is the snapshot shape of the CASE_MANAGER's `create_case_participant` ledger entry.
  The CASE_MANAGER creates the invitee's participant record when it sends a stub Invite, and commits that creation as its own entry, carrying the record in full ([CLP-07-013](../specs/protocol.md#clp-07-013)).
  Replicas copy the record from the ledger fan-out ([§5.4.2 Routing Topology](../vultron-spec/layers.md#542-routing-topology)).
  An actor joins a case by accepting its stub Invite (see [Accept Invite to Case](#accept-invite-to-case)).
- **On receipt:** an inbox refuses a direct `Create(CaseParticipant)` as an unrecognized activity and changes nothing.
- **Triggering transition:** none — object construction.
- **Example artifact:** [create_participant.json](../examples/create_participant.json), the snapshot shape as the case actor authors it.
