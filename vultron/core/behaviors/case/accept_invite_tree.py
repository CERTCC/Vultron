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

When the CaseActor receives ``Accept(Invite(actor, case))``, it runs this tree
as itself (the CaseActor) to record the invitee's participation in its own
DataLayer — without spoofing the invitee's identity (PCR-08-010).

Tree structure::

    AcceptInviteActorToCaseBT (Sequence, memory=False)
    ├── CheckInviteeNotAlreadyParticipantNode  — idempotency guard
    ├── CapturePreCommitBackfillTargetNode     — snapshot ledger for resume case
    ├── GuardedCommitCaseLedgerEntryBT         — record receipt (CLP-10-006)
    ├── CreateInviteeParticipantNode           — construct participant at RM.START
    ├── MaybeSignEmbargoConsentNode            — sign when embargo is EM.ACTIVE
    ├── PersistInviteeParticipantNode          — dl.create, attach, save case
    ├── AdvanceInviteeToReceivedNode           — advance to RM.RECEIVED via writer
    ├── EmitAddCaseParticipantNode             — emit Add(CaseParticipant), commit ledger
    ├── EmitAnnounceCaseToInviteeNode          — queue Announce(VulnerabilityCase)
    └── BackfillCanonicalLedgerToInviteeNode   — send prior ledger to invitee

Specs: PCR-08-010 (identity constraint), CM-10-001/CM-10-003 (embargo
consent), MV-10-003/MV-10-005 (announce after consent resolved).
BT-06-001, BT-15-001.
"""

import py_trees

from vultron.core.behaviors.case.nodes import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.case.nodes.accept_invite import (
    EmitAddCaseParticipantNode,
)
from vultron.core.behaviors.case.nodes.invite_embargo_consent import (
    _CheckEmbargoActiveStateNode,
    _SignEmbargoConsentLeafNode,
)
from vultron.core.behaviors.case.nodes.invite_ledger_backfill import (
    BackfillCanonicalLedgerToInviteeNode,
    CapturePreCommitBackfillTargetNode,
    EmitAnnounceCaseToInviteeNode,
)
from vultron.core.behaviors.case.nodes.invite_participant import (
    CheckInviteeNotAlreadyParticipantNode,
    CreateInviteeParticipantNode,
)
from vultron.core.behaviors.case.nodes.invite_participant_persist import (
    AdvanceInviteeToReceivedNode,
    PersistInviteeParticipantNode,
)


class MaybeSignEmbargoConsentNode(py_trees.composites.Selector):
    """Auto-sign embargo consent when the case embargo is fully EM.ACTIVE.

    Selector logic:
    - ``_TrySignEmbargoConsent`` (Sequence): sign if embargo is EM.ACTIVE.
    - ``_AlwaysSucceed`` (leaf): fall-through so the parent Sequence can
      continue when there is no active embargo or it is in REVISE state.

    Only auto-signs when ``em_state == EM.ACTIVE`` — REVISE means terms
    are being renegotiated and the new participant should not be committed.
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
) -> py_trees.composites.Sequence:
    """Return the BT for handling an inbound ``Accept(Invite(actor, case))``.

    The CaseActor runs this tree **as itself** (not as the invitee) to record
    the invitee's participation in its own DataLayer (PCR-08-010).

    The returned Sequence::

        AcceptInviteActorToCaseBT (memory=False)
        ├── CheckInviteeNotAlreadyParticipantNode  — idempotency guard
        ├── CapturePreCommitBackfillTargetNode     — snapshot ledger for resume case
        ├── GuardedCommitCaseLedgerEntryBT         — record receipt (CLP-10-006)
        ├── CreateInviteeParticipantNode           — construct participant at RM.START
        ├── MaybeSignEmbargoConsentNode            — sign when EM.ACTIVE
        ├── PersistInviteeParticipantNode          — persist, attach, save case
        ├── AdvanceInviteeToReceivedNode           — advance to RM.RECEIVED via writer
        ├── EmitAddCaseParticipantNode             — emit Add(CaseParticipant), commit ledger
        ├── EmitAnnounceCaseToInviteeNode          — queue Announce to invitee
        └── BackfillCanonicalLedgerToInviteeNode   — send prior ledger to invitee

    The idempotency guard ``CheckInviteeNotAlreadyParticipantNode`` uses
    :class:`~vultron.core.behaviors.idempotency.SilentIdempotencyGuardMixin`
    to enforce CLP-13-001: when a true duplicate is detected (invitee already
    joined AND backfill is complete), the guard returns ``Status.FAILURE`` with
    an INFO log and no ledger write.  When backfill is incomplete, it returns
    SUCCESS with ``invitee_already_participant = True`` so the tree continues
    to the commit + backfill steps without re-creating the participant.

    Args:
        case_id: ID of the VulnerabilityCase the invitee accepted.
        invitee_id: Actor ID of the actor who accepted the invitation.

    Returns:
        Configured ``Sequence`` ready for execution via
        :class:`~vultron.core.behaviors.bridge.BTBridge`.
    """
    return create_receive_activity_tree(
        name="AcceptInviteActorToCaseBT",
        case_id=case_id,
        precondition_guards=[
            CheckInviteeNotAlreadyParticipantNode(
                case_id=case_id, invitee_id=invitee_id
            ),
            CapturePreCommitBackfillTargetNode(case_id=case_id),
        ],
        effect_nodes=[
            CreateInviteeParticipantNode(
                case_id=case_id, invitee_id=invitee_id
            ),
            MaybeSignEmbargoConsentNode(
                case_id=case_id, invitee_id=invitee_id
            ),
            PersistInviteeParticipantNode(
                case_id=case_id, invitee_id=invitee_id
            ),
            AdvanceInviteeToReceivedNode(
                case_id=case_id, invitee_id=invitee_id
            ),
            EmitAddCaseParticipantNode(case_id=case_id, invitee_id=invitee_id),
            EmitAnnounceCaseToInviteeNode(
                case_id=case_id, invitee_id=invitee_id
            ),
            BackfillCanonicalLedgerToInviteeNode(
                case_id=case_id, invitee_id=invitee_id
            ),
        ],
    )


__all__ = [
    "MaybeSignEmbargoConsentNode",
    "create_accept_invite_actor_to_case_tree",
]
