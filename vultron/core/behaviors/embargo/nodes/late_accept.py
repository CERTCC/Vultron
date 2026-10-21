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

"""The CASE_MANAGER's routing of a late embargo Accept (EMB-17).

An ``Accept(Invite(EmbargoEvent))`` the Invite expiry found late is not an
answer (EMB-17-001).  The CASE_MANAGER routes it by its compatibility with the
case's embargo, one arm per outcome, each a diversion of the Accept tree
(CLP-10-026): :class:`LateAcceptRouteIsNode` names the arm, and
:class:`CommitLateAcceptAcknowledgementNode` is the no-op acknowledgement
when the case holds no embargo (EMB-17-004), taken only when
:class:`LateAcceptAcknowledgeableNode` finds the delivery can be answered.
"""

from enum import StrEnum
from typing import Any, cast

from py_trees.common import Status

from vultron.core.behaviors.case.nodes.ledger_payload import (
    carries_no_received_body,
    unrecordable_resend_reason,
)
from vultron.core.behaviors.case_manager_commit import (
    _CommitCaseManagerActivityBase,
)
from vultron.core.behaviors.embargo.nodes.em_state import read_case_em_state
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.sync.nodes._helpers import _extract_id_from_field
from vultron.core.models.events.base import VultronEvent
from vultron.core.models.rsvp_deadline import INVITE_EXPIRED_NOOP_SEMANTIC_TYPE
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.received_activity import archived_received_body
from vultron.core.states.em import EM
from vultron.core.sync_helpers import recorded_entries_for_case
from vultron.errors import VultronWiringError


class LateAcceptRoute(StrEnum):
    """How the CASE_MANAGER answers a late embargo ``Accept`` (EMB-17-001).

    - ``HONOUR`` — the accepted embargo is the case's current one: the
      participant's row moves to ``AGREED`` (EMB-17-002).
    - ``REINVITE`` — the case has a current embargo, but not the accepted
      one: the accepter is invited to it (EMB-17-003).
    - ``ACKNOWLEDGE`` — the case holds no embargo (EM ``EXITED`` or
      ``NONE``): a no-op acknowledgement (EMB-17-004).
    """

    HONOUR = "honour"
    REINVITE = "reinvite"
    ACKNOWLEDGE = "acknowledge"


def late_accept_route(
    em_state: EM, active_embargo_id: str | None, embargo_id: str
) -> LateAcceptRoute:
    """The EMB-17 arm for a late Accept of *embargo_id* (EMB-17-001)."""
    if em_state in (EM.ACTIVE, EM.REVISE) and active_embargo_id == embargo_id:
        return LateAcceptRoute.HONOUR
    if em_state in (EM.ACTIVE, EM.REVISE, EM.PROPOSED):
        return LateAcceptRoute.REINVITE
    return LateAcceptRoute.ACKNOWLEDGE


