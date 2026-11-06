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

"""Nodes for the CASE_MANAGER's order of a sender's activities (SYNC-21).

A participant numbers each case activity it sends the CASE_MANAGER with
``senderSequence`` (SYNC-21-001), and the CASE_MANAGER judges each sender's
activities in that order (SYNC-21-008, ADR-0178).  The received-tree factory
places the stage these nodes make after the door guards and the sender
guard, so only an activity from an active participant, addressed to the
CASE_MANAGER of an open case, is held or refused for its number
(SYNC-21-023), and before anything judges the act, so the tree judges each
activity unchanged and in order:

- :class:`ClassifySequenceNumberNode` says what the number is
  (:class:`~vultron.core.services.sender_sequence_order.SequenceStanding`),
  reading and writing nothing else;
- :class:`AdmitInOrderNode` moves the next expected number past an activity
  about to be judged, which counts as judged whatever its merits decide
  (SYNC-21-009);
- :class:`HoldPastGapNode` holds an activity numbered past a gap, as the body
  that arrived (SYNC-21-010, IO-03-009);
- :class:`EmitSequenceRefusalNoticeNode` refuses a late, reused or
  missing number with a notice naming the next expected number
  (SYNC-21-014, SYNC-21-015, SYNC-21-017), in a ``RefusalActTransaction``
  so a failed notice fails the tree rather than admitting the activity;
- :class:`SequenceAdmitsNode` ends the tree for every standing but
  those judged now.

:class:`~vultron.core.behaviors.sync.nodes.sender_sequence_drain.DrainSequenceHoldsNode`
ends every hold for a case before the CASE_MANAGER role passes (SYNC-21-025).

A tree whose activity takes no number names a registered
:class:`SenderSequenceExemption` instead.
"""

from __future__ import annotations

from typing import Final, cast

import py_trees
from py_trees.common import Status
from pydantic import BaseModel, ConfigDict

from vultron.config.app import get_config
from vultron.core.behaviors.case.nodes.addressee import named_in_to
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.helpers.emit import _EmitSingleActivityBase
from vultron.core.models._helpers import _as_id, now_utc
from vultron.core.models.events.base import LedgerPositionedEvent
from vultron.core.models.sender_sequence import SenderSequenceOrder
from vultron.core.participants.role_predicate import has_role
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.received_activity import (
    began_in_an_earlier_run,
    held_received_body,
)
from vultron.core.services.sender_sequence_order import (
    JUDGED,
    NOTICED,
    SequenceStanding,
    admit_in_order,
    classify_sender_sequence,
    hold_past_gap,
    sender_sequence_order,
)
from vultron.core.sync_helpers import is_ledgered_activity
from vultron.enums.roles import CVDRole
from vultron.errors import VultronWiringError
from vultron.primitives import NonEmptyString, same_actor_id

__all__ = [
    "AdmitInOrderNode",
    "ClassifySequenceNumberNode",
    "EmitSequenceRefusalNoticeNode",
    "HoldPastGapNode",
    "LEDGER_REQUEST_TAKES_NO_NUMBER",
    "SENDER_SEQUENCE_EXEMPTIONS",
    "SequenceAdmitsNode",
    "SequenceOrderStage",
    "SenderSequenceExemption",
    "SequenceStandingIsNode",
]


class SequenceOrderStage(py_trees.composites.Sequence):
    """The sender sequence stage's body: a ``Sequence`` known by its type.

    Its writes are the CASE_MANAGER's own bookkeeping and the refusal
    notice, and it commits nothing, so the architecture ratchets read it as
    a permitted stage ahead of the act's commit, as they read the ledger
    position answer (CLP-10-010).
    """


