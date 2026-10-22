#!/usr/bin/env python
#
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
"""Matcher condition nodes for the embargo negotiation's ledger entries.

The CASE_MANAGER's act with a participant's verb and object carries the
participant's semantic type (ADR-0152, SE-03-004), so some entry shapes share
one semantic type and are told apart here, after routing: a proposal from a
relayed Invite by authorship and by whether the replica's register already
holds the embargo (:func:`is_relayed_embargo_invite`), and the CASE_MANAGER's
``Reject`` of a proposal from a participant's by the payload's ``actor``
(:func:`sent_by_case_manager`).  Used as preconditions in the
``AnnounceLogEntryReceivedBT`` embargo slots (EP-09-007, BTND-08-001).
"""

from __future__ import annotations

from typing import Any

from py_trees.common import Status

from vultron.core.behaviors.sync.nodes._event_condition_base import (
    _ActivityEventNode,
    _SingleSemanticTypeNode,
)
from vultron.core.behaviors.sync.nodes._helpers import _extract_id_from_field
from vultron.core.behaviors.sync.nodes.conditions import _require_log_entry
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.wire_keys import wire_key
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.predicates.addressing import snapshot_actor_id
from vultron.core.states.embargo_register import EmbargoRegisterStatus
from vultron.errors import VultronWiringError

# The revision relay's semantic types (EP-09-007, ADR-0113).  The proposal and
# each relayed Invite share one semantic type and are told apart by authorship:
# see :func:`is_relayed_embargo_invite`.
_ATTRIBUTED_TO = wire_key("attributed_to")
_EMBARGO_INVITE_EVENT = MessageSemantics.INVITE_TO_EMBARGO_ON_CASE.value
_ACCEPT_EMBARGO_INVITE_EVENT = (
    MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE.value
)
_REJECT_EMBARGO_INVITE_EVENT = (
    MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE.value
)
_UNDO_EMBARGO_INVITE_EVENT = (
    MessageSemantics.UNDO_INVITE_TO_EMBARGO_ON_CASE.value
)


def _proposes_nothing(
    snapshot: dict[str, Any], case: VulnerabilityCase
) -> bool:
    """True when the Invite names an embargo *case*'s register has left ``PROPOSED``.

    Such an Invite cannot be a proposal: the register already holds the
    embargo it names, decided, so the Invite asks about terms the case has
    (ADR-0152).  It reads the register as it stood before the entry is
    applied, and applying a proposal leaves its entry ``PROPOSED``, so the
    classification of one entry is the same in every slot.
    """
    embargo_id = _extract_id_from_field(snapshot.get("object"))
    if embargo_id is None:
        return False
    held = case.embargo_register_entry(embargo_id)
    return held is not None and held.status != EmbargoRegisterStatus.PROPOSED


def is_relayed_embargo_invite(
    snapshot: dict[str, Any],
    case: VulnerabilityCase | None,
    dl: CasePersistence,
) -> bool:
    """True when an ``invite_to_embargo_on_case`` snapshot is a relayed Invite.

    The CASE_MANAGER commits the proposal it received and then each Invite it
    relays under the same semantic type (EP-09-002).  A relay is the manager's
    own emission on the proposer's behalf: ``actor`` is the CASE_MANAGER and
    ``attributedTo`` names the proposer (CM-24).  When ``attributedTo`` names
    somebody else, that is enough.  When it names the CASE_MANAGER itself,
    because the manager proposed the terms (the protocol default among them),
    the Invite is a relay only when the case's register already holds the
    embargo it names, decided: such an Invite, a re-invite of a late accepter
    (EMB-17-003) or of a reinstated participant (CM-31-013), proposes nothing
    (ADR-0152).  A self-attributed Invite of a still-open proposal stays with
    the proposal slot, whose ``PROPOSE`` is then already in place.  Anything
    else is the proposal — including a proposal whose sender put a third
    party in ``attributedTo``, which only the CASE_MANAGER may do
    (PCR-08-010).

    With no case replica the role holder cannot be resolved; the entry is then
    classified on authorship alone, and the apply nodes skip it leniently
    (Regime 2, ADR-0087), so the classification has no effect.
    """
    actor_id = snapshot_actor_id(snapshot.get("actor"))
    attributed_to = snapshot_actor_id(snapshot.get(_ATTRIBUTED_TO))
    if not actor_id or not attributed_to:
        return False
    if case is None:
        return attributed_to != actor_id
    if resolve_case_manager_id(case, dl) != actor_id:
        return False
    return attributed_to != actor_id or _proposes_nothing(snapshot, case)


