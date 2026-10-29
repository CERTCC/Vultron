#!/usr/bin/env python
#
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
"""Nodes for the CASE_MANAGER's answer to a stamped ledger position (SYNC-18).

Every case activity states its sender's ledger tail as ``ledgerPosition``
(SYNC-18-001).  The CASE_MANAGER judges it against its own ledger:

- **held** — the position names an entry the ledger holds, at the tail or
  behind it.  A lag is logged at DEBUG (SYNC-18-004) and, for an active
  participant, answered as a ``Read(CaseLedgerEntry)`` is: the position is
  recorded and the entries after it replayed (SYNC-18-007).
- **split** — the position names an index the ledger holds with another
  hash, or an index past its tail.  It is logged at ERROR and an active
  participant is re-seeded (SYNC-18-005).

:class:`ClassifyLedgerPositionNode` judges the position once and
:class:`LedgerPositionIsNode` is the condition each arm of that answer starts
with; :class:`PeerActiveParticipantNode` skips the record and the
replay for an inert sender; :class:`LedgerPositionAnswer` keeps whatever the
answer does from deciding the received activity's outcome.  The received-tree
factory composes them (``ledger_position_stage``).  A tree that answers the
position itself names a :class:`LedgerPositionExemption` instead.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import Final, cast

import py_trees
from py_trees.common import Status
from pydantic import BaseModel, ConfigDict

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.node_logger import node_logger
from vultron.core.behaviors.sync.nodes.embargo_pause import peer_is_withheld
from vultron.core.models.events.base import LedgerPositionedEvent
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.sync_helpers import (
    holds_ledger_position,
    ledger_tail_position,
)
from vultron.errors import VultronError
from vultron.primitives import NonEmptyString, same_actor_id

__all__ = [
    "HELD",
    "LEDGER_POSITION_EXEMPTIONS",
    "ClassifyLedgerPositionNode",
    "LedgerPositionAnswer",
    "LedgerPositionExemption",
    "LedgerPositionIsNode",
    "PositionStanding",
    "STATED_POSITION_ANSWERED_BY_TREE",
    "PeerActiveParticipantNode",
]


class LedgerPositionExemption(BaseModel):
    """One recorded decision that a received tree answers no stamped position.

    Attributes:
        name: Short stable name of the decision.
        reason: Why the tree is correct without the factory's answer, and
            what stands in for it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: NonEmptyString
    reason: NonEmptyString


STATED_POSITION_ANSWERED_BY_TREE: Final = LedgerPositionExemption(
    name="stated-position-answered-by-tree",
    reason=(
        "The activity is a Read(CaseLedgerEntry), whose whole act is to"
        " state the position, so its own tree answers it: it records and"
        " replays a held position and answers a split one with a WARNING and"
        " nothing sent (SYNC-17-003 to SYNC-17-005).  A second answer would"
        " re-seed where SYNC-17-005 sends nothing."
    ),
)

#: Every decision that lets a received tree go without the answer.
LEDGER_POSITION_EXEMPTIONS: Final[dict[str, LedgerPositionExemption]] = {
    exemption.name: exemption
    for exemption in (STATED_POSITION_ANSWERED_BY_TREE,)
}


class PositionStanding(StrEnum):
    """How a stamped position stands against the CASE_MANAGER's ledger."""

    NONE = "none"
    """The activity states no position from the sender to answer."""
    TAIL = "tail"
    """The position is this ledger's tail."""
    LAG = "lag"
    """The ledger holds the position, behind its tail."""
    SPLIT = "split"
    """The ledger does not hold it: another hash there, or past the tail."""


#: The standings of a position the ledger holds (SYNC-18-007).
HELD: Final = frozenset({PositionStanding.TAIL, PositionStanding.LAG})


