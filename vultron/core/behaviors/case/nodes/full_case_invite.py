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

"""Leaf nodes for the full-case Invite and its three replies (ADR-0121).

After a participant joins, the CASE_MANAGER asks it to judge the case with
``Invite(Actor)[target=VulnerabilityCase]`` carrying the CASE_MANAGER's ledger
tail (CM-11-010).  The participant answers ``Accept`` (RV, ``RECEIVED →
VALID``), ``TentativeReject`` (RI, ``RECEIVED → INVALID``) or ``Reject`` (RC,
``RECEIVED → CLOSED``), each carrying its own ledger position (CM-11-011).

Composed by ``full_case_invite_trees`` (BTND-07-003).
"""

import logging
from typing import cast

from py_trees.common import Status
from pydantic import ValidationError

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.participant.common import (
    resolve_participant_state_from_dl,
)
from vultron.core.behaviors.case.nodes.participant.status import (
    CreateParticipantStatusNode,
)
from vultron.core.behaviors.helpers import (
    DataLayerAction,
    DataLayerCondition,
    _EmitSingleActivityBase,
)
from vultron.core.behaviors.sync.commit_tree import commit_emitted_activity
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.predicates.addressing import same_actor_id
from vultron.core.states.rm import RM, is_valid_rm_transition
from vultron.core.sync_helpers import (
    ledger_position_refusal,
    ledger_tail_position,
)

logger = logging.getLogger(__name__)


def stored_invite_floor(invite: object) -> LedgerPosition | None:
    """The ledger position a stored full-case Invite carries in its ``content``.

    ``None`` when the stored Invite carries none, or one that does not parse
    (the wire layer refused such an Invite at the edge, so a stored one only
    lacks it if it is not a full-case Invite).
    """
    content = getattr(invite, "content", None)
    if not isinstance(content, str) or not content.strip():
        return None
    try:
        return LedgerPosition.model_validate_json(content)
    except ValidationError:
        return None


