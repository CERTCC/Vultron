---
stakeholder_type: [platform-developer, project-contributor]
level: 400
page_type: reference
subject: protocol
description: >
  Case lifecycle, participant roster, and ownership transfer activities.
---

# Case Management Messages

These messages drive the lifecycle of a `VulnerabilityCase`, the record of one Coordinated Vulnerability Disclosure (CVD) case, and its roster of participants.
They have no formal-protocol shorthand — the 28-symbol formal message set addresses state-machine transitions, not the case-infrastructure layer that supports them (see [ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)).

All messages on this page operate on a case that already exists.
For the pre-existence bootstrap (vendor → case-actor service), see [Case Proposal](case_proposal.md).
For the ledger mechanism that replicates these activities to all participants, see [Ledger Replication](ledger_replication.md).

Two authorities appear below, and they are distinct roles rather than one actor.
The **Case Owner** decides for the case: who is admitted, which roles they hold, and whether an ownership transfer is offered.

The **CASE_MANAGER** is the case's single-writer authority.
It mints and updates the `VulnerabilityCase` object, records every case-scoped message in the ledger, and delivers case snapshots to participants (spec [§10.1 Single-Writer Authority](../vultron-spec/interactions.md#101-single-writer-authority), [ADR-0088](../../adr/0088-consolidate-case-authority-determination.md)).
The CASE_MANAGER acts for the Case Owner.
The same actor often holds both roles, but it need not.

If the CASE_MANAGER refuses one of these messages because a precondition does not hold, it answers the sender with the [refusal notice](faults_and_acknowledgements.md#refusal-notice).
That notice is a `Reject` of the refused message, with the reason in `summary` ([CLP-02-005](../vultron-spec/requirements/ledger-replication.md#clp-02-005), [CLP-05-001](../vultron-spec/requirements/ledger-replication.md#clp-05-001)).
The CASE_MANAGER records nothing of the refused message in the ledger.
It sends no answer when the sender may not send the message at all, or when the message repeats one whose effect is already in place.

Each message on this page also states its sender's ledger position.
The sender puts the tail of its copy of the case ledger in the activity's `ledgerPosition`, an object with `logIndex` and `entryHash`, when it builds the message ([SYNC-18-001](../vultron-spec/requirements/ledger-replication.md#sync-18-001)).
A receiver refuses such a message when it carries no position or one that does not parse, and writes nothing ([SYNC-18-003](../vultron-spec/requirements/ledger-replication.md#sync-18-003)).
`Create(VulnerabilityCase)`, `Update(VulnerabilityCase)` and `Announce(VulnerabilityCase)` carry none, because the case they carry states its own position.
A reply to a stub `Invite` carries none either, because its sender does not hold the case yet.

A refused `Offer` or `Invite` is answered with a `Reject` of it, which the sender reads as the decline of its request.
The [close-case](#close-case) decline is the one message on this page with an answer of its own, so it gets no refusal notice.
The 300-level introduction is [The Case Manager and the Case Ledger](../../topics/case_lifecycle/case_manager_and_ledger.md).

## Occasions

{% include-markdown "./_occasions/lookup-case_management.md" %}

{% include-markdown "./_occasions/sections/create-case.md" %}

- **Recipients:** the CASE_MANAGER sends the completed case to the report receiver (the Case Owner) only ([CBT-01-010](../vultron-spec/requirements/ledger-replication.md#cbt-01-010), [CM-22-001](../vultron-spec/requirements/case-management.md#cm-22-001), [CM-22-002](../vultron-spec/requirements/case-management.md#cm-22-002)).
  The report receiver then sends the report submitter a `Create(VulnerabilityCase)` as itself.
  That message names the CASE_MANAGER and is the trust bootstrap (spec [§10.3 Case Bootstrap and the Trust Root](../vultron-spec/interactions.md#103-case-bootstrap-and-the-trust-root); [CBT-01-001](../vultron-spec/requirements/ledger-replication.md#cbt-01-001), [ADR-0132](../../adr/0132-the-report-receiver-introduces-the-case-manager-to-the-reporter.md)).
- **Who is named where:** the `actor` of the `Create` is the CASE_MANAGER that mints the case, and the case's `attributedTo` is the Case Owner ([CP-09-001](../vultron-spec/requirements/case-management.md#cp-09-001), [CM-02-008](../vultron-spec/requirements/case-management.md#cm-02-008)).
  The two coincide when the Case Owner creates its own case, as in the example above.
  When a case-actor service creates the case from a [Case Proposal](case_proposal.md), the service is the `actor` and `attributedTo` names the proposing actor, never the service itself.
  Every owner check reads `attributedTo`, and an ownership transfer rewrites it ([CM-21-002](../vultron-spec/requirements/case-management.md#cm-21-002)).
- **Triggering transition:** none — object construction precedes protocol state.
- **Example artifact:** [create_case.json](../examples/create_case.json).

{% include-markdown "./_occasions/sections/add-report-to-case.md" %}

- **Triggering transition:** none — a report can be added at any Report Management (RM) state.
- **Who may send:** the CASE_MANAGER admits it only from the Case Owner, and a participant replica accepts it only from the CASE_MANAGER.
  Any other sender is refused and the report is not attached.
- **Example artifact:** [add_report_to_case.json](../examples/add_report_to_case.json).

{% include-markdown "./_occasions/sections/offer-case-participant-role.md" %}

- **Routing:** the offer is addressed to the CASE_MANAGER only, never to the target ([CM-33-001](../vultron-spec/requirements/case-management.md#cm-33-001)).
  The CASE_MANAGER records it in the ledger.
  Then it forwards it to the target as its own `Offer(CaseParticipantRole)`, with the Case Owner in `attributedTo` and `inReplyTo` naming the recorded offer.
  The target acts only on that forward, and answers the CASE_MANAGER, not the Case Owner ([CM-33-004](../vultron-spec/requirements/case-management.md#cm-33-004)).
  Nothing is granted until the CASE_MANAGER records the target's `Accept` ([CM-02-016](../specs/project.md#cm-02-016)).
- **Who may send:** the Case Owner only.
  The CASE_MANAGER refuses an offer from any other sender ([CM-33-002](../vultron-spec/requirements/case-management.md#cm-33-002)).
  `CASE_OWNER` and `CASE_MANAGER` cannot be offered.
  The CASE_MANAGER also refuses an offer with no readable role, or of a role the target already holds.
  It also refuses an offer whose target is not a participant, or whose target is the CASE_MANAGER itself ([CM-33-003](../vultron-spec/requirements/case-management.md#cm-33-003)).
  A refused offer is not recorded and not forwarded.
  The CASE_MANAGER answers an offer refused for its role or target with the refusal notice, and an offer from any other sender with nothing.
- **Object type:** the object type alone identifies the activity as a role offer rather than an ownership-transfer offer (ADR-0039).
  Roles are granted through the case's authority chain ([§12.1 Role Assignment](../vultron-spec/interactions.md#121-role-assignment-n)).
- **Target:** the participant offered the role.
  The `context` is the case.
- **Forward example:** [forward_case_participant_role.json](../examples/forward_case_participant_role.json).
- **Triggering transition:** none — roster action, not a state-machine event.
- **Example artifact:** [offer_case_participant_role.json](../examples/offer_case_participant_role.json).

The [`CaseParticipantRole`](../activitypub/objects.md#caseparticipantrole) object carries the role.
This offer is distinct from `Offer(CaseParticipant)`, which forwards an actor recommendation to the Case Owner and is covered under [Offer case participant](general.md#offer-case-participant).

{% include-markdown "./_occasions/sections/accept-case-participant-role.md" %}

- **Routing:** the `Accept` goes to the CASE_MANAGER only, never to the Case Owner that made the offer ([CM-33-004](../vultron-spec/requirements/case-management.md#cm-33-004)).
  Its `object` is the CASE_MANAGER's forward, which the CASE_MANAGER matches to the recorded offer through the forward's `inReplyTo`, never through the copy the `Accept` carries.
- **Who may send:** the target of the recorded offer only, and only while that offer is open: until the CASE_MANAGER records an `Accept` or `Reject` of it ([CM-33-005](../vultron-spec/requirements/case-management.md#cm-33-005)).
  The CASE_MANAGER refuses an `Accept` from any other sender, or to an offer that is no longer open.
  It also refuses an `Accept` whose carried offer names another role or target.
  For a refused `Accept`, the CASE_MANAGER writes no ledger entry and changes no role.
  When the CASE_MANAGER refuses an `Accept` because the offer is no longer open or its carried offer differs, it answers with the refusal notice.
  It answers an `Accept` from any other sender with nothing.
  A redelivery of the `Accept` that closed the offer changes nothing.
- **Effect:** the CASE_MANAGER records the `Accept` in the ledger as `accept_case_participant_role`, and grants the role on its own copy of the case.
  It announces the entry to every participant.
  Each participant grants the role when it replays the entry ([CM-33-006](../vultron-spec/requirements/case-management.md#cm-33-006), [CM-02-016](../specs/project.md#cm-02-016)).
- **Triggering transition:** none — roster action.
- **Example artifact:** [accept_case_participant_role.json](../examples/accept_case_participant_role.json).

{% include-markdown "./_occasions/sections/reject-case-participant-role.md" %}

- **Routing:** as for the `Accept`, the `Reject` goes to the CASE_MANAGER only, and names the forward it answers ([CM-33-004](../vultron-spec/requirements/case-management.md#cm-33-004)).
- **Who may send:** as for the `Accept`, the target of the recorded offer only, while that offer is open ([CM-33-005](../vultron-spec/requirements/case-management.md#cm-33-005)).
  The CASE_MANAGER answers a refused `Reject` as it does a refused `Accept`.
- **Effect:** the CASE_MANAGER records the `Reject` in the ledger as `reject_case_participant_role` and announces the entry to every participant ([CM-33-006](../vultron-spec/requirements/case-management.md#cm-33-006)).
  The entry closes the offer, and no role changes.
- **Triggering transition:** none — roster action.
- **Example artifact:** [reject_case_participant_role.json](../examples/reject_case_participant_role.json).

The dedicated object type is preferred over a `target`-field discriminator ([SE-08-003](../vultron-spec/requirements/messages.md#se-08-003)), and the earlier wire format `Offer(VulnerabilityCase)[target=CaseParticipant]` for offering a role has been removed.

{% include-markdown "./_occasions/sections/propose-case-ownership-transfer.md" %}

- **Routing:** the proposal is addressed to the CASE_MANAGER, never to the proposed new owner ([CM-21-005](../vultron-spec/requirements/case-management.md#cm-21-005)).
  See [Case Ownership Transfer](../../topics/case_lifecycle/ownership_transfer.md).
  The CASE_MANAGER admits it only from the Case Owner, and only while no offer for the case is open ([CM-21-019](../vultron-spec/requirements/case-management.md#cm-21-019), [CM-21-014](../vultron-spec/requirements/case-management.md#cm-21-014)).
  It refuses a proposal whose inner offer names another case, or no actor it can address, and ignores any `id`, `actor` or `to` inside the inner offer.
- **Context:** the case the proposal is about.
  The inner offer's object must be that case, as a typed reference: an inline object with only its `id` and `type` ([AKM-03-004](../specs/project.md#akm-03-004), [ADR-0165](../../adr/0165-a-participants-act-on-a-case-names-the-case-and-never-carries-it.md)).
- **Trigger:** the Case Owner sends it with `POST /actors/{actor_id}/trigger/offer-case-ownership-transfer`, which returns the proposal ([TRIG-11-001](../specs/project.md#trig-11-001), [Trigger API Reference](../trigger-api.md#actor-participation)).
- **Effect:** the CASE_MANAGER records the proposal in the ledger and makes the offer below itself ([ADR-0148](../../adr/0148-an-owner-proposes-an-ownership-transfer-offer-and-the-case-manager-makes-it.md)).
- **Triggering transition:** none — ownership transfer is a roster operation.
- **Example artifact:** [propose_case_ownership_transfer.json](../examples/propose_case_ownership_transfer.json).

{% include-markdown "./_occasions/sections/offer-case-ownership-transfer.md" %}

- **Routing:** the CASE_MANAGER makes the offer from the owner's proposal and records it in the ledger ([§12.3 Case Ownership Transfer](../vultron-spec/interactions.md#123-case-ownership-transfer-n), [CM-21-005](../vultron-spec/requirements/case-management.md#cm-21-005)).
  It is the one offer of the transfer: its `id` is one the CASE_MANAGER derives from the proposal, and the proposed new owner answers it by that `id`.
  A participant takes it only from the CASE_MANAGER ([CM-21-019](../vultron-spec/requirements/case-management.md#cm-21-019)).
- **Target:** the proposed new owner, as a full actor object.
- **Object:** the case, as a typed reference: an inline object with only its `id` and `type` ([AKM-03-004](../specs/project.md#akm-03-004), [ADR-0165](../../adr/0165-a-participants-act-on-a-case-names-the-case-and-never-carries-it.md)).
  The proposed new owner is an active participant, so it already holds the case ([CM-21-021](../vultron-spec/requirements/case-management.md#cm-21-021)).
- **Triggering transition:** none — ownership transfer is a roster operation.
- **Example artifact:** [offer_case_ownership_transfer.json](../examples/offer_case_ownership_transfer.json).

{% include-markdown "./_occasions/sections/accept-case-ownership-transfer.md" %}

- **Triggering transition:** none — roster operation.
- **Example artifact:** [accept_case_ownership_transfer.json](../examples/accept_case_ownership_transfer.json).

{% include-markdown "./_occasions/sections/reject-case-ownership-transfer.md" %}

- **Routing:** the `Reject` is addressed to the CASE_MANAGER, not to the actor that made the offer ([CM-21-010](../vultron-spec/requirements/case-management.md#cm-21-010)).
  The CASE_MANAGER acts on it only when it comes from the proposed owner of an open offer it recorded ([CM-21-013](../vultron-spec/requirements/case-management.md#cm-21-013)).
  It records the `Reject` in the ledger and sends the entry to every participant, which closes the offer ([CM-21-012](../vultron-spec/requirements/case-management.md#cm-21-012)).
- **Trigger:** the recipient sends it with `POST /actors/{actor_id}/trigger/reject-case-ownership-transfer`, whose body names the `offer_id` it declines ([TRIG-11-005](../specs/project.md#trig-11-005), [Trigger API Reference](../trigger-api.md#actor-participation)).
- **Triggering transition:** none — roster operation.
- **Example artifact:** [reject_case_ownership_transfer.json](../examples/reject_case_ownership_transfer.json).

{% include-markdown "./_occasions/sections/withdraw-case-ownership-transfer.md" %}

- **Routing:** the withdrawal is addressed to the CASE_MANAGER ([CM-21-015](../vultron-spec/requirements/case-management.md#cm-21-015)).
  It is an `Undo` of the owner's own proposal.
  The CASE_MANAGER withdraws the offer that it made from that proposal.
  It acts only when the withdrawal comes from the Case Owner that the offer was made for, and only while the offer is open.
  It records the withdrawal in the ledger and sends the entry to every participant, which closes the offer.
  The proposed owner can no longer accept it, and the case may be offered again ([CM-21-014](../vultron-spec/requirements/case-management.md#cm-21-014)).
  A withdrawal from anyone else, or of an offer already answered or withdrawn, is refused with nothing recorded.
  The CASE_MANAGER answers a withdrawal of an offer already answered or withdrawn with the refusal notice, and a withdrawal from anyone else with nothing.
- **Trigger:** the Case Owner sends it with `POST /actors/{actor_id}/trigger/withdraw-case-ownership-transfer`, whose body names, as `offer_id`, the proposal it withdraws ([TRIG-11-006](../specs/project.md#trig-11-006), [Trigger API Reference](../trigger-api.md#actor-participation)).
- **Triggering transition:** none — roster operation.
- **Example artifact:** [undo_case_ownership_transfer.json](../examples/undo_case_ownership_transfer.json).

{% include-markdown "./_occasions/sections/invite-actor-to-case.md" %}

- **Who decides:** the Case Owner decides whom to invite.
  A participant that wants a third party brought in sends a recommendation instead ([Suggest actor to case](general.md#suggest-actor-to-case)).
  See [§12.2 Invitation and Acceptance](../vultron-spec/interactions.md#122-invitation-and-acceptance-n).
- **Triggering transition:** none — roster action.
- **Object and target:** the `object` is the actor being invited, and the `target` is the case stub, of type `VulnerabilityCaseStub`.
  The stub carries the case identifier in its `caseId` and a required `summary` field: the owner-chosen description the invitee reads before deciding whether to accept ([CM-11-013](../vultron-spec/requirements/case-management.md#cm-11-013), [CM-17-010](../vultron-spec/requirements/case-management.md#cm-17-010), [MV-10-001](../vultron-spec/requirements/messages.md#mv-10-001)).
  The factory raises `VultronActivityConstructionError` when `VulnerabilityCase.stub_summary` is not set, and the receiver refuses a stub with an absent or blank `summary`.
  The Invite names at least one CVD role for the invitee, and the CASE_MANAGER refuses to send one with an empty role list ([CM-11-019](../vultron-spec/requirements/case-management.md#cm-11-019)).
  The Invite carries its reply deadline in `endTime`.
  The CASE_MANAGER sets that deadline the same way it sets an embargo Invite's deadline.
  The deadline is the Invite's `published` time plus the configured RSVP window, capped at the end of the active embargo ([CM-11-014](../vultron-spec/requirements/case-management.md#cm-11-014), [CM-28-012](../vultron-spec/requirements/case-management.md#cm-28-012)).
  When the deadline passes, the Invite closes and the invitee's record does not change.
  A reply after the deadline is still processed: an `Accept` joins the invitee and a `Reject` closes the record.
  The CASE_MANAGER can re-invite an actor with a fresh stub Invite on the same record and a new deadline.
  The fresh Invite's `inReplyTo` names the earlier one ([CM-11-015](../vultron-spec/requirements/case-management.md#cm-11-015)).
  A re-invite of a participant that has closed is refused.
  When the active embargo is activated, revised or terminated while a stub Invite is outstanding, the CASE_MANAGER sends a replacement with the current terms and a new deadline.
  The replacement names the Invite it supersedes in the standard AS2 `inReplyTo` property.
  The replacement is also an invitation to the embargo now in force.
  The CASE_MANAGER marks the invitee's consent row for that embargo `INVITED` with the replacement's deadline.
  It records the row as its own ledger entry, after the replacement's entry.
  With no embargo in force, no consent row changes.
  An `Accept` of the superseded Invite is refused, naming the replacement, and a `Reject` of it is honored ([CM-11-016](../vultron-spec/requirements/case-management.md#cm-11-016)).
- **Ask kind:** the Invite closes on `Accept` or `Reject` of it (`INVITE_ACTOR_TO_CASE_REPLY_TYPES`), and its expiry is stale: a late reply is still processed ([ASK-03-008](../vultron-spec/requirements/case-management.md#ask-03-008)).
- **Example artifact:** [invite_to_case.json](../examples/invite_to_case.json).

{% include-markdown "./_occasions/sections/accept-invite-to-case.md" %}

- **Effects:** the CASE_MANAGER records the acceptance in the ledger, marks the participant's existing record joined, and then sends `Announce(VulnerabilityCase)` to seed the new participant's replica ([CM-17-004](../vultron-spec/requirements/case-management.md#cm-17-004)).
  An Accept from an invitee with no participant record is refused with a reported reason and writes nothing, because an Accept never creates a participant ([CM-11-021](../vultron-spec/requirements/case-management.md#cm-11-021)).
  The Accept is the ledger entry for its own effects (the consent row and `joined`), which a replica applies.
  The record's creation and a vendor's VF status have their own entries.
  The CASE_MANAGER sends no `Add(CaseParticipant)` for it ([CM-31-012](../vultron-spec/requirements/case-management.md#cm-31-012)).
- **What it does not do:** it joins the case and consents to the active embargo.
  It does not judge the case.
  The participant judges the case by answering the [Full-Case Invite](#invite-actor-to-full-case) that follows.
- **Example artifact:** [accept_invite_to_case.json](../examples/accept_invite_to_case.json).

{% include-markdown "./_occasions/sections/reject-invite-to-case.md" %}

- **Effects:** the CASE_MANAGER moves the invitee's record to RM Closed and keeps it, and the participant stays inert ([CM-11-007](../vultron-spec/requirements/case-management.md#cm-11-007)).
  A `Reject` from an invitee that has no participant record is refused with a reported reason, not ignored ([CM-11-018](../vultron-spec/requirements/case-management.md#cm-11-018)).
- **Triggering transition:** none — roster action.
- **Example artifact:** [reject_invite_to_case.json](../examples/reject_invite_to_case.json).

{% include-markdown "./_occasions/sections/invite-actor-to-full-case.md" %}

- **Sequence:** after a participant joins, the CASE_MANAGER sends `Announce(VulnerabilityCase)`, starts the ledger replay, and then asks the participant to judge the case with the full-case Invite ([CM-11-010](../vultron-spec/requirements/case-management.md#cm-11-010), [ADR-0121](../../adr/0121-joined-participant-judges-the-case-by-full-case-invite.md)).
  The participant already holds the case, so the Invite names it by URI and asks one question: is this case valid?
- **Triggering transition:** none — the Invite asks, and the reply moves RM.
- **Object and target:** the `object` is the participant, and the `target` is the plain case URI ([AKM-02-003](../vultron-spec/requirements/messages.md#akm-02-003)).
  The CASE_MANAGER's ledger position when it issued the Invite travels as the Invite's `ledgerPosition`, the property every case activity carries, for example `"ledgerPosition": {"logIndex": 3, "entryHash": "<hash>"}` ([SYNC-18-001](../vultron-spec/requirements/ledger-replication.md#sync-18-001)).
  It is a floor: the participant's reply must reach at least this point in the ledger ([VAM-04-011](../vultron-spec/requirements/messages.md#vam-04-011)).
  An empty ledger is `logIndex` -1 with the case's `genesisHash` as `entryHash` ([CLP-08-004](../vultron-spec/requirements/ledger-replication.md#clp-08-004)).
- **Ask kind:** the Invite closes on `Accept`, `TentativeReject` or `Reject` of it (`INVITE_ACTOR_TO_FULL_CASE_REPLY_TYPES`).

{% include-markdown "./_occasions/sections/accept-full-case-invite.md" %}

- **Effects:** the participant judges the case valid ([Validate report](rm.md#report-valid)), and the CASE_MANAGER records RM Received → Valid ([CM-11-011](../vultron-spec/requirements/case-management.md#cm-11-011)).
- **Ledger position:** the reply carries the participant's own ledger position as its `ledgerPosition`, in the same form as the Invite ([VAM-04-012](../vultron-spec/requirements/messages.md#vam-04-012)).
  The CASE_MANAGER refuses a reply whose position is behind the Invite's, or names an entry its ledger does not hold, and writes nothing ([CM-11-012](../vultron-spec/requirements/case-management.md#cm-11-012)).
  It also refuses, and writes nothing for, a reply from an inert participant that has not joined the case (CM-11-012).

{% include-markdown "./_occasions/sections/tentatively-reject-full-case-invite.md" %}

- **Effects:** the participant judges the case invalid ([Invalidate report](rm.md#report-invalid)), and the CASE_MANAGER records RM Received → Invalid.
  The stub Invite has no `TentativeReject`, because accepting a stub judges nothing ([CM-11-007](../vultron-spec/requirements/case-management.md#cm-11-007)).
- **Ledger position:** the reply carries the participant's ledger position as its `ledgerPosition` ([VAM-04-013](../vultron-spec/requirements/messages.md#vam-04-013)).

{% include-markdown "./_occasions/sections/reject-full-case-invite.md" %}

- **Effects:** the participant closes the case ([Close report](rm.md#report-closed)), and the CASE_MANAGER records RM Received → Closed.
  The participant stops receiving case content.
- **Ledger position:** the reply carries the participant's ledger position as its `ledgerPosition` ([VAM-04-014](../vultron-spec/requirements/messages.md#vam-04-014)).

{% include-markdown "./_occasions/sections/announce-vulnerability-case.md" %}

- **Contents:** the full `VulnerabilityCase` object is delivered inline so the recipient can seed its local replica ([PCR-02-002](../vultron-spec/requirements/ledger-replication.md#pcr-02-002)).
  The same activity delivers a full case snapshot at every later lifecycle stage ([PCR-02-001](../vultron-spec/requirements/ledger-replication.md#pcr-02-001)).
- **Triggering transition:** none — roster action following invite acceptance.
- **Example artifact:** [announce_case.json](../examples/announce_case.json).

{% include-markdown "./_occasions/sections/close-case.md" %}

- **Triggering transition:** RM: A → C.
- **Object:** the case, as a typed reference: an inline object with only its `id` and `type` ([AKM-03-004](../specs/project.md#akm-03-004), [ADR-0165](../../adr/0165-a-participants-act-on-a-case-names-the-case-and-never-carries-it.md)).
  The CASE_MANAGER reads the case from its own store and refuses a case it does not hold ([AKM-03-006](../specs/project.md#akm-03-006)).
  A full case that another sender still carries is not refused, but the CASE_MANAGER reads only its `id` and stores nothing from it ([AKM-03-005](../specs/project.md#akm-03-005)).
- **Decline:** while the case holds an active embargo, the CASE_MANAGER declines the Case Owner's close with a `Reject` of the `Leave` and records nothing ([CM-23-011](../vultron-spec/requirements/case-management.md#cm-23-011)).
  That decline is the answer to the refusal, so the CASE_MANAGER sends no refusal notice as well.
- **Example artifact:** [close_case.json](../examples/close_case.json).

{% include-markdown "./_occasions/sections/add-case-participant-to-case.md" %}

- **Reinstatement:** it clears the participant's removal fact, so the participant is entitled to case content again.
  It does not ask the participant to accept again.
  `Add(CaseParticipant)` does not seat a new member: an actor joins a case by accepting its stub Invite (see [Accept Invite to Case](#accept-invite-to-case)).
- **Triggering transition:** none — the participant's record loses its removal fact.
- **Who may send:**
  The CASE_MANAGER admits it only from the Case Owner.
  It refuses an `Add` that names a participant that is not removed, a participant that never joined the case, or no participant of the case.
  It also refuses an `Add` whose participant gives an `attributedTo` other than the actor of the record it names.
  The reason is that each replica finds its own copy of the record by that actor.
  A participant replica accepts it only from the CASE_MANAGER, as the direct notice below, and writes nothing from it.
- **Ledger:** the Case Owner's received `Add` is the one ledger entry for the reinstatement.
  Every replica applies the reinstatement from that entry, the reinstated participant's own included.
- **Catch-up:** after the participant is active again, the CASE_MANAGER sends it every ledger entry committed after its removal entry.
  It sends the entries in log order, so the participant's copy of the ledger has no gap.
  A participant that is not a signatory to the active embargo stays inert: the CASE_MANAGER sends it that embargo's Invite instead, and the catch-up waits until it accepts.
- **Notice:** the CASE_MANAGER also sends the reinstated participant a direct `Add(CaseParticipant)` naming it, with `actor` set to the CASE_MANAGER and `attributedTo` set to the Case Owner.
  The notice is not ledgered.
- **Spec:** [Participant Removal](../vultron-spec/interactions.md#124-participant-removal-n).

The example above shows a Vendor that holds the Case Owner role reinstating a Coordinator.
The wire shape is the same whatever roles the participant holds.
Only `caseRoles` on the attached object differs.

{% include-markdown "./_occasions/sections/remove-case-participant-from-case.md" %}

- **Removal:** it withdraws the participant's entitlement to case content.
  The participant's record stays on the case roster.
- **Triggering transition:** none — the participant's record gains a removal fact.
- **Target:** the case MUST be named in `target`.
  A `Remove` that names the case only in `origin` is not recognized as this message.
- **Who may send:**
  The CASE_MANAGER admits it only from the Case Owner.
  It refuses a removal of the CASE_MANAGER's or the Case Owner's participant, and a removal that names no participant of the case.
  It also refuses a removal whose participant gives an `attributedTo` other than the actor of the record it names.
  The reason is that each replica finds its own copy of the record by that actor.
  A participant replica accepts it only from the CASE_MANAGER, as the direct notice below, and writes nothing from it.
- **Ledger:** the Case Owner's received `Remove` is the one ledger entry for the removal.
  Every replica applies the removal from that entry, the removed participant's own included.
- **Notice:** the CASE_MANAGER then sends the removed participant a direct `Remove(CaseParticipant)` naming it, with `actor` set to the CASE_MANAGER and `attributedTo` set to the Case Owner.
  The notice is not ledgered.
- **Spec:** [Participant Removal](../vultron-spec/interactions.md#124-participant-removal-n).
- **Example artifact:** [remove_participant_from_case.json](../examples/remove_participant_from_case.json).

{% include-markdown "./_occasions/sections/update-case-owner.md" %}

- **Protocol role:** every change the CASE_MANAGER makes to the case file is its own ledger entry ([CLP-07-013](../vultron-spec/requirements/ledger-replication.md#clp-07-013)).
  An `Update` carrying the case in full is the shape that such an entry takes for a change to a case field.
  The prototype commits one such entry, `update_case_owner`, when an ownership transfer changes the case owner ([CM-21-002](../vultron-spec/requirements/case-management.md#cm-21-002)), and replicas copy it from the ledger fan-out ([§10.2 Routing Topology](../vultron-spec/interactions.md#102-routing-topology)).
  A participant that wants a change made asks the CASE_MANAGER.
  It does not send `Update` to the CASE_MANAGER or to its peers.
- **On receipt:** the activity is recognized, but no use case handles it, so an inbox reports "no use case found" and changes nothing.
- **Triggering transition:** none — metadata change, not a state transition.

{% include-markdown "./_occasions/sections/create-case-participant.md" %}

- **Protocol role:** a participant record comes into existence only as the CASE_MANAGER's consequence of an act it records ([ADR-0137](../../adr/0137-case-records-are-attached-by-one-message-never-created-first.md), VAM-01-011).
  The CASE_MANAGER creates the invitee's participant record when it sends a stub Invite, and commits that creation as its own entry, carrying the record in full ([CLP-07-013](../vultron-spec/requirements/ledger-replication.md#clp-07-013)).
  Replicas copy the record from the ledger fan-out ([§10.2 Routing Topology](../vultron-spec/interactions.md#102-routing-topology)).
  An actor joins a case by accepting its stub Invite (see [Accept Invite to Case](#accept-invite-to-case)).
- **On receipt:** the activity is recognized, but no use case handles it, so an inbox reports "no use case found" and changes nothing (VAM-01-010).
- **Triggering transition:** none — object construction.

{% include-markdown "./_occasions/sections/update-case-participant.md" %}

- **Protocol role:** the CASE_MANAGER commits each participant record it changes as its own entry, after the act that caused the change ([CLP-07-013](../vultron-spec/requirements/ledger-replication.md#clp-07-013)).
  An ownership transfer moves the `CASE_OWNER` role this way, one entry for each record that changed ([CM-21-002](../vultron-spec/requirements/case-management.md#cm-21-002)).
  Replicas store the record as the CASE_MANAGER stored it.
- **On receipt:** the activity is recognized, but no use case handles it, so an inbox reports "no use case found" and changes nothing.
- **Triggering transition:** none — the record changes as the act's consequence.
