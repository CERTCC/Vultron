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

"""Does a named actor hold a role in a case? (ADR-0153, CM-02-011)

:class:`ActorHoldsRoleInCaseNode` asks that of an actor the tree names — an
invitee, a subject, an answerer — through
:func:`~vultron.core.participants.role_predicate.has_role`, the one sanctioned
way to ask.  Every role but ``CVDRole.CASE_MANAGER`` is a permission rule
*inside* a received path rather than a path of its own (HP-01-037), and this
is how a tree checks one.

It is not the sender guard and not the path stage.  The sender guard asks
about the activity's sender and is composed once per use case
(HP-01-006, HP-01-007); the path stage asks about the *receiver's*
``CVDRole.CASE_MANAGER`` role, once per message (HP-01-035).  This node asks
about neither, so it is the right shape only for an actor the message names.

``CVDRole.CASE_MANAGER`` is refused at construction, for that reason: asked
about the executing actor it would be a second authority condition node, which
ARCH-24-003 allows exactly one of, and a role passed as a parameter is invisible
to the detector both authority ratchets share
(``test/architecture/_authority_question.py``).  Authority is the path stage's
question (HP-01-037) and the gate's (BT-17-001); nothing else asks it.
"""

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.participants.role_predicate import has_role
from vultron.enums.roles import CVDRole
from vultron.errors import VultronWiringError

__all__ = ["ActorHoldsRoleInCaseNode"]


class ActorHoldsRoleInCaseNode(DataLayerConditionWithPorts):
    """Condition: *actor_id* holds *role* in the case, read fresh.

    Returns:
        SUCCESS when the case's roster records *actor_id* holding *role*;
        FAILURE otherwise, a case this store does not hold included — an
        actor holds no role in a case the store does not have
        (:func:`~vultron.core.participants.role_predicate.has_role`).

    The role is read per message rather than fixed at startup, because a
    role granted or removed mid-case changes the answer (CM-02-011).

    The case comes only from the ``/case_id`` input port (BTND-01-006); a
    tree that names it at build time seeds the port with
    :func:`~vultron.core.behaviors.case_id_scope.with_case_id`.

    Args:
        actor_id: The actor whose role is in question.  Read from the
            message, never from the receiving store (ADR-0022).
        role: The role asked about.  ``CVDRole.CASE_MANAGER`` is refused:
            authority has one asker (ARCH-24-003, HP-01-037).
        name: Node name; defaults to the class name.

    Raises:
        VultronWiringError: *role* is ``CVDRole.CASE_MANAGER``.
    """

    def __init__(
        self,
        actor_id: str,
        role: CVDRole,
        name: str | None = None,
    ) -> None:
        if role is CVDRole.CASE_MANAGER:
            raise VultronWiringError(
                f"{type(self).__name__}: CVDRole.CASE_MANAGER is the path"
                " stage's question and the CASE_MANAGER gate's; exactly one"
                " node answers it, so this node refuses that role"
                " (ARCH-24-003, HP-01-037)"
            )
        super().__init__(name=name or self.__class__.__name__)
        self._actor_id = actor_id
        self._role = role
        self._case_id_bb: str | None = None

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id"}

    def initialise(self) -> None:
        super().initialise()
        self._case_id_bb = None
        try:
            self._case_id_bb = self.get_input("case_id")
        except NoDataAvailable, NotImplementedError:
            pass

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case_id = self._case_id_bb
        if not case_id:
            self.feedback_message = (
                f"{self.name}: no case to read '{self._actor_id}'s"
                f" {self._role.name} role in"
            )
            self.logger.warning(
                "%s: executing at '%s', no case to read '%s's %s role in",
                self.name,
                self.actor_id,
                self._actor_id,
                self._role.name,
            )
            return Status.FAILURE
        if has_role(self._actor_id, case_id, self._role, self.datalayer):
            self.logger.debug(
                "%s: executing at '%s', '%s' holds %s in case '%s'",
                self.name,
                self.actor_id,
                self._actor_id,
                self._role.name,
                case_id,
            )
            return Status.SUCCESS
        self.feedback_message = (
            f"'{self._actor_id}' does not hold {self._role.name} in case"
            f" '{case_id}'"
        )
        self.logger.debug(
            "%s: executing at '%s', %s",
            self.name,
            self.actor_id,
            self.feedback_message,
        )
        return Status.FAILURE