class ClassifyLedgerPositionNode(DataLayerActionWithPorts):
    """Judge the sender's stamped position against this ledger, once.

    The received activity (``/activity``) states the position when it is a
    :class:`~vultron.core.models.events.base.LedgerPositionedEvent` sent by
    *sender_id*; an activity this actor sent itself states none worth
    answering.  The node publishes the position's
    :class:`PositionStanding` in this store's ledger for *case_id* as
    ``ledger_position_standing``, for the :class:`LedgerPositionIsNode`
    conditions after it (the context-handoff pattern of the sync package),
    and logs what it found: a lag at DEBUG (SYNC-18-004), a split at ERROR
    (SYNC-18-005).  It writes nothing to the store and always succeeds.

    The tail is read once (:func:`~vultron.core.sync_helpers.ledger_tail_position`);
    a position at it needs no further read, and only one behind it is looked
    up (:func:`~vultron.core.sync_helpers.holds_ledger_position`).

    Spec: SYNC-18-004, SYNC-18-005, SYNC-18-007.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "ledger_position_standing": PortInformation(
            data_type=str, required=True
        ),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "activity": "/activity",
            "ledger_position_standing": "/ledger_position_standing",
        }

    def __init__(
        self,
        case_id: str,
        sender_id: str,
        name: str | None = None,
        *,
        is_redelivery: Callable[[], bool] | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.sender_id = sender_id
        self.redelivery_check = is_redelivery
        self.standing: PositionStanding = PositionStanding.NONE
        """The standing the last run found (for inspection)."""

    def initialise(self) -> None:
        super().initialise()
        self.activity = self.get_input("activity")

    def _stated_position(self) -> LedgerPosition | None:
        """The position the sender stamped, or ``None`` when none is owed.

        A redelivery of an activity this store already archived owes none:
        a resend keeps its first stamp (SYNC-18-002), which the first
        delivery answered, and answering it again would move the sender's
        acknowledged position back and replay what was sent since.
        """
        activity = self.activity
        if not isinstance(activity, LedgerPositionedEvent):
            return None
        if self.redelivery_check is not None and self.redelivery_check():
            self.logger.debug(
                "%s: activity '%s' is a redelivery; its ledger position was"
                " answered when it first arrived (SYNC-18-002)",
                self.name,
                activity.activity_id,
            )
            return None
        if not same_actor_id(activity.actor_id, self.sender_id):
            return None
        if self.actor_id is not None and same_actor_id(
            activity.actor_id, self.actor_id
        ):
            return None
        return activity.ledger_position

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        dl = cast(CasePersistence, self.datalayer)
        position = self._stated_position()
        self.standing = PositionStanding.NONE
        if position is not None:
            tail = ledger_tail_position(self.case_id, dl)
            if position == tail:
                self.standing = PositionStanding.TAIL
            elif position.log_index < tail.log_index and (
                holds_ledger_position(self.case_id, dl, position)
            ):
                self.standing = PositionStanding.LAG
            else:
                self.standing = PositionStanding.SPLIT
            self._log(position, tail)
        self._set_output("ledger_position_standing", str(self.standing))
        return Status.SUCCESS

    def _log(self, position: LedgerPosition, tail: LedgerPosition) -> None:
        activity_id = getattr(self.activity, "activity_id", None)
        if self.standing is PositionStanding.SPLIT:
            self.logger.error(
                "%s: activity '%s' from '%s' for case '%s' states ledger"
                " position (log_index=%d, entry_hash=%.16s…) this ledger does"
                " not hold (tail log_index=%d): the sender's chain has split;"
                " the activity is judged as it is (SYNC-18-005)",
                self.name,
                activity_id,
                self.sender_id,
                self.case_id,
                position.log_index,
                position.entry_hash,
                tail.log_index,
            )
        elif self.standing is PositionStanding.LAG:
            self.logger.debug(
                "%s: activity '%s' from '%s' for case '%s' states ledger"
                " position %d, behind this ledger's tail %d; the activity is"
                " judged as it is (SYNC-18-004)",
                self.name,
                activity_id,
                self.sender_id,
                self.case_id,
                position.log_index,
                tail.log_index,
            )


class LedgerPositionIsNode(DataLayerConditionWithPorts):
    """SUCCESS when the classified standing is one of *expect*.

    Reads the ``ledger_position_standing`` :class:`ClassifyLedgerPositionNode`
    published earlier in the same tick; reads nothing else.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "ledger_position_standing": PortInformation(
            data_type=str, required=True
        ),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"ledger_position_standing": "/ledger_position_standing"}

    def __init__(
        self, expect: frozenset[PositionStanding], name: str | None = None
    ) -> None:
        label = "|".join(sorted(expect))
        super().__init__(name=name or f"LedgerPositionIs[{label}]")
        self.expect = expect

    def initialise(self) -> None:
        super().initialise()
        self.standing = PositionStanding(
            self.get_input("ledger_position_standing")
        )

    def update(self) -> Status:
        if self.standing in self.expect:
            return Status.SUCCESS
        return Status.FAILURE


