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

"""The CASE_MANAGER's ``Announce`` of an act it admitted (ADR-0199).

An admitted act reaches the participants by the ledger fan-out.  An actor the
act concerns that the fan-out does not reach receives
``Announce(<the admitted act>)`` from the CASE_MANAGER instead: a removed or
reinstated participant (CM-31-044), and, by ADR-0203, a signatory an
embargo's end may have bound.  :class:`EmitAnnounceAdmittedActNode` is the one
emit every such notice uses; a use names its recipients by overriding
:meth:`~EmitAnnounceAdmittedActNode._recipients`.

The ``Announce`` informs and asks nothing.  Its ``actor`` is the CASE_MANAGER,
so the receiver's trust check reads the CASE_MANAGER, and the announced act
travels inline as it was received, keeping its own author and id.  It names
the act in ``inReplyTo`` too, because the act's commit caused it (ADR-0204).
Its id is derived from the act, so a re-run of the act rebuilds the same
``Announce`` and the outbox sends it once (ID-04-004, OX-06-002).  It is
delivery, not a record: it is queued in the act's transaction and never
committed to the ledger (CLP-07-015, CM-31-026).
"""

from py_trees.ports import PortInformation

from vultron.core.behaviors.act_key_ports import (
    act_key_ports,
    act_key_remappings,
    act_value,
)
from vultron.core.behaviors.act_keys import CASE_ID
from vultron.core.behaviors.helpers.emit import _EmitSingleActivityBase
from vultron.core.behaviors.received_request import ReceivedRequestInputMixin
from vultron.core.models.activity_ids import derived_activity_id
from vultron.errors import VultronValidationError, VultronWiringError

#: The kind label of the derived ``Announce`` id (ID-04-004).
ANNOUNCE_ADMITTED_ACT_KIND = "announce-admitted-act"


class EmitAnnounceAdmittedActNode(
    ReceivedRequestInputMixin, _EmitSingleActivityBase
):
    """Send ``Announce(<the admitted act>)`` to the actors it concerns.

    The shared emit of ADR-0199's announcement: the CASE_MANAGER is the
    ``actor``, the admitted act is the ``object`` and the ``inReplyTo``,
    the case is the ``context``, and the id is derived from the act
    (:meth:`announce_id`).  Subclasses name the recipients in
    :meth:`_recipients`.  The admitted act is the received activity on the
    blackboard by default; a use whose act is not the one received
    overrides :meth:`_admitted_act_id`.  The case is read from ``/case_id``
    (BTND-01-008).

    Runs after the guarded commit, as a manager effect.  The handler treats
    a ``FAILURE`` here as an internal fault, never a refusal: the act is
    already admitted.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **_EmitSingleActivityBase.INPUT_PORTS,
        **act_key_ports(CASE_ID),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            **super()._domain_port_remappings(),
            **act_key_remappings(CASE_ID),
        }

    @staticmethod
    def announce_id(act_id: str) -> str:
        """The id of the CASE_MANAGER's ``Announce`` of the act *act_id*.

        One ``Announce`` per admitted act, to all its recipients, so the id
        is derived from the act alone (ID-04-004).
        """
        return derived_activity_id(ANNOUNCE_ADMITTED_ACT_KIND, act_id)

    def _recipients(self) -> list[str]:
        """The actors the announcement goes to; subclasses implement it."""
        raise NotImplementedError

    def _admitted_act_id(self) -> str:
        """The id of the act announced: by default, the act received.

        Raises:
            VultronWiringError: The run carries no received act.
        """
        act_id = self._received_request_id()
        if act_id is None:
            raise VultronWiringError(
                f"{self.name}: no admitted act to announce: the run carries"
                " no received activity (ADR-0199)"
            )
        return act_id

    def _call_factory(self) -> tuple[str, str]:
        assert self.actor_id is not None
        assert self.trigger_activity_factory is not None
        case_id = act_value(self, CASE_ID, str)
        act_id = self._admitted_act_id()
        to = self._recipients()
        if not to:
            raise VultronValidationError(
                f"{self.name}: the announcement of '{act_id}' names no"
                " recipient"
            )
        return self.trigger_activity_factory.announce_admitted_act(
            admitted_act_id=act_id,
            case_id=case_id,
            actor=self.actor_id,
            to=to,
            id_=self.announce_id(act_id),
            at=self._require_act_instant(),
        )

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        self.logger.info(
            "%s: announced admitted act '%s' as '%s' (ADR-0199)",
            self.name,
            self._admitted_act_id(),
            activity_id,
        )


__all__ = [
    "ANNOUNCE_ADMITTED_ACT_KIND",
    "EmitAnnounceAdmittedActNode",
]
