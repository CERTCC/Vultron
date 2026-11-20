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

"""BT leaf nodes for the Case Owner's reinstatement, ``Add(<Actor>)`` (CM-31-011).

The Case Owner reinstates a removed participant by sending
``Add(<Actor>, target=<case>)`` to the CASE_MANAGER only, naming the actor as
a typed reference (ADR-0199).  The nodes reuse the removal module's frames:

- read-only precondition guards: the named actor has a participant record on
  the case (the frame), holds neither ``CASE_MANAGER`` nor ``CASE_OWNER``, has
  joined (:class:`ParticipantHasJoinedNode`) and is removed
  (:class:`ParticipantIsRemovedNode`), each refused with a refusal notice
  (CM-31-036);
- one effect, :class:`ClearParticipantRemovalNode`, which clears the removal
  fact without asking the participant to accept again (CM-31-034,
  CM-31-035);
- the announcement of the Owner's act to the reinstated actor
  (:class:`~vultron.core.behaviors.case.nodes.case_participant_received.AnnounceParticipantMoveNode`,
  CM-31-044).
"""

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.case_participant_received import (
    NamedParticipantIsNotProtectedNode,
    ParticipantMoveEffectNode,
    ParticipantMoveGuardNode,
)
from vultron.core.behaviors.case.nodes.ledgered_repeat import (
    ActivityNotYetLedgeredNode,
)
from vultron.core.behaviors.case_id_scope import with_case_id
from vultron.core.models.case_participant import CaseParticipant


class ParticipantHasJoinedNode(ParticipantMoveGuardNode):
    """Guard: the actor a reinstatement names has joined the case.

    An invitee that never accepted its stub Invite is not a member, so there
    is nothing to reinstate: joining is accepting the stub Invite
    (ADR-0114), and a reinstatement must not become a way around it
    (CM-31-036).
    """

    def _check(self, record: CaseParticipant) -> Status:
        if record.joined:
            return Status.SUCCESS
        return self._refuse(
            f"'{self.named_actor_id}' never joined case '{self.case_id}'; it"
            " joins by accepting its stub Invite"
        )


class ParticipantIsRemovedNode(ParticipantMoveGuardNode):
    """Guard: the actor a reinstatement names is removed.

    A reinstatement only clears a removal (ADR-0116), so one naming a
    participant that carries no removal fact is refused, not skipped
    (CM-31-036).  A repeat of a reinstatement the ledger already records is
    skipped before this guard runs
    (:class:`~vultron.core.behaviors.case.nodes.ledgered_repeat.ActivityNotYetLedgeredNode`).
    """

    def _check(self, record: CaseParticipant) -> Status:
        if record.removed:
            return Status.SUCCESS
        return self._refuse(
            f"'{self.named_actor_id}' is not removed from case"
            f" '{self.case_id}'; a reinstatement only clears a removal"
        )


def case_manager_admits_reinstatement_guard(
    case_id: str,
) -> py_trees.composites.Sequence:
    """Precondition guard: the CASE_MANAGER admits the reinstatement.

    The reinstatement twin of
    :func:`~vultron.core.behaviors.case.nodes.case_participant_received.case_manager_admits_removal_guard`:
    the reinstatement declares the manager path alone, so the guards run as
    the tree's own work (HP-01-038).  The CASE_MANAGER runs them in order,
    so a reinstatement it refuses leaves no ledger entry (CM-31-036).  A
    repeat of a reinstatement the ledger already records is skipped first,
    because its participant is no longer removed and the removed check
    would refuse it.
    """
    return py_trees.composites.Sequence(
        name="ReinstatementAdmissible",
        memory=False,
        children=[
            with_case_id(ActivityNotYetLedgeredNode(), case_id),
            with_case_id(
                NamedParticipantIsNotProtectedNode(move="reinstatement"),
                case_id,
            ),
            with_case_id(
                ParticipantHasJoinedNode(move="reinstatement"), case_id
            ),
            with_case_id(
                ParticipantIsRemovedNode(move="reinstatement"), case_id
            ),
        ],
    )


class ClearParticipantRemovalNode(ParticipantMoveEffectNode):
    """Clear the removal fact on the named participant (CM-31-034).

    Calls :meth:`CaseParticipant.clear_removal` on the shared effect frame.
    The participant does not accept again, and its status history and
    embargo consent rows are untouched; whether it is active again is the
    case-level check's answer, so a participant that is not a signatory to
    the active embargo stays inert until it consents (ADR-0116).  The replica
    apply node clears the same fact from the ledger entry (CM-31-045).

    The entry's fan-out, selected before this write, withholds the
    reinstatement entry from the participant and records it in its paused
    stream; the admission backfill that follows sends it (CM-10-006).
    """

    def _apply(self, record: CaseParticipant) -> bool:
        return record.clear_removal()

    def _log_applied(self, record: CaseParticipant) -> None:
        self.logger.info(
            "%s: reinstated '%s' (participant '%s') in case '%s' (CM-31-011)",
            self.name,
            self.named_actor_id,
            record.id_,
            self.case_id,
        )


__all__ = [
    "ClearParticipantRemovalNode",
    "ParticipantHasJoinedNode",
    "ParticipantIsRemovedNode",
    "case_manager_admits_reinstatement_guard",
]