class PeerActiveParticipantNode(DataLayerConditionWithPorts):
    """SUCCESS when *sender_id*'s standing in *case_id* is *active*.

    The active-participant check is the shared one
    (:func:`~vultron.core.participants.recipients.is_case_content_recipient`,
    CM-10-004, CM-10-007).  A removed, unconsented or not-yet-joined
    participant's position is not answered: nothing is recorded for it and
    nothing sent (SYNC-18-007), so the answer asks ``active=False`` first to
    skip it, and ``active=True`` again before it writes.  ``FAILURE`` when
    the standing is the other one, and when it cannot be decided (the case
    is not in this store), with the reason, so an undecided standing is
    never read as active.
    """

    def __init__(
        self,
        case_id: str,
        sender_id: str,
        *,
        active: bool,
        name: str | None = None,
    ) -> None:
        label = "Active" if active else "NotActive"
        super().__init__(name=name or f"Peer{label}Participant")
        self.case_id = case_id
        self.sender_id = sender_id
        self.active = active

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        try:
            withheld = peer_is_withheld(
                cast(CasePersistence, self.datalayer),
                case_id=self.case_id,
                peer_id=self.sender_id,
            )
        except VultronError as exc:
            self.feedback_message = str(exc)
            return Status.FAILURE
        if withheld is self.active:
            self.feedback_message = (
                f"sender '{self.sender_id}' is not an active participant of"
                f" case '{self.case_id}'"
                if withheld
                else f"sender '{self.sender_id}' is an active participant of"
                f" case '{self.case_id}'"
            )
            return Status.FAILURE
        if withheld:
            self.logger.info(
                "%s: sender '%s' is not an active participant of case '%s';"
                " its ledger position is not recorded or answered"
                " (SYNC-18-007, CM-10-004)",
                self.name,
                self.sender_id,
                self.case_id,
            )
        return Status.SUCCESS


class LedgerPositionAnswer(py_trees.decorators.Decorator):
    """The answer to a stamped position; it never decides the activity.

    ``SUCCESS`` when the answer recorded, replayed, re-seeded or had nothing
    to do.  When it fails — a replay held back at an entry that does not
    verify, or a gate it could not decide — the failure is logged at WARNING
    and reported as ``SUCCESS``, so the received activity is judged as it
    would be without the position (SYNC-18-004, SYNC-18-005, SYNC-18-007).
    The child keeps its ``FAILURE`` for inspection.  An exception is not
    caught, so an internal error still ends the tree (ADR-0095).
    """

    def update(self) -> Status:
        child = self.decorated
        if child.status == Status.FAILURE:
            self.feedback_message = BTBridge.get_failure_reason(child)
            node_logger(self).warning(
                "%s: answer to the sender's ledger position failed; the"
                " activity is judged as it is: %s",
                self.name,
                self.feedback_message,
            )
            return Status.SUCCESS
        return child.status
