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

The node is a refusal effect, and the factory adds it itself:
:func:`~vultron.core.behaviors.case.receive_activity_tree.create_receive_activity_tree`
puts :func:`refusal_notice` ahead of a tree's own ``refusal_effects`` in every
tree that commits to a case and has precondition guards, so no tree writes
its own copy (CS-22-001).  A tree goes without it only by passing a
registered :class:`RefusalNoticeExemption` that says what answers its
refusals instead: :data:`REFUSAL_NOTICE_EXEMPTIONS` is the whole list, and
``test/architecture/test_received_tree_refusal_notice.py`` pins which tree
uses each one.
The factory runs the notice only when a precondition guard refuses, only at
the case's CASE_MANAGER, never for a sender-guard refusal, a repeat reported
``SKIPPED`` or a redelivery (CLP-10-022).  It writes no state: the notice's
id is derived from the CASE_MANAGER and the refused activity, so a retry
queues it once (ID-04-004, OX-06-002).

Blackboard contract (BTND-03-003):

- ``activity`` (READ, ``/activity``): the received
  :class:`~vultron.core.models.events.base.VultronEvent`.  The refused
  activity is the body intake archived for it, embedded verbatim
  (CLP-10-017, ADR-0149); the event's sender is the asserter.
"""

import json
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any, Final

import py_trees
from py_trees.common import Status
from pydantic import BaseModel, ConfigDict

from vultron.core.behaviors.case.nodes.diversion_stage import Diversion
from vultron.core.behaviors.case.nodes.refusal_stage import (
    enclosing_refusal_reason,
)
from vultron.core.behaviors.exemption_registry import require_registered
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
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.errors import VultronWiringError
from vultron.primitives import NonEmptyString

__all__ = [
    "ClearRefusedAssertionNode",
    "EmitRefusalNoticeNode",
    "OWNER_CLOSE_DECLINE",
    "REFUSAL_NOTICE_EXEMPTIONS",
    "RefusalNoticeExemption",
    "refusal_effects_with_notice",
    "refusal_notice",
]


class RefusalNoticeExemption(BaseModel):
    """One recorded decision that a received tree sends no refusal notice.

    Attributes:
        name: Short stable name of the decision.
        reason: Why the tree is correct without the notice, and what
            answers its refusals instead.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: NonEmptyString
    reason: NonEmptyString


OWNER_CLOSE_DECLINE: Final = RefusalNoticeExemption(
    name="owner-close-decline",
    reason=(
        "The close-case tree's close arm refuses a Case Owner's"
        " Leave(VulnerabilityCase) only while an embargo is active, and the"
        " enclosing tree's decline arm answers that refusal with its own"
        " Reject of the Leave (CM-23-011, MSM-05-001).  The decline is the"
        " refusal's answer, so a notice would answer it twice (CLP-05-001)."
    ),
)

#: Every registered exemption, by name.  The factory refuses any other.
REFUSAL_NOTICE_EXEMPTIONS: Final[Mapping[str, RefusalNoticeExemption]] = (
    MappingProxyType(
        {exemption.name: exemption for exemption in (OWNER_CLOSE_DECLINE,)}
    )
)


def refusal_effects_with_notice(
    name: str,
    case_id: str | None,
    guards: Sequence[py_trees.behaviour.Behaviour | Diversion],
    refusal_effects: list[py_trees.behaviour.Behaviour],
    exemption: RefusalNoticeExemption | None,
) -> list[py_trees.behaviour.Behaviour]:
    """A received tree's refusal effects, the refusal notice first (CLP-02-005).

    A tree that commits to *case_id* and has precondition *guards* answers
    their refusal with the refusal notice to the asserter (CLP-05-001), ahead
    of the tree's own *refusal_effects*.  An exempt tree keeps only its own;
    so does a tree with no guards or no case, which refuses no assertion at
    the CASE_MANAGER before a commit.  A tree with a :class:`Diversion`
    takes the notice too: a diverted delivery has already been answered, so
    the refusal stage runs no refusal effect for it, and the notice answers
    only the refusals the guards make (CLP-10-026).
    :func:`~vultron.core.behaviors.case.receive_activity_tree.create_receive_activity_tree`
    calls it with the tree's *name*.

    Raises:
        VultronWiringError: *exemption* is not registered in
            :data:`REFUSAL_NOTICE_EXEMPTIONS`, or the tree would send no
            notice without it (no case or no guards), so it exempts nothing.
    """
    where = f"create_receive_activity_tree({name})"
    guarded = bool(guards)
    if exemption is None:
        if case_id is None or not guarded:
            return refusal_effects
        return [refusal_notice(case_id), *refusal_effects]
    require_registered(
        exemption,
        REFUSAL_NOTICE_EXEMPTIONS,
        where=where,
        kind="refusal-notice",
        registry_name="REFUSAL_NOTICE_EXEMPTIONS",
        spec_id="CLP-02-005",
    )
    if case_id is None or not guarded:
        raise VultronWiringError(
            f"{where}: refusal-notice exemption {exemption.name!r} exempts"
            " nothing — the tree has no precondition guards or no case to"
            " commit to (CLP-02-005)"
        )
    return refusal_effects


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
        if not isinstance(event, VultronEvent):
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
            refused_activity=self._archived_body(event.activity_id),
            asserter=event.actor_id,
            reason=reason,
        )

    def _archived_body(self, activity_id: str) -> dict[str, Any]:
        """The refused activity's body, as intake archived it (ADR-0149).

        The notice embeds the refused activity as the asserter sent it
        (CLP-05-001, DL-06-004).  It is read from the archive, the one copy
        of what arrived, and handed to the reply seam unread.

        Raises:
            VultronWiringError: When nothing is archived for *activity_id*:
                intake archives every received activity before any guard
                runs (CLP-10-017), so the tree is miswired.
        """
        assert self.datalayer is not None
        record = self.datalayer.read(
            ReceivedActivityRecord.build_id(activity_id)
        )
        if not isinstance(record, ReceivedActivityRecord):
            raise VultronWiringError(
                f"{self.name}: activity '{activity_id}' was refused but is not"
                " archived, so there is no received body to embed"
                " (CLP-10-017)"
            )
        body: dict[str, Any] = json.loads(record.received_body)
        return body

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
