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

"""BT leaf nodes for a received ``Add(CaseParticipant)``: reinstatement (CM-31-011).

``Add(CaseParticipant, target=VulnerabilityCase)`` is the Case Owner's request
to the CASE_MANAGER to reinstate a removed participant, and only that
(ADR-0116, VAM-06-002).  It mirrors the removal pipeline in
:mod:`~vultron.core.behaviors.case.nodes.case_participant_received`, reusing
its guard, effect and notice frames:

- three read-only precondition guards — the named participant is on the
  roster (:class:`MoveNamesCaseParticipantNode`, shared), has joined, and
  is removed; each failure is ``REFUSED``, so ``Add`` never seats a member
  (joining is accepting a stub Invite, ADR-0114);
- one effect, :class:`ReinstateCaseParticipantReceivedNode`, which clears
  the removal fact through :meth:`CaseParticipant.clear_removal`;
- the direct notice to the reinstated participant,
  :class:`EmitParticipantReinstatementNoticeNode`, which is not ledgered.

Composite tree factories assembling these nodes are in
``case_participant_received_tree.py`` at the process-area root per
BTND-07-003.
"""

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.case_participant_received import (
    EmitParticipantMoveNoticeNode,
    MoveNamesCaseParticipantNode,
    ParticipantMove,
    ParticipantMoveEffectNode,
    ParticipantMoveGuardNode,
)
from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.ports.trigger_activity import TriggerActivityPort


class ParticipantHasJoinedNode(ParticipantMoveGuardNode):
    """Guard: the participant an ``Add(CaseParticipant)`` names has joined.

    An invitee that never accepted its stub Invite is not a member, so there
    is nothing to reinstate: joining is accepting the stub Invite
    (ADR-0114), and ``Add`` must not become a way around it (CM-31-011).
    """

    def _check(self, record: CaseParticipant) -> Status:
        if record.joined:
            return Status.SUCCESS
        return self._refuse(
            f"participant '{self.participant_id}' never joined case"
            f" '{self.case_id}'; it joins by accepting its stub Invite"
        )


class ParticipantIsRemovedNode(ParticipantMoveGuardNode):
    """Guard: the participant an ``Add(CaseParticipant)`` names is removed.

    ``Add`` only reinstates (CM-31-011, VAM-06-002), so an ``Add`` naming a
    participant that carries no removal fact is refused, not skipped: it is
    not a repeat of an earlier reinstatement the CASE_MANAGER could tell
    apart from a request to seat a member.
    """

    def _check(self, record: CaseParticipant) -> Status:
        if record.removed:
            return Status.SUCCESS
        return self._refuse(
            f"participant '{self.participant_id}' of case '{self.case_id}'"
            " is not removed; Add(CaseParticipant) only reinstates"
        )


def case_manager_admits_reinstatement_guard(
    participant_id: str,
    case_id: str,
    claimed_actor_id: str | None = None,
) -> py_trees.composites.Selector:
    """Precondition guard: when this actor is the CASE_MANAGER, the reinstatement is admissible.

    The reinstatement twin of :func:`case_manager_admits_removal_guard`: a
    replica skips it as ``SUCCESS`` (it writes nothing, RSH-08-003), and the
    CASE_MANAGER runs the three reinstatement guards in order, so an ``Add``
    it refuses leaves no ledger entry (CM-31-011).  *claimed_actor_id* is the
    actor the inline participant is attributed to, when it names one.
    """
    return create_case_manager_gated_tree(
        name="ReinstatementAdmissibleIfCaseManager",
        case_id=case_id,
        body_name="ReinstatementAdmissible",
        children=[
            MoveNamesCaseParticipantNode(
                participant_id=participant_id,
                case_id=case_id,
                claimed_actor_id=claimed_actor_id,
                move="reinstatement",
            ),
            ParticipantHasJoinedNode(
                participant_id=participant_id,
                case_id=case_id,
                move="reinstatement",
            ),
            ParticipantIsRemovedNode(
                participant_id=participant_id,
                case_id=case_id,
                move="reinstatement",
            ),
        ],
    )


class ReinstateCaseParticipantReceivedNode(ParticipantMoveEffectNode):
    """Clear the removal fact on the named participant (CM-31-011).

    Calls :meth:`CaseParticipant.clear_removal` on the shared effect frame.
    The participant does not accept again, and its status history and
    embargo consent rows are untouched; whether it is active again is the
    case-level check's answer, so a participant that is not a signatory to
    the active embargo stays inert until it consents (ADR-0116).  The replica
    apply node clears the same fact from the ledger entry.

    The entry's fan-out, selected before this write, withholds the
    reinstatement entry from the participant and records it in its paused
    stream; the admission backfill that follows sends it (CM-10-006).
    """

    def _apply(self, record: CaseParticipant) -> bool:
        return record.clear_removal()

    def _log_applied(self) -> None:
        self.logger.info(
            "%s: reinstated participant '%s' in case '%s' (CM-31-011)",
            self.name,
            self.participant_id,
            self.case_id,
        )


class EmitParticipantReinstatementNoticeNode(EmitParticipantMoveNoticeNode):
    """Send the reinstated participant its direct ``Add(CaseParticipant)`` notice.

    The reinstated participant learns the reinstatement as case state from
    the reinstatement entry, which the admission backfill sends it once it
    is active (CM-10-006); its replica applies that entry, not this notice
    (RSH-08-003).  The notice reaches an inert participant too — one that is
    not a signatory to the active embargo — because it carries only the
    participant's own record, no other case content.
    """

    _MOVE: ParticipantMove = "reinstatement"

    def _send(
        self,
        trigger_activity: TriggerActivityPort,
        actor: str,
        attributed_to: str,
        to: list[str],
    ) -> tuple[str, str]:
        return trigger_activity.add_participant_to_case(
            participant_id=self.participant_id,
            case_id=self.case_id,
            actor=actor,
            attributed_to=attributed_to,
            to=to,
        )


__all__ = [
    "EmitParticipantReinstatementNoticeNode",
    "ParticipantHasJoinedNode",
    "ParticipantIsRemovedNode",
    "ReinstateCaseParticipantReceivedNode",
    "case_manager_admits_reinstatement_guard",
]
