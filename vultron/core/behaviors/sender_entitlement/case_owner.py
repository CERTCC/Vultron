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

"""The ``CASE_OWNER`` kind: the case-owner predicate and its check."""

from typing import ClassVar

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.helpers import (
    DataLayerConditionWithPorts,
)
from vultron.core.behaviors.sender_entitlement.base import (
    SenderEntitlementConditionNode,
)
from vultron.core.behaviors.sender_entitlement.declarations import (
    SenderEntitlementKind,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.predicates.addressing import (
    participant_id_for_actor,
)
from vultron.core.predicates.roles import has_case_owner_role

# ---------------------------------------------------------------------------
# Pure-predicate helper
# ---------------------------------------------------------------------------


def is_case_owner(case: object | None, actor_id: str) -> bool:
    """Return ``True`` when *actor_id* matches the case's attributed owner.

    Consolidated from ``_is_case_owner`` in
    ``vultron.core.use_cases.triggers._helpers`` (ADR-0115, AC-2).

    Args:
        case: The ``VulnerabilityCase`` object (or ``None``).
        actor_id: The actor ID to test.

    Returns:
        ``True`` when the case's ``attributed_to`` matches *actor_id*;
        ``False`` when the case is ``None`` or the owner does not match.
    """
    if case is None:
        return False
    owner_id = _as_id(getattr(case, "attributed_to", None))
    return owner_id is not None and owner_id == actor_id


def _holds_case_owner_role(
    datalayer: CasePersistence, case: VulnerabilityCase, actor_id: str
) -> bool:
    """Return ``True`` when *actor_id*'s participant record holds CASE_OWNER."""
    participant_id = participant_id_for_actor(
        case.actor_participant_index, actor_id
    )
    if participant_id is None:
        return False
    participant = datalayer.read(participant_id)
    if not isinstance(participant, CaseParticipant):
        return False
    return has_case_owner_role(
        list(participant.roles) if participant.roles else []
    )


# ---------------------------------------------------------------------------
# Condition node: CASE_OWNER
# ---------------------------------------------------------------------------


class SenderIsCaseOwnerNode(SenderEntitlementConditionNode):
    """Guard: sender must hold ``CVDRole.CASE_OWNER``.

    Returns ``SUCCESS`` when the sender's participant record carries
    ``CVDRole.CASE_OWNER``.
    Returns ``FAILURE`` for any actor that is not a known CASE_OWNER,
    including unknown actors or those holding other roles.

    A non-match goes through
    :meth:`~vultron.core.behaviors.sender_entitlement.base
    .SenderEntitlementConditionNode._refuse_by_placement`, the rule every
    kind check takes, so its one line is WARNING where this check is the
    guard's whole answer and DEBUG, without the ``REFUSED`` wording, where a
    later arm of an any-of side may still admit the sender (SL-03-002,
    SL-03-003).

    It is the sender door only, placed by the composed guard.  A tree that
    picks an arm on whether an actor holds the role — the status adoption
    bypass (RSH-01-002), the Leave, suggest-actor and embargo trees — asks
    :class:`~vultron.core.behaviors.role_condition.ActorHoldsRoleInCaseNode`
    instead, which states no refusal: placed where its FAILURE is the tree's
    answer, this node would log ``REFUSED (HP-01-006)`` for a sender the
    guard admitted (#5903).

    Reads ``case_id`` only from the ``/case_id`` input port (BTND-01-006); a
    tree that names the case at build time seeds the port with
    :func:`~vultron.core.behaviors.case_id_scope.with_case_id`.

    Merged from ``CheckIsCaseOwnerNode`` (ADR-0115, AC-2).

    Spec: RSH-01-002, HP-01-006, SL-03-002, SL-03-003.
    """

    guards_kind: ClassVar[SenderEntitlementKind | None] = (
        SenderEntitlementKind.CASE_OWNER
    )

    def __init__(
        self,
        sender_actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._sender_actor_id = sender_actor_id

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id"}

    def initialise(self) -> None:
        super().initialise()
        self._case_id_bb: str | None = None
        try:
            self._case_id_bb = self.get_input("case_id")
        except NoDataAvailable, NotImplementedError:
            pass

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case_id = self._case_id_bb

        case, failure = self._require_case(case_id)
        if failure is not None:
            return failure  # Regime 1: CASE_OWNER role gate needs the case

        if _holds_case_owner_role(self.datalayer, case, self._sender_actor_id):
            self.logger.debug(
                "%s: sender '%s' IS CASE_OWNER for case '%s'",
                self.name,
                self._sender_actor_id,
                case_id,
            )
            return Status.SUCCESS

        return self._refuse_by_placement(
            f"Sender '{self._sender_actor_id}' is not the Case Owner of case"
            f" '{case_id}' — REFUSED (HP-01-006)"
        )
