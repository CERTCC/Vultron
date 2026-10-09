#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""BT nodes and factory for AcceptInviteActorToCase received use-case.

When the CASE_MANAGER receives ``Accept(Invite(actor, case))``, it runs this
tree as itself to record the invitee's participation in its own DataLayer —
without spoofing the invitee's identity (PCR-08-010, PCR-08-009).

Tree structure::

    AcceptInviteActorToCaseBT (Sequence, memory=False)
    ├── SenderIsInviteeNode                    — sender is the recorded invitee
    ├── CheckInviteeNotAlreadyParticipantNode  — idempotency guard
    ├── InviteeHasParticipantRecordNode        — refuse when no record (CM-11-021)
    ├── StubInviteAnswerableNode               — not superseded
    ├── CapturePreCommitBackfillTargetNode     — snapshot ledger for resume case
    ├── GuardedCommitCaseLedgerEntryBT         — record receipt (CLP-10-006)
    └── AcceptInviteIfCaseManager (Selector)   — BT-17-001 gate
        ├── SkipIfNotCaseManager               — Inverter(CheckIsCaseManagerNode)
        └── AcceptInviteEffects (Sequence, memory=False)
            ├── MaybeSignEmbargoConsentNode          — sign when an embargo is in force
            ├── ActivateInviteeParticipantNode       — mark the inert record joined
            ├── AdvanceInviteeVFToVendorAwareNode    — record VF Vf for VENDOR (CM-11-009)
            ├── EmitAnnounceCaseToInviteeNode        — queue Announce(VulnerabilityCase)
            ├── BackfillCanonicalLedgerToInviteeNode — send prior ledger to invitee
            ├── EmitInviteActorToFullCaseNode        — full-case Invite, ledger tail (CM-11-010)
            └── RelayOpenProposalsToJoinerNode       — Invite to each open embargo proposal (EP-09-011)

