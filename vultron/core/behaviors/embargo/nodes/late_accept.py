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

"""The CASE_MANAGER's no-op acknowledgement of a late embargo Accept (EMB-17-004)."""

from typing import Any, cast

from vultron.core.behaviors.case.nodes.ledger_payload import (
    _extract_payload_snapshot,
)
from vultron.core.behaviors.case_manager_commit import (
    _CommitCaseManagerActivityBase,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.models.events.base import VultronEvent
from vultron.core.models.rsvp_deadline import INVITE_EXPIRED_NOOP_EVENT_TYPE
from vultron.errors import VultronWiringError


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

    The received Accept is read from ``/activity`` and rendered through the
    wire-render port, the shape a received activity is recorded in
    (CLP-07-009).  Addressed to nobody: the ledger fan-out is its delivery,
    and a replica stores it and changes nothing (EMB-17-010).  The factory
    derives the ``Ignore``'s id from the CASE_MANAGER and the Accept, so a
    redelivered Accept commits nothing new.

    A missing received event or rendering port is a composition fault and
    raises (ARCH-15-001, ADR-0095).
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
            event_type=INVITE_EXPIRED_NOOP_EVENT_TYPE,
            notify_participants=False,
            name=name,
        )
        self._event: object | None = None

    def initialise(self) -> None:
        super().initialise()
        self._event = self._try_get_input("activity")

    def _late_accept(self) -> dict[str, Any]:
        """The received Accept, rendered as it is recorded when received."""
        event = self._event
        if not isinstance(event, VultronEvent) or event.activity is None:
            raise VultronWiringError(
                f"{self.name}: no received Accept on the blackboard to"
                " acknowledge (ARCH-15-001)"
            )
        return _extract_payload_snapshot(
            event, self.datalayer, self._require_wire_render_port()
        )

    def _build(self, to: list[str] | None) -> tuple[str, str]:
        assert self.trigger_activity_factory is not None
        return self.trigger_activity_factory.ignore_late_embargo_accept(
            case_id=self._case_id,
            actor=cast(str, self.actor_id),
            late_accept=self._late_accept(),
        )


__all__ = ["CommitLateAcceptAcknowledgementNode"]