def sent_by_case_manager(
    snapshot: dict[str, Any],
    case: VulnerabilityCase | None,
    dl: CasePersistence,
) -> bool:
    """True when the snapshot's ``actor`` is the case's CASE_MANAGER.

    A CASE_MANAGER act with a participant's verb and object carries the
    participant's semantic type (ADR-0152, SE-03-004), so a replica that must
    apply it differently tells the two apart here, after routing.  With no
    case replica the role holder cannot be resolved, and the entry is read as
    a participant's; the apply nodes skip it leniently (Regime 2, ADR-0087).
    """
    actor_id = snapshot_actor_id(snapshot.get("actor"))
    if not actor_id or case is None:
        return False
    return resolve_case_manager_id(case, dl) == actor_id


class _EmbargoInviteEventNode(_ActivityEventNode):
    """Shared match for the two ``invite_to_embargo_on_case`` entry shapes."""

    _match_relay: bool

    def update(self) -> Status:
        entry = _require_log_entry(self.activity, self.name)
        if entry.semantic_type != _EMBARGO_INVITE_EVENT:
            return Status.FAILURE
        if self.datalayer is None:
            # Telling a proposal from a relayed Invite needs the store; a
            # FAILURE here would read as "not this slot" in both Inverters and
            # leave the entry unreplayed with nothing said (a wiring fault).
            raise VultronWiringError(
                f"{self.name}: no DataLayer to classify the"
                f" '{_EMBARGO_INVITE_EVENT}' entry on case"
                f" '{entry.case_id}'"
            )
        case = self._resolve_case_replica(entry.case_id)
        relayed = is_relayed_embargo_invite(
            entry.payload_snapshot, case, self.datalayer
        )
        return (
            Status.SUCCESS if relayed is self._match_relay else Status.FAILURE
        )


class IsEmbargoProposalEventNode(_EmbargoInviteEventNode):
    """Precondition: this entry is the embargo proposal the CASE_MANAGER received.

    Matches an ``invite_to_embargo_on_case`` entry that is *not* a relayed
    Invite (:func:`is_relayed_embargo_invite`).  Used in the
    ``EmbargoProposalEffects`` slot of ``AnnounceLogEntryReceivedBT``.

    Per EP-09-007, RSH-08-004, BTND-08-001, SYNC-12-001.
    """

    _match_relay = False


class IsEmbargoInviteRelayEventNode(_EmbargoInviteEventNode):
    """Precondition: this entry is an Invite the CASE_MANAGER relayed.

    Matches an ``invite_to_embargo_on_case`` entry whose ``actor`` is the
    CASE_MANAGER and whose ``attributedTo`` is the proposer
    (:func:`is_relayed_embargo_invite`).  Used in the
    ``EmbargoInviteRelayEffects`` slot of ``AnnounceLogEntryReceivedBT``.

    Per EP-09-002, EP-09-007, RSH-08-004, BTND-08-001, SYNC-12-001.
    """

    _match_relay = True


class IsAcceptEmbargoInviteEventNode(_SingleSemanticTypeNode):
    """Precondition: this entry is an ``accept_invite_to_embargo_on_case`` event.

    Used in the ``EmbargoAcceptanceEffects`` slot of
    ``AnnounceLogEntryReceivedBT``.

    Per EP-09-007, RSH-08-004, BTND-08-001, SYNC-12-001.
    """

    matched_semantic_type = _ACCEPT_EMBARGO_INVITE_EVENT


class _RejectEmbargoInviteEventNode(_ActivityEventNode):
    """Shared match for the two ``reject_invite_to_embargo_on_case`` entry shapes.

    A participant's ``Reject(Invite(EmbargoEvent))`` is its own consent
    (MSM-07-004); the CASE_MANAGER's is its abandonment of the proposal it
    received, which cancels it (EMB-16-001).  Both carry one semantic type
    (ADR-0152), so the payload's ``actor`` tells them apart
    (:func:`sent_by_case_manager`).
    """

    _match_case_manager: bool

    def update(self) -> Status:
        entry = _require_log_entry(self.activity, self.name)
        if entry.semantic_type != _REJECT_EMBARGO_INVITE_EVENT:
            return Status.FAILURE
        if self.datalayer is None:
            # A FAILURE here would read as "not this slot" in both Inverters
            # and leave the entry unreplayed with nothing said.
            raise VultronWiringError(
                f"{self.name}: no DataLayer to classify the"
                f" '{_REJECT_EMBARGO_INVITE_EVENT}' entry on case"
                f" '{entry.case_id}'"
            )
        case = self._resolve_case_replica(entry.case_id)
        by_manager = sent_by_case_manager(
            entry.payload_snapshot, case, self.datalayer
        )
        return (
            Status.SUCCESS
            if by_manager is self._match_case_manager
            else Status.FAILURE
        )


class IsRejectEmbargoInviteEventNode(_RejectEmbargoInviteEventNode):
    """Precondition: this entry is a participant's ``Reject`` of an embargo Invite.

    Matches a ``reject_invite_to_embargo_on_case`` entry whose ``actor`` is
    not the case's CASE_MANAGER: the sender's own consent, recorded
    ``DECLINED`` (MSM-07-004).  Used in the ``EmbargoRejectionEffects`` slot
    of ``AnnounceLogEntryReceivedBT``.

    Per EP-09-007, RSH-08-004, BTND-08-001, SYNC-12-001.
    """

    _match_case_manager = False


class IsEmbargoAbandonmentEventNode(_RejectEmbargoInviteEventNode):
    """Precondition: this entry is the CASE_MANAGER's ``Reject`` of a proposal.

    Matches a ``reject_invite_to_embargo_on_case`` entry whose ``actor`` is
    the case's CASE_MANAGER: its abandonment of the proposal it received once
    P/X/A is set, which cancels the proposal (EMB-16-001, ADR-0152).  Used in
    the ``EmbargoAbandonmentEffects`` slot of ``AnnounceLogEntryReceivedBT``.

    Per EMB-16-001, EP-09-007, RSH-08-004, BTND-08-001, SYNC-12-001.
    """

    _match_case_manager = True


class IsUndoEmbargoInviteEventNode(_SingleSemanticTypeNode):
    """Precondition: this entry is the CASE_MANAGER's ``Undo`` of an embargo Invite.

    Matches ``undo_invite_to_embargo_on_case``: the CASE_MANAGER's withdrawal
    of an Invite it sent, when it abandons an open proposal (EMB-16-001,
    ADR-0152).  Used in the ``EmbargoInviteWithdrawalEffects`` slot of
    ``AnnounceLogEntryReceivedBT``.

    Per EMB-16-001, EP-09-007, RSH-08-004, BTND-08-001, SYNC-12-001.
    """

    matched_semantic_type = _UNDO_EMBARGO_INVITE_EVENT


__all__ = [
    "IsAcceptEmbargoInviteEventNode",
    "IsEmbargoAbandonmentEventNode",
    "IsEmbargoInviteRelayEventNode",
    "IsEmbargoProposalEventNode",
    "IsRejectEmbargoInviteEventNode",
    "IsUndoEmbargoInviteEventNode",
    "is_relayed_embargo_invite",
    "sent_by_case_manager",
]