class LateAcceptRouteIsNode(DataLayerConditionWithPorts):
    """Condition: a late Accept of *embargo_id* takes the *route* arm.

    Reads the case's EM state through
    :func:`~vultron.core.behaviors.embargo.nodes.em_state.read_case_em_state`
    (AC-1, #1474) and its embargo in force when the node runs, after the
    Invite expiry has been recorded.  SUCCESS when
    :func:`late_accept_route` names *route*, logged at INFO; FAILURE
    otherwise.  Read-only.  A case the CASE_MANAGER cannot
    read raises: it holds its own case (Regime 1, ADR-0087), and a guess
    here would route the Accept to the wrong arm.
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        accepting_actor_id: str,
        route: LateAcceptRoute,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._embargo_id = embargo_id
        self._accepting_actor_id = accepting_actor_id
        self.route = route

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        em_state = read_case_em_state(self.datalayer, self._case_id)
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure
        route = late_accept_route(
            em_state, case.active_embargo_id, self._embargo_id
        )
        if route is not self.route:
            return Status.FAILURE
        self.feedback_message = (
            f"late Accept of embargo '{self._embargo_id}' by"
            f" '{self._accepting_actor_id}' on case '{self._case_id}'"
            f" (EM {em_state.name}): {route.value} (EMB-17-001)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


def late_accept_acknowledged(
    datalayer: CasePersistence, case_id: str, accept_id: str
) -> bool:
    """True when *case_id*'s ledger records the ``Ignore`` of *accept_id*.

    The acknowledgement carries the late Accept inline as its ``object``
    (EMB-17-004), so the Accept's id names the entry that answers it.
    """
    return any(
        entry.semantic_type == INVITE_EXPIRED_NOOP_SEMANTIC_TYPE
        and _extract_id_from_field(entry.payload_snapshot.get("object"))
        == accept_id
        for entry in recorded_entries_for_case(case_id=case_id, dl=datalayer)
    )


class LateAcceptAcknowledgeableNode(DataLayerConditionWithPorts):
    """Condition: the acknowledgement arm can answer this late Accept.

    The acknowledgement carries the received Accept inline (EMB-17-004), so
    it needs the received body.  A resend routed without one (IE-10-001,
    VM-08-002) can be answered only by the acknowledgement already recorded
    for it.  SUCCESS when the event carries its body or that acknowledgement
    is recorded; FAILURE otherwise, logged at WARNING, so the arm is not
    taken and the tree's late-Accept guard refuses the delivery instead of
    the arm failing to answer it (CLP-10-026).  Read-only.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._event: object | None = None

    def initialise(self) -> None:
        super().initialise()
        self._event = self._try_get_input("activity")

    def update(self) -> Status:
        event = self._event
        if not carries_no_received_body(event):
            return Status.SUCCESS
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        accept_id = cast(VultronEvent, event).activity_id
        if late_accept_acknowledged(self.datalayer, self._case_id, accept_id):
            return Status.SUCCESS
        self.feedback_message = unrecordable_resend_reason(
            accept_id, self._case_id
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


class CommitLateAcceptAcknowledgementNode(_CommitCaseManagerActivityBase):
    """Commit the CASE_MANAGER's ``Ignore`` of a late embargo ``Accept``.

    The Invite had expired and the case holds no embargo the Accept could
    still bind (EM ``EXITED`` or ``NONE``), so the CASE_MANAGER acknowledges
    the answer and changes no consent row (EMB-17-004, ADR-0118).  The
    acknowledgement is the CASE_MANAGER's own decision, taken from the clock,
    so it is committed as its own entry (CLP-07-013): an
    ``Ignore(Accept(Invite(EmbargoEvent)))`` the factory builds as the
    executing CASE_MANAGER, with the received Accept inline, and
    its sealed blob is the entry's ``payloadSnapshot`` (VM-08-003).

    The received Accept is the body intake archived for the event on
    ``/activity``, carried inline as it arrived (DL-06-004, ADR-0149): the
    received body a received entry records (CLP-07-011).
    Addressed to nobody: the ledger fan-out is its delivery, and a replica
    stores it and changes nothing (EMB-17-010).  The factory derives the
    ``Ignore``'s id from the CASE_MANAGER and the Accept, so a redelivered
    Accept commits nothing new.  A resend routed without received evidence
    (IE-10-001) has no body to carry: the acknowledgement already recorded
    for its Accept stands.  The arm is taken for such a resend only when one
    is recorded (:class:`LateAcceptAcknowledgeableNode`), so reaching this
    node without either is a composition fault, as is a missing received
    event (ARCH-15-001, ADR-0095).
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(
            case_id=case_id,
            semantic_type=INVITE_EXPIRED_NOOP_SEMANTIC_TYPE,
            notify_participants=False,
            name=name,
        )
        self._event: object | None = None

    def initialise(self) -> None:
        super().initialise()
        self._event = self._try_get_input("activity")

    def update(self) -> Status:
        if carries_no_received_body(self._event):
            return self._answer_resend(cast(VultronEvent, self._event))
        return super().update()

    def _answer_resend(self, event: VultronEvent) -> Status:
        """The recorded acknowledgement of *event*'s Accept stands."""
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        if not late_accept_acknowledged(
            self.datalayer, self._case_id, event.activity_id
        ):
            raise VultronWiringError(
                f"{self.name}: late Accept '{event.activity_id}' carries no"
                " received body and no acknowledgement of it is recorded; the"
                " arm's condition should not have held (CLP-10-026)"
            )
        self.feedback_message = (
            f"late Accept '{event.activity_id}' is a redelivery already"
            f" acknowledged on case '{self._case_id}'"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS

    def _late_accept(self) -> dict[str, Any]:
        """The received Accept, as intake archived it (ADR-0149).

        Handed to the reply seam unread, which embeds it as it arrived
        (DL-06-004), as the refusal notice embeds what it refuses.
        """
        event = self._event
        if not isinstance(event, VultronEvent):
            raise VultronWiringError(
                f"{self.name}: no received Accept on the blackboard to"
                " acknowledge (ARCH-15-001)"
            )
        assert self.datalayer is not None
        return archived_received_body(self.datalayer, event.activity_id)

    def _build(self, to: list[str] | None) -> tuple[str, str]:
        assert self.trigger_activity_factory is not None
        return self.trigger_activity_factory.ignore_late_embargo_accept(
            case_id=self._case_id,
            actor=cast(str, self.actor_id),
            late_accept=self._late_accept(),
        )


__all__ = [
    "CommitLateAcceptAcknowledgementNode",
    "LateAcceptAcknowledgeableNode",
    "LateAcceptRoute",
    "LateAcceptRouteIsNode",
    "late_accept_acknowledged",
    "late_accept_route",
]