class LogFullCaseInviteReceivedNode(DataLayerAction):
    """Log the participant's receipt of the full-case Invite at INFO (SL-04-006)."""

    def __init__(
        self,
        invitee_id: str,
        case_id: str,
        sender_id: str,
        floor: LedgerPosition,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.invitee_id = invitee_id
        self.case_id = case_id
        self.sender_id = sender_id
        self.floor = floor

    def update(self) -> Status:
        self.logger.info(
            "Actor '%s' received the full-case Invite for '%s' from '%s'"
            " (ledger floor %d)",
            self.invitee_id,
            self.case_id,
            self.sender_id,
            self.floor.log_index,
        )
        return Status.SUCCESS


class CheckFullCaseReplyNode(DataLayerCondition):
    """Refuse a full-case Invite reply the CASE_MANAGER cannot accept.

    Runs before the receipt is committed, so a refused reply writes nothing
    (CM-11-012).  Only the case's CASE_MANAGER judges a reply: any other
    receiver passes this guard and the CASE_MANAGER-gated stages skip.  The
    reply is refused when:

    - the Invite it answers is not one this CASE_MANAGER issued, or carries
      no ledger position;
    - its sender is not the actor the Invite asked, holds no participant
      record (CM-11-001), or has not joined the case (an inert participant
      may answer only the Invites addressed to it before it joins);
    - its RM state cannot take the transition the reply asks for (a
      duplicate or contradictory reply, CM-11-011), so no receipt is
      committed for a transition the apply stage would refuse;
    - its ledger position is behind the Invite's floor, or names an
      entry the CASE_MANAGER's ledger does not hold at that index.

    The floor is read from the CASE_MANAGER's own stored Invite, never from
    the copy the reply embeds.
    """

    def __init__(
        self,
        case_id: str,
        invite_id: str,
        replier_id: str,
        position: LedgerPosition,
        rm_state: RM,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.invite_id = invite_id
        self.replier_id = replier_id
        self.position = position
        self.rm_state = rm_state

    def _refuse(self, reason: str) -> Status:
        self.feedback_message = reason
        self.logger.warning(
            "%s: refusing full-case reply: %s", self.name, reason
        )
        return Status.FAILURE

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        case = self._resolve_case_replica(self.case_id)
        if case is None or resolve_case_manager_id(case, self.datalayer) != (
            self.actor_id
        ):
            return Status.SUCCESS
        invite = self.datalayer.read(self.invite_id)
        if invite is None or _as_id(getattr(invite, "actor", None)) != (
            self.actor_id
        ):
            return self._refuse(
                f"'{self.invite_id}' is not a full-case Invite this"
                " CASE_MANAGER issued"
            )
        floor = stored_invite_floor(invite)
        if floor is None:
            return self._refuse(
                f"Invite '{self.invite_id}' carries no ledger position"
            )
        if not same_actor_id(
            _as_id(getattr(invite, "object_", None)) or "", self.replier_id
        ):
            return self._refuse(
                f"'{self.replier_id}' is not the actor Invite"
                f" '{self.invite_id}' asked"
            )
        participant_id = case.actor_participant_index.get(self.replier_id)
        participant = (
            self.datalayer.read(participant_id) if participant_id else None
        )
        if not isinstance(participant, CaseParticipant):
            return self._refuse(
                f"'{self.replier_id}' is not a participant of case"
                f" '{self.case_id}'"
            )
        if not participant.joined:
            return self._refuse(
                f"'{self.replier_id}' has not joined case '{self.case_id}';"
                " only a joined participant judges the case (CM-11-010)"
            )
        current_rm, _, _ = resolve_participant_state_from_dl(
            self.datalayer, participant.id_
        )
        if not is_valid_rm_transition(current_rm, self.rm_state):
            return self._refuse(
                f"'{self.replier_id}' is at RM {current_rm.name} and cannot"
                f" move to RM {self.rm_state.name} (CM-11-011)"
            )
        reason = ledger_position_refusal(
            self.case_id,
            self.datalayer,
            position=self.position,
            floor=floor,
        )
        if reason is not None:
            return self._refuse(reason)
        return Status.SUCCESS


class ApplyFullCaseReplyToParticipantNode(DataLayerAction):
    """Record a full-case reply as the participant's RM transition (CM-11-011).

    Writes ``rm_state`` for the replier through the sole ParticipantStatus
    writer, run as the CASE_MANAGER (the store owner) and attributed to the
    replier.  ``CheckFullCaseReplyNode`` has already refused a replier that
    cannot take the transition, before the receipt was committed; the writer
    re-validates it (CSB-16).
    """

    def __init__(
        self,
        case_id: str,
        replier_id: str,
        rm_state: RM,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.replier_id = replier_id
        self.rm_state = rm_state
        # Pre-built once (BTND-10-004).
        self._status_node = CreateParticipantStatusNode(
            actor_id=replier_id,
            rm_state=rm_state,
            vf_state=None,
            d_state=None,
            pxa_state=None,
        )

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None and self.actor_id is not None
        result = BTBridge(datalayer=self.datalayer).execute_with_setup(
            self._status_node, actor_id=self.actor_id, case_id=self.case_id
        )
        if result.status != Status.SUCCESS:
            self.feedback_message = (
                f"could not record RM {self.rm_state.name} for"
                f" '{self.replier_id}' in case '{self.case_id}'"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return result.status
        self.logger.info(
            "%s: participant '%s' moved to RM.%s in case '%s' (CM-11-011)",
            self.name,
            self.replier_id,
            self.rm_state.name,
            self.case_id,
        )
        return Status.SUCCESS


class EmitInviteActorToFullCaseNode(_EmitSingleActivityBase):
    """Create the full-case Invite, commit it, and queue it in the outbox.

    Runs in the CASE_MANAGER-gated accept tree after ``Announce(VulnerabilityCase)``
    and the ledger replay, so it is queued after the last replayed entry and
    delivery to the invitee is ordered behind them (CM-11-010, ADR-0112).  The
    Invite carries the CASE_MANAGER's ledger tail *before* the Invite's own
    entry is committed: the floor the invitee's reply must reach.  Build →
    commit → outbox append, as :class:`EmitInviteActorToCaseNode` does.
    """

    def __init__(
        self,
        case_id: str,
        invitee_id: str,
        captured: dict | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(captured=captured, name=name)
        self.case_id = case_id
        self.invitee_id = invitee_id

    def _already_invited(self) -> bool:
        """Whether this CASE_MANAGER already asked *invitee_id* to judge the case.

        A resumed join re-runs the accept tree; the participant is asked once.
        """
        assert self.datalayer is not None
        for obj in self.datalayer.list_objects("Invite"):
            if (
                _as_id(getattr(obj, "target", None)) == self.case_id
                and stored_invite_floor(obj) is not None
                and _as_id(getattr(obj, "object_", None)) == self.invitee_id
            ):
                return True
        return False

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        if self.trigger_activity_factory is None:
            # As the sibling Announce and Add(CaseParticipant) emit nodes in
            # the accept tree: a join without an outbound factory is logged.
            self.logger.warning(
                "%s: trigger_activity_factory not available; cannot emit the"
                " full-case Invite for case '%s' (CM-11-010)",
                self.name,
                self.case_id,
            )
            return Status.SUCCESS
        if self._already_invited():
            self.logger.info(
                "%s: '%s' was already sent the full-case Invite for case"
                " '%s' — not sending another",
                self.name,
                self.invitee_id,
                self.case_id,
            )
            return Status.SUCCESS
        return super().update()

    def _call_factory(self) -> tuple[str, str]:
        assert self.datalayer is not None and self.actor_id is not None
        assert self.trigger_activity_factory is not None
        tail = ledger_tail_position(self.case_id, self.datalayer)
        activity_id, activity_blob = (
            self.trigger_activity_factory.invite_actor_to_full_case(
                invitee_id=self.invitee_id,
                case_id=self.case_id,
                actor=self.actor_id,
                to=[self.invitee_id],
                ledger_log_index=tail.log_index,
                ledger_entry_hash=tail.entry_hash,
            )
        )
        commit_emitted_activity(
            datalayer=cast(CaseOutboxPersistence, self.datalayer),
            actor_id=self.actor_id,
            case_id=self.case_id,
            activity_id=activity_id,
            activity_blob=activity_blob,
            event_type="invite_actor_to_full_case",
        )
        return activity_id, activity_blob

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        self.logger.info(
            "Actor '%s' emitted the full-case Invite '%s' to '%s' for case"
            " '%s' (CM-11-010)",
            self.actor_id,
            activity_id,
            self.invitee_id,
            self.case_id,
        )