class SenderSequenceExemption(BaseModel):
    """One recorded decision that a received tree judges no sender sequence.

    Attributes:
        name: Short stable name of the decision.
        reason: Why the tree's activity takes no number.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: NonEmptyString
    reason: NonEmptyString


LEDGER_REQUEST_TAKES_NO_NUMBER: Final = SenderSequenceExemption(
    name="ledger-request-takes-no-number",
    reason=(
        "The activity is a Read(CaseLedgerEntry), a request about the ledger"
        " and not a case event (CLP-02-013), so its sender numbers it not"
        " (SYNC-21-001): a request for a missed entry must not wait behind"
        " the gap it reports."
    ),
)

#: Every decision that lets a received tree go without the stage.
SENDER_SEQUENCE_EXEMPTIONS: Final[dict[str, SenderSequenceExemption]] = {
    exemption.name: exemption
    for exemption in (LEDGER_REQUEST_TAKES_NO_NUMBER,)
}


def _recipient_ids(to: object) -> list[str]:
    """*to* as a list of ids: AS2 allows one recipient or a list of them."""
    if to is None:
        return []
    values = to if isinstance(to, list) else [to]
    return [rid for rid in (_as_id(value) for value in values) if rid]


class ClassifySequenceNumberNode(DataLayerActionWithPorts):
    """Say what the received activity's ``senderSequence`` is, once.

    The activity must be numbered when its sender numbers it: it states a
    ``ledgerPosition`` (a :class:`LedgerPositionedEvent`), comes from
    *sender_id*, a participant other than this CASE_MANAGER, and its ``to``
    addresses this CASE_MANAGER, directly or by a participants collection
    (SYNC-21-001).  Any other activity is
    :attr:`~SequenceStanding.NOT_NUMBERED`.  A number a sender sent that is
    not a positive integer reaches core as none, because the parse edge sets
    it aside (VM-08-002 keeps it in the received body), so it is
    :attr:`~SequenceStanding.MISSING` (SYNC-21-017).

    The node reads the order record and the ledger and writes nothing; it
    always succeeds.  :attr:`standing`, :attr:`order` and :attr:`number`
    are what the arms after it act on.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def __init__(
        self,
        case_id: str,
        sender_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.sender_id = sender_id
        self.activity: object | None = None
        self.standing: SequenceStanding = SequenceStanding.NOT_NUMBERED
        self.order: SenderSequenceOrder | None = None
        self.number: int | None = None

    def initialise(self) -> None:
        super().initialise()
        self.activity = self.get_input("activity")
        self.standing = SequenceStanding.NOT_NUMBERED
        self.order = None
        self.number = None

    @property
    def activity_id(self) -> str:
        """The received activity's id."""
        return str(getattr(self.activity, "activity_id", ""))

    def _takes_a_number(self, dl: CasePersistence) -> bool:
        event = self.activity
        if not isinstance(event, LedgerPositionedEvent):
            return False
        if not same_actor_id(event.actor_id, self.sender_id):
            return False
        if self.actor_id is None or same_actor_id(
            event.actor_id, self.actor_id
        ):
            return False
        if has_role(event.actor_id, self.case_id, CVDRole.CASE_MANAGER, dl):
            return False
        to = _recipient_ids(getattr(event.activity, "to", None))
        return named_in_to(dl, self.actor_id, to)

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        dl = cast(CasePersistence, self.datalayer)
        if not self._takes_a_number(dl):
            return Status.SUCCESS
        event = cast(LedgerPositionedEvent, self.activity)
        self.number = (
            event.activity.sender_sequence if event.activity else None
        )
        self.order = sender_sequence_order(dl, self.case_id, self.sender_id)
        # The re-run of a record a run left in holding, read from the
        # record intake marked (SYNC-21-018, ADR-0154).
        redelivery = began_in_an_earlier_run(
            dl, event.activity_id, intake_ran=True
        )
        self.standing = classify_sender_sequence(
            self.order,
            self.number,
            event.activity_id,
            redelivery=redelivery,
            ledgered=redelivery
            and is_ledgered_activity(dl, self.case_id, event.activity_id),
        )
        self.logger.debug(
            "%s: activity '%s' from '%s' on case '%s' numbered %s, next"
            " expected %d: %s (SYNC-21-008)",
            self.name,
            event.activity_id,
            self.sender_id,
            self.case_id,
            self.number,
            self.order.next_expected,
            self.standing,
        )
        return Status.SUCCESS

    def refusal_reason(self) -> str:
        """Why an activity with this standing is not judged now."""
        expected = self.order.next_expected if self.order else 1
        what = (
            f"activity '{self.activity_id}' from '{self.sender_id}' on case"
            f" '{self.case_id}'"
        )
        reasons = {
            SequenceStanding.AHEAD: (
                f"{what} is numbered {self.number}, past the next expected"
                f" number {expected}; held until the gap fills or the hold"
                " ends (SYNC-21-010)"
            ),
            SequenceStanding.HELD_REPEAT: (
                f"{what} is already held for its number {self.number}; the"
                " held copy stays (SYNC-21-018)"
            ),
            SequenceStanding.REPEAT_REFUSED: (
                f"{what} is a repeat numbered {self.number}, below the next"
                f" expected number {expected}, and was not applied; it is"
                " not applied now (SYNC-21-014, SYNC-21-024, CLP-05-006)"
            ),
            SequenceStanding.LATE: (
                f"{what} is numbered {self.number}, below the next expected"
                f" number {expected}: a later activity of its sender has"
                " been judged (SYNC-21-014)"
            ),
            SequenceStanding.REUSED: (
                f"{what} is numbered {self.number}, the number of another"
                f" activity this CASE_MANAGER holds (SYNC-21-014)"
            ),
            SequenceStanding.MISSING: (
                f"{what} carries no senderSequence that is a positive"
                f" integer; the next expected number is {expected}"
                " (SYNC-21-017)"
            ),
        }
        return reasons.get(self.standing, f"{what} is judged in order")


class SequenceStandingIsNode(DataLayerConditionWithPorts):
    """Condition: the classified standing is one of *expect*."""

    def __init__(
        self,
        classify: ClassifySequenceNumberNode,
        expect: frozenset[SequenceStanding],
        name: str | None = None,
    ) -> None:
        label = "|".join(sorted(expect))
        super().__init__(name=name or f"SequenceStandingIs[{label}]")
        self._classify = classify
        self.expect = expect

    def update(self) -> Status:
        if self._classify.standing in self.expect:
            return Status.SUCCESS
        return Status.FAILURE


class AdmitInOrderNode(DataLayerActionWithPorts):
    """Move the sender's next expected number past the activity judged now.

    The activity counts as judged whether its merits then admit or refuse
    it (SYNC-21-009).  A number within an ended hold first skips the
    numbers still missing before it, each logged at WARNING (SYNC-21-013,
    SYNC-21-022).  Its writes are the CASE_MANAGER's own bookkeeping
    (SYNC-21-020), never case state.  A store failure raises: the activity
    must not be judged out of order.
    """

    def __init__(
        self, classify: ClassifySequenceNumberNode, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._classify = classify

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        order, number = self._classify.order, self._classify.number
        if order is None or number is None:
            raise VultronWiringError(
                f"{self.name}: no classified number to admit (SYNC-21-008)"
            )
        admit_in_order(
            cast(CasePersistence, self.datalayer),
            order,
            number,
            self._classify.activity_id,
        )
        return Status.SUCCESS


class HoldPastGapNode(DataLayerActionWithPorts):
    """Hold the activity numbered past a gap until the gap fills (SYNC-21-010).

    The body that arrived goes back to holding on its one received record,
    owing the replay that judges it (IO-03-009, ADR-0154).  The hold ends
    when the sender's held activities reach the cap or the oldest has
    waited out the wait (``ledger.sender_sequence_hold_cap`` and
    ``ledger.sender_sequence_hold_seconds``, SYNC-21-011, SYNC-21-012,
    SYNC-21-021); its activities are then due for their replay in number
    order.  A store failure raises.
    """

    def __init__(
        self, classify: ClassifySequenceNumberNode, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._classify = classify

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        order, number = self._classify.order, self._classify.number
        if order is None or number is None:
            raise VultronWiringError(
                f"{self.name}: no classified number to hold (SYNC-21-010)"
            )
        ledger = get_config().ledger
        hold_past_gap(
            cast(CasePersistence, self.datalayer),
            order,
            number,
            self._classify.activity_id,
            now_utc(),
            cap=ledger.sender_sequence_hold_cap,
            wait=ledger.sender_sequence_hold,
        )
        return Status.SUCCESS


class EmitSequenceRefusalNoticeNode(_EmitSingleActivityBase):
    """Queue the refusal notice for an activity refused for its number.

    One ``Reject`` of the received activity to its sender, as every refusal
    notice is (CLP-05-001), carrying the next number the CASE_MANAGER
    expects as ``expectedSenderSequence`` so the sender resumes there
    (SYNC-21-015, SYNC-21-007).  It writes no state; its id is derived from
    the CASE_MANAGER and the refused activity, so a retry queues it once.
    """

    def __init__(
        self,
        case_id: str,
        classify: ClassifySequenceNumberNode,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._classify = classify

    def _call_factory(self) -> tuple[str, str]:
        order = self._classify.order
        if order is None:
            raise VultronWiringError(
                f"{self.name}: no classified number to refuse (SYNC-21-015)"
            )
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        assert self.datalayer is not None
        return self.trigger_activity_factory.refusal_notice(
            case_id=self._case_id,
            actor=self.actor_id,
            # The body intake archived, as the sender sent it (CLP-05-001).
            refused_activity=held_received_body(
                self.datalayer, self._classify.activity_id
            ),
            asserter=self._classify.sender_id,
            reason=self._classify.refusal_reason(),
            expected_sender_sequence=order.next_expected,
        )

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        self.logger.info(
            "CASE_MANAGER '%s' sent refusal notice '%s' to '%s' for activity"
            " '%s' on case '%s': %s (SYNC-21-015)",
            self.actor_id,
            activity_id,
            self._classify.sender_id,
            self._classify.activity_id,
            self._case_id,
            self._classify.refusal_reason(),
        )


class SequenceAdmitsNode(DataLayerConditionWithPorts):
    """Condition: the activity is judged now, in its sender's order.

    Fails for a held activity, a repeat answered here and a refused number,
    naming why in its feedback, so the tree stops before anything judges
    the act; the handler reads the standing for its verdict.
    """

    def __init__(
        self, classify: ClassifySequenceNumberNode, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.classify = classify

    def update(self) -> Status:
        if self.classify.standing in JUDGED:
            return Status.SUCCESS
        self.feedback_message = self.classify.refusal_reason()
        if self.classify.standing in NOTICED:
            self.logger.warning("%s: %s", self.name, self.feedback_message)
        else:
            self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE
