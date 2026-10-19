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

"""The CASE_MANAGER's refusal notice to the asserting participant (ADR-0141).

When a precondition guard at the CASE_MANAGER refuses an assertion, nothing is
committed (CLP-05-002), so the participant would never learn its assertion
had no effect.  :class:`EmitRefusalNoticeNode` tells it: one ``Reject`` of the
refused activity, inline, threaded by ``inReplyTo``, addressed to the asserter
alone and carrying the refusing guard's reason in ``summary`` (CLP-02-005,
CLP-05-001).  :class:`ClearRefusedAssertionNode` is the participant's side:
it closes the pending assertion the notice answers (CLP-06-006).

The node is a refusal effect: a received tree passes it, through
:func:`refusal_notice`, as ``refusal_effects`` to
:func:`~vultron.core.behaviors.case.receive_activity_tree.create_receive_activity_tree`.
The factory runs it only when a precondition guard refuses, only at the
case's CASE_MANAGER, never for a sender-guard refusal, a repeat reported
``SKIPPED`` or a redelivery (CLP-10-022).  It writes no state: the notice's
id is derived from the CASE_MANAGER and the refused activity, so a retry
queues it once (ID-04-004, OX-06-002).

Blackboard contract (BTND-03-003):

- ``activity`` (READ, ``/activity``): the received
  :class:`~vultron.core.models.events.base.VultronEvent`.  The refused
  activity is its ``activity``, rendered as it is recorded when received
  (CLP-07-009); its sender is the asserter.
"""

from py_trees.common import Status

from vultron.core.behaviors.case.nodes.ledger_payload import (
    _extract_payload_snapshot,
)
from vultron.core.behaviors.case.nodes.refusal_stage import (
    enclosing_refusal_reason,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
    _EmitSingleActivityBase,
)
from vultron.core.models.events.base import VultronEvent
from vultron.core.models.pending_assertion import (
    PendingAssertion,
    get_pending_assertion_store,
)
from vultron.errors import VultronWiringError

__all__ = [
    "ClearRefusedAssertionNode",
    "EmitRefusalNoticeNode",
    "refusal_notice",
]


class EmitRefusalNoticeNode(_EmitSingleActivityBase):
    """Queue the refusal notice for the received activity a guard refused.

    Reads the received event from ``/activity`` and the refusing guard's
    reason from the enclosing
    :class:`~vultron.core.behaviors.case.nodes.refusal_stage.PreconditionGuardStage`.
    Returns ``FAILURE`` when either is missing or the notice cannot be built;
    the refusal stage logs that at WARNING and the delivery is still refused
    for the guard's reason.

    Subclasses :class:`_EmitSingleActivityBase`; only ``_call_factory`` and
    ``_on_success`` are overridden (BTND-07-005, BTND-07-009).
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def __init__(self, case_id: str | None, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._event: object | None = None
        self._asserter: str | None = None
        self._refused_id: str | None = None
        self._reason: str | None = None

    def initialise(self) -> None:
        super().initialise()
        self._event = self._try_get_input("activity")

    def _call_factory(self) -> tuple[str, str]:
        event = self._event
        if not isinstance(event, VultronEvent) or event.activity is None:
            raise VultronWiringError(
                f"{self.name}: no received activity on the blackboard to"
                " refuse (ARCH-15-001)"
            )
        reason = enclosing_refusal_reason(self)
        if reason is None:
            raise VultronWiringError(
                f"{self.name}: not a refusal effect of a precondition-guard"
                " stage, so there is no refusal reason to send (CLP-10-022)"
            )
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        self._asserter = event.actor_id
        self._refused_id = event.activity_id
        self._reason = reason
        return self.trigger_activity_factory.refusal_notice(
            case_id=self._case_id,
            actor=self.actor_id,
            refused_activity=_extract_payload_snapshot(
                event, self.datalayer, self._require_wire_render_port()
            ),
            asserter=event.actor_id,
            reason=reason,
        )

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        self.logger.info(
            "CASE_MANAGER '%s' sent refusal notice '%s' to '%s' for activity"
            " '%s' on case '%s': %s (CLP-05-001)",
            self.actor_id,
            activity_id,
            self._asserter,
            self._refused_id,
            self._case_id,
            self._reason,
        )


def refusal_notice(case_id: str | None) -> EmitRefusalNoticeNode:
    """The refusal notice, for a received tree's ``refusal_effects``.

    Args:
        case_id: The case the refused activity concerns; the notice's
            ``context``.
    """
    return EmitRefusalNoticeNode(case_id=case_id, name="EmitRefusalNotice")


class ClearRefusedAssertionNode(DataLayerActionWithPorts):
    """Close the pending assertion a refusal notice answers (CLP-06-006).

    Runs at the participant that sent the refused activity, after the sender
    guard established that the notice came from the case's CASE_MANAGER
    (HP-01-006).  The assertion had no effect, so the participant marks its
    pending entry cleared and logs the refusal at WARNING with the refused
    activity, this actor and the reason.  It writes no case state and sends
    nothing: what to do next is for later behavior to decide (CLP-05-001,
    CLP-06-005).  A notice for an activity this actor holds no pending entry
    for clears nothing and still succeeds.

    Pending-assertion state is this actor's own in-memory record, not case
    state (CLP-06-002), so the node is not a state writer.
    """

    def __init__(
        self,
        case_id: str,
        refused_activity_id: str,
        reason: str | None,
        sender_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.refused_activity_id = refused_activity_id
        self.reason = reason
        self.sender_id = sender_id
        self.cleared: list[PendingAssertion] = []
        """The pending entries the last run cleared."""

    def update(self) -> Status:
        self.cleared = []
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.actor_id is not None
        self.cleared = get_pending_assertion_store(
            self.actor_id
        ).clear_activity(self.case_id, self.refused_activity_id)
        self.logger.warning(
            "CASE_MANAGER '%s' refused activity '%s' from actor '%s' on case"
            " '%s': %s; %d pending assertion(s) cleared, nothing re-sent"
            " (CLP-05-001, CLP-06-006)",
            self.sender_id,
            self.refused_activity_id,
            self.actor_id,
            self.case_id,
            self.reason or "no reason given",
            len(self.cleared),
        )
        return Status.SUCCESS