Admitting the invitee, announcing the case to it and backfilling the ledger
are the CASE_MANAGER's (PCR-08-009); every other participant learns of the
new member from the stub Invite's entry (``ApplyStubInviteFromLedgerNode``
creates the inert record) and the ``Accept(Invite)`` entry's fan-out (its
replica marks the record joined through ``ApplyInviteAcceptFromLedgerNode``).
No ``Add(CaseParticipant)`` follows and no ``add_case_participant`` entry is
committed: that message now means reinstatement only (CM-31-012, ADR-0116).
The same handler runs on any actor that holds a copy of the Accept, so the
effects sit behind a role gate and a receiver that is not the case's
CASE_MANAGER does nothing (#3752).

Specs: PCR-08-009/PCR-08-010 (who records, identity constraint),
CM-10-001/CM-10-003 (embargo consent), MV-10-003/MV-10-005 (announce after
consent resolved). BT-06-001, BT-15-001, BT-17-001.
"""

import py_trees

from vultron.core.behaviors.case.nodes.full_case_invite import (
    EmitInviteActorToFullCaseNode,
)
from vultron.core.behaviors.case.nodes.invite_embargo_consent import (
    _CheckEmbargoActiveStateNode,
    _SignEmbargoConsentLeafNode,
)
from vultron.core.behaviors.case.nodes.invite_inert_participant import (
    AdvanceInviteeVFToVendorAwareNode,
)
from vultron.core.behaviors.case.nodes.invite_ledger_backfill import (
    BackfillCanonicalLedgerToInviteeNode,
    CapturePreCommitBackfillTargetNode,
    EmitAnnounceCaseToInviteeNode,
)
from vultron.core.behaviors.case.nodes.invite_participant import (
    CheckInviteeNotAlreadyParticipantNode,
    InviteeHasParticipantRecordNode,
)
from vultron.core.behaviors.case.nodes.invite_participant_persist import (
    ActivateInviteeParticipantNode,
)
from vultron.core.behaviors.case.nodes.invite_revision_relay import (
    RelayOpenProposalsToJoinerNode,
)
from vultron.core.behaviors.case.nodes.stub_invite_lifetime import (
    StubInviteAnswerableNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_entitlement import SenderIsInviteeNode


class MaybeSignEmbargoConsentNode(py_trees.composites.Selector):
    """Auto-sign embargo consent to the embargo in force.

    Selector logic:
    - ``_TrySignEmbargoConsent`` (Sequence): sign if the case has an active
      embargo — EM ``ACTIVE``, or ``REVISE`` while the prior terms still hold.
    - ``_AlwaysSucceed`` (leaf): fall-through so the parent Sequence can
      continue when there is no active embargo.

    During ``REVISE`` the joiner signs the terms *in force*, never the open
    revision.  Not signing would leave it inert (CM-10-004) under terms that
    still hold.  One difference from the other signatories remains: the
    revision Invite was relayed (EP-09-002) before this joiner was on the
    roster, so the relay never reached it.  ``RelayOpenProposalsToJoinerNode``
    closes that gap at the end of the accept effects (EP-09-011): the joiner
    is sent an Invite for each open proposal, so it can accept the revision
    and be a signatory of it at activation, or lapse per ADR-0093.
    """

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(
            name=name or self.__class__.__name__,
            memory=False,
            children=[
                _TrySignEmbargoConsentSequence(
                    case_id=case_id, invitee_id=invitee_id
                ),
                py_trees.behaviours.Success(name="_AlwaysSucceed"),
            ],
        )


class _TrySignEmbargoConsentSequence(py_trees.composites.Sequence):
    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(
            name=name or "_TrySignEmbargoConsent",
            memory=False,
            children=[
                _CheckEmbargoActiveStateNode(case_id=case_id),
                _SignEmbargoConsentLeafNode(invitee_id=invitee_id),
            ],
        )


def create_accept_invite_actor_to_case_tree(
    case_id: str,
    invitee_id: str,
    invite_id: str,
) -> py_trees.composites.Sequence:
    """Return the BT for handling an inbound ``Accept(Invite(actor, case))``.

    The CASE_MANAGER runs this tree **as itself** (not as the invitee) to
    record the invitee's participation in its own DataLayer (PCR-08-009,
    PCR-08-010).

    The returned Sequence::

        AcceptInviteActorToCaseBT (memory=False)
        ├── SenderIsInviteeNode                    — sender is the recorded invitee
        ├── CheckInviteeNotAlreadyParticipantNode  — idempotency guard
        ├── InviteeHasParticipantRecordNode        — refuse an Accept with no record (CM-11-021)
        ├── StubInviteAnswerableNode               — not superseded
        ├── CapturePreCommitBackfillTargetNode     — snapshot ledger for resume case
        ├── GuardedCommitCaseLedgerEntryBT         — record receipt (CLP-10-006)
        └── AcceptInviteIfCaseManager              — BT-17-001 gate (#3752)
            └── AcceptInviteEffects (memory=False)
                ├── MaybeSignEmbargoConsentNode          — sign when an embargo is in force
                ├── ActivateInviteeParticipantNode       — mark the inert record joined
                ├── EmitAnnounceCaseToInviteeNode        — queue Announce to invitee
                ├── BackfillCanonicalLedgerToInviteeNode — send prior ledger to invitee
                ├── EmitInviteActorToFullCaseNode        — full-case Invite with the ledger tail (CM-11-010)
                └── RelayOpenProposalsToJoinerNode       — Invite to each open embargo proposal (EP-09-011)

    The announce, backfill and full-case Invite follow CM-17-004 steps (3)
    and (4): the invitee receives the case snapshot, then the prior ledger in
    log-index order, and only then the first entry committed after it joined —
    the full-case Invite's, whose fan-out reaches the invitee too, because
    ``ActivateInviteeParticipantNode`` has already made it active.  Any
    committing node placed earlier hands the late joiner a ledger entry before
    its case seed (SYNC-15 pre-genesis reject and replay, #2898).  The
    stub-Invite acceptance commits no ``add_case_participant`` entry
    (CM-31-012): replicas seat the inert record from the stub Invite's entry and
    mark it joined from the ``Accept(Invite)`` entry.

    The idempotency guard ``CheckInviteeNotAlreadyParticipantNode`` uses
    :class:`~vultron.core.behaviors.idempotency.SilentIdempotencyGuardMixin`
    to enforce CLP-13-001: when a true duplicate is detected (invitee already
    joined AND backfill is complete), the guard returns ``Status.FAILURE`` with
    an INFO log and no ledger write.  When backfill is incomplete, it returns
    SUCCESS with ``invitee_already_participant = True`` so the tree continues
    to the commit + backfill steps without re-creating the participant.

    The sender guard refuses an Accept unless its sender is the invitee of the
    stub Invite this store recorded for the case, before anything is written
    (CM-11-017, HP-01-006, ADR-0115).

    Args:
        case_id: ID of the VulnerabilityCase the invitee accepted.
        invitee_id: Actor ID of the actor who accepted the invitation (the
            reply's sender).
        invite_id: ID of the recorded stub Invite being accepted; its roles,
            not the reply's embedded copy, become the participant's.

    Returns:
        Configured ``Sequence`` ready for execution via
        :class:`~vultron.core.behaviors.bridge.BTBridge`.
    """
    return create_receive_activity_tree(
        name="AcceptInviteActorToCaseBT",
        case_id=case_id,
        sender_guard=SenderIsInviteeNode(
            invite_id=invite_id,
            sender_actor_id=invitee_id,
            case_id=case_id,
        ),
        precondition_guards=[
            CheckInviteeNotAlreadyParticipantNode(
                case_id=case_id, invitee_id=invitee_id
            ),
            # An Accept never creates a participant: the record exists from
            # the stub Invite, and none means refuse before any write
            # (CM-11-021).
            InviteeHasParticipantRecordNode(
                case_id=case_id, invitee_id=invitee_id
            ),
            # A superseded stub cannot be accepted (CM-11-016); an expired one
            # can (ASK-03-008).  A redelivery of a joined invitee's Accept
            # already ended the tree above, so this never refuses a duplicate.
            StubInviteAnswerableNode(invite_id=invite_id, case_id=case_id),
            CapturePreCommitBackfillTargetNode(case_id=case_id),
        ],
        manager_effects=[
            MaybeSignEmbargoConsentNode(
                case_id=case_id, invitee_id=invitee_id
            ),
            ActivateInviteeParticipantNode(
                case_id=case_id, invitee_id=invitee_id
            ),
            AdvanceInviteeVFToVendorAwareNode(
                case_id=case_id, invitee_id=invitee_id
            ),
            # CM-17-004 step (3): seed the invitee's case,
            # then backfill the prior ledger in log-index order.
            EmitAnnounceCaseToInviteeNode(
                case_id=case_id, invitee_id=invitee_id
            ),
            BackfillCanonicalLedgerToInviteeNode(
                case_id=case_id, invitee_id=invitee_id
            ),
            # CM-17-004 step (4): the full-case Invite, queued after
            # the last replayed entry so its ledger tail is the floor
            # the invitee must reach before it answers (CM-11-010,
            # ADR-0121).  It is also the first node after the join that
            # commits an entry, and that commit fans out to the invitee,
            # active since ActivateInviteeParticipantNode.  Placed before
            # the announce it would hand the invitee a ledger entry for
            # a case it does not hold yet (SYNC-15 pre-genesis Reject,
            # then a from-genesis replay interleaved with the backfill —
            # fcvcv V2/C2, #2898); placed between announce and backfill
            # it would arrive as a forward gap ahead of the entries it
            # extends.  Here it reaches the invitee as the next entry in
            # chain order.  No Add(CaseParticipant) precedes it
            # (CM-31-012).
            EmitInviteActorToFullCaseNode(
                case_id=case_id, invitee_id=invitee_id
            ),
            # EP-09-011: the joiner was not on the roster when any
            # open proposal was relayed, so it is invited now, after
            # it holds the case and the ledger.  Its commits fan out to
            # the joiner too, so it stays after the backfill for the
            # same #2898 reason.
            RelayOpenProposalsToJoinerNode(
                case_id=case_id, invitee_id=invitee_id
            ),
        ],
        manager_case_id=case_id,
        manager_gate_name="AcceptInviteIfCaseManager",
        manager_body_name="AcceptInviteEffects",
    )


__all__ = [
    "MaybeSignEmbargoConsentNode",
    "create_accept_invite_actor_to_case_tree",
]
