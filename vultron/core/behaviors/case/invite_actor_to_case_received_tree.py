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

"""Received-side BT factories for the InviteActorToCase workflow.

See CLP-10-001, CLP-10-005, CLP-10-006; Issue #1293, #3821.
"""

import logging

import py_trees

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.act_key_scope import with_act_keys
from vultron.core.behaviors.act_keys import CASE_ID, INVITEE_ID, SENDER_ID
from vultron.core.behaviors.case.nodes.invite_received import (
    LogInviteReceivedNode,
    RecordInviteTrustAnchorNode,
)
from vultron.core.behaviors.case.nodes.invite_reject_participant import (
    ApplyInviteRejectToParticipantNode,
)
from vultron.core.behaviors.case.nodes.owner_invite import (
    case_manager_admits_owner_invite_guard,
    owner_decided_stub_invite,
)
from vultron.core.behaviors.case.nodes.path_branch import OnPaths
from vultron.core.behaviors.case.nodes.received_path import (
    ReceivedPath,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sender_guard import (
    ClosedSenderCheck,
    SenderCheckContext,
)

logger = logging.getLogger(__name__)


def create_reject_invite_actor_to_case_received_tree(
    case_id: str,
    invite_id: str,
    invitee_id: str | None = None,
    *,
    sender_rule: SenderRule,
) -> py_trees.composites.Sequence:
    """Received-side BT for ``Reject(Invite(VulnerabilityCase preview)[target=Actor])``
    on
    the CaseActor inbox.

    Commits the canonical ``CaseLedgerEntry`` for the invite rejection when the
    receiving actor holds ``CVDRole.CASE_MANAGER`` (CLP-10-006).  When
    ``invitee_id`` is supplied, also applies the reject effects to the inert
    participant record: RM ``CLOSED``, VF ``Vf``, PEC ``DECLINED`` (when an
    embargo is in force) — AC-3 (CM-11-007, CM-11-009, ADR-0114).

    The sender must be the invitee of the stub Invite this store recorded for
    the case, or the Reject is refused before anything is written (CM-11-017,
    HP-01-006, ADR-0115).  The factory composes that guard from the use
    case's declared rule (HP-01-008); the handler refuses a Reject that names
    no case before it builds this tree, so the rule needs no side for an
    activity outside any case.

    Args:
        case_id: ID of the VulnerabilityCase referenced by the invite; never
            empty.
        invitee_id: Actor ID of the rejecting invitee (the reply's sender).
            Required for AC-3 effects; omit only when the invitee cannot be
            resolved, in which case the sender guard refuses.
        invite_id: ID of the recorded stub Invite the Reject answers.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-025).

    Returns:
        Root ``RejectInviteActorToCaseReceivedBT`` Sequence node.
    """
    manager_effects: list[py_trees.behaviour.Behaviour] = []
    if invitee_id:
        manager_effects.append(
            ApplyInviteRejectToParticipantNode(
                case_id=case_id,
                invitee_id=invitee_id,
            )
        )

    return create_receive_activity_tree(
        name="RejectInviteActorToCaseReceivedBT",
        # The invitee rejects to the CASE_MANAGER that invited it, which alone
        # closes the inert record (CM-11-007, PCR-08-001), so the manager path
        # is the only one this type handles (HP-01-038).
        paths={ReceivedPath.CASE_MANAGER},
        case_id=case_id,
        precondition_guards=[],
        sender_rule=sender_rule,
        # A Reject closes its invitee: the handler reads a repeat from one
        # the case already records as closed as SKIPPED (CM-23-049,
        # ID-05-003).
        closed_sender=ClosedSenderCheck(
            sender_id=invitee_id or "", closes=True
        ),
        sender_context=SenderCheckContext(
            sender_id=invitee_id or "",
            case_id=case_id,
            invite_id=invite_id,
            invite_is_case_join=True,
        ),
        manager_effects=manager_effects,
        manager_case_id=case_id if manager_effects else None,
        manager_gate_name=(
            "RejectInviteApplyEffects" if manager_effects else None
        ),
    )


def create_invite_actor_to_case_received_tree(
    case_id: str,
    invitee_id: str,
    inviter_id: str,
    invite_id: str,
    roles: list[str] | None = None,
    actor_config: ActorConfig | None = None,
    *,
    sender_rule: SenderRule,
) -> py_trees.composites.Sequence:
    """Received-side BT for ``Invite(VulnerabilityCase preview)[target=Actor]`` — one
    tree for every receiver.

    The Case Owner's decision to invite and the CASE_MANAGER's stub Invite
    share one wire shape: ``object`` the case preview, ``target`` the
    invitee (ADR-0199, ADR-0205).  The path the receiver is on tells them
    apart (HP-01-038):

    - **At the CASE_MANAGER**, the Invite is the Case Owner's own, sent to it
      and naming another actor in ``target`` (CM-17-007).  The CASE_MANAGER
      refuses it with the refusal notice when the sender is not the Case
      Owner, the ``target`` is the CASE_MANAGER or the Owner, the invitee is
      removed, joined or at ``RM.CLOSED``, or the roles are empty or name an
      authority role (:func:`case_manager_admits_owner_invite_guard`).
      Otherwise it commits the Owner's Invite as one ledger entry and sends
      its own stub Invite, ``attributedTo`` the Owner and ``inReplyTo`` the
      Owner's Invite (CM-24-002, CM-24-020, PCR-08-007), which it commits
      once it is in the outbox (CM-17-006).  A re-invite of an invitee that
      has not answered names the stub it supersedes instead (CM-11-044).
    - **Elsewhere**, the receiver is the invitee, holding only the Invite's
      case stub (MV-10-004), and the sender must be the case's CASE_MANAGER
      (PCR-03-001)::

        InviteActorToCaseReceivedBT (Sequence)
        ├── ActivityAddressedToReceiver  # addressee door guard (HP-01-005)
        ├── ActivityNotSeenBeforeNode    # seen-before door (ADR-0154)
        ├── ReceivedPathNode             # no case yet, a replica, or manager
        ├── CaseOpenToExternalWrites     # post-close boundary (CM-23-013)
        ├── <sender guard>               # composed from the declared rule
        ├── Intake                       # stores the Invite idempotently
        ├── OwnerInviteAdmissible        # CASE_MANAGER only
        ├── GuardedCommitCaseLedgerEntryBT   # CASE_MANAGER only — skips here
        ├── InviteeRecordsInvite         # not the CASE_MANAGER
        │   ├── LogInviteReceivedNode        # SL-04-006
        │   └── RecordInviteTrustAnchorNode  # PCR-03-004
        └── OwnerDecidedStubInvite       # CASE_MANAGER only

    The path stage declares the no-case branch the invitee takes, so the
    Invite is admitted at a receiver that holds no replica rather than
    waiting for one (HP-01-041, HP-01-012).  Both gates read a case
    the receiver does not hold as "not the CASE_MANAGER"
    (``case_may_be_absent``), because an invitee has no replica until the
    case is announced.

    The factory composes the sender guard from the use case's declared rule
    (HP-01-008).  An invitee holding only the case's preview has no
    CASE_MANAGER to compare against, so the guard passes there (the
    bootstrap window) and the trust-anchor rules of PCR-03-004 decide what
    the Invite may record.

    Args:
        case_id: ID of the case the Invite's ``object`` names (ADR-0205).
        invitee_id: The invited actor (the Invite's ``target``).
        inviter_id: The Invite's sender: the Case Owner at the CASE_MANAGER,
            the case's expected CASE_MANAGER at the invitee.
        invite_id: The Invite's id, recorded so the invitee's Accept of it
            can fix the anchor (PCR-03-004); at the CASE_MANAGER, the request
            its stub Invite carries out.
        roles: The roles the Invite offers the invitee (CM-17-003).
        actor_config: The receiving CASE_MANAGER's configuration; its RSVP
            windows set the stub Invite's reply deadline (CM-11-014).
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-025).

    Returns:
        Root ``InviteActorToCaseReceivedBT`` Sequence node.
    """
    # The keys the CASE_MANAGER's nodes read for the Owner's Invite
    # (BTND-01-008).
    owner_keys = {
        CASE_ID: case_id,
        INVITEE_ID: invitee_id,
        SENDER_ID: inviter_id,
    }
    return create_receive_activity_tree(
        name="InviteActorToCaseReceivedBT",
        case_id=case_id,
        precondition_guards=[
            # The CASE_MANAGER's adjudication of the Owner's decision; an
            # invitee judges nothing here (HP-01-038).
            OnPaths.at_case_manager(
                "OwnerInviteAdmissibleAtCaseManager",
                with_act_keys(
                    case_manager_admits_owner_invite_guard(roles), owner_keys
                ),
            )
        ],
        # The stub Invite precedes its case (MV-10-004), so the invitee is
        # on the no-case path and this is the type that declares that
        # branch and takes it (HP-01-041): the inbox's defer check
        # exempts the stub Invite rather than holding it for a case that
        # only the answer brings.  An invitee that already holds a replica
        # takes the participant path, and the Case Owner's own Invite takes
        # the manager path at the CASE_MANAGER it is addressed to
        # (CM-17-007).  All three are handled, so the stage refuses none of
        # them and only chooses which arms run.
        paths={
            ReceivedPath.NO_CASE,
            ReceivedPath.PARTICIPANT_REPLICA,
            ReceivedPath.CASE_MANAGER,
        },
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=inviter_id, case_id=case_id
        ),
        replica_effects=[
            # The invitee's own record of the Invite, on every declared
            # path but the manager's: the CASE_MANAGER is never invited by
            # an Invite it receives, so it anchors no trust in it
            # (HP-01-038, PCR-03-004).  The branch reads the path the stage
            # resolved rather than asking the roster again (HP-01-036).
            OnPaths.off_case_manager(
                "InviteeRecordsInvite",
                LogInviteReceivedNode(
                    invitee_id=invitee_id,
                    case_id=case_id,
                    sender_id=inviter_id,
                ),
                RecordInviteTrustAnchorNode(
                    case_id=case_id,
                    invitee_id=invitee_id,
                    case_actor_id=inviter_id,
                    invite_id=invite_id,
                ),
            ),
        ],
        manager_effects=[
            with_act_keys(
                owner_decided_stub_invite(
                    list(roles or []),
                    credits_sender=True,
                    actor_config=actor_config,
                ),
                owner_keys,
            )
        ],
        manager_case_id=case_id,
        manager_gate_name="OwnerInviteIfCaseManager",
        manager_body_name="OwnerInviteEffects",
        manager_case_may_be_absent=True,
        case_may_be_absent=True,
    )
