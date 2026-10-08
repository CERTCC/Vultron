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

"""Embargo removal and teardown nodes."""

from py_trees.common import Status
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.embargo.nodes.em_state import read_case_em_state
from vultron.core.behaviors.embargo.nodes.emit import _SendEmbargoActivityBase
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.narrative_log import log_em_transition
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.behaviors.sync.nodes import _require_log_entry
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.participants.recipients import case_content_recipients
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    TransitionMode,
)
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import TerminationReason
from vultron.errors import BtNodePreconditionError, VultronNotFoundError


class HasEmbargoActiveNode(DataLayerConditionWithPorts):
    """Condition: EM state is ACTIVE or REVISE (embargo is active).

    Returns SUCCESS when ``case.em_state`` is not EXITED
    (i.e., the embargo is still active and teardown has not been applied).
    Returns FAILURE when EM is EXITED (teardown already done — idempotent
    guard) or when the case is not found.

    Uses ``ReadEmStateNode`` to read EM state (AC-1 of issue #1554).
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        try:
            em_state = read_case_em_state(self.datalayer, self.case_id)
        except BtNodePreconditionError as exc:
            self.feedback_message = str(exc)
            return Status.FAILURE

        if em_state == EM.EXITED:
            self.feedback_message = f"Case '{self.case_id}' EM already EXITED — teardown not needed"
            return Status.FAILURE

        return Status.SUCCESS


class ClearActiveEmbargoNode(DataLayerActionWithPorts, StateWriteCapable):
    """Terminate the embargo in force, so EM derives ``EXITED``.

    Reads the current EM state via ``ReadEmStateNode``, then delegates to
    ``EmbargoLifecycle.terminate_active_embargo()`` in OBSERVED mode
    (EMB-18-001): one register step terminates the ``ACTIVE`` entry and
    cancels every open proposal (EP-08-004, ADR-0122), in one
    ``datalayer.save()``.  A ``Remove`` ends the embargo before its end time,
    so the reason passed is ``EARLY`` (stored once #4293 carries it).

    Handles idempotency: returns SUCCESS without modifying state when EM is
    already EXITED.  A case with no embargo in force is also left unchanged
    and returns SUCCESS, but reports the skip and logs no EM transition;
    :attr:`applied` tells a caller which happened.
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        #: True only when this tick terminated an embargo.
        self.applied = False

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        try:
            current_em = read_case_em_state(self.datalayer, self.case_id)
        except BtNodePreconditionError as exc:
            self.feedback_message = str(exc)
            return Status.FAILURE

        if current_em == EM.EXITED:
            self.feedback_message = (
                f"Case '{self.case_id}' EM already EXITED — idempotent no-op"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

        # EMB-18-001: route the termination through EmbargoLifecycle.
        lifecycle = EmbargoLifecycle(persistence=self.datalayer)
        try:
            result = lifecycle.terminate_active_embargo(
                case_id=self.case_id,
                reason=TerminationReason.EARLY,
                actor_id=self.actor_id,
                transition_mode=TransitionMode.OBSERVED,
            )
        except VultronNotFoundError as exc:
            self.feedback_message = str(exc)
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        em_after = result.em_after
        if not result.case_changed:
            # The lifecycle has already warned; no teardown happened here.
            self.feedback_message = (
                f"No embargo in force on case '{self.case_id}'"
                f" (EM {current_em}) — teardown skipped"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

        self.applied = True
        self.feedback_message = (
            f"Cleared active embargo on case '{self.case_id}'"
            f" (EM {current_em} → {em_after})"
        )
        self.logger.debug("%s: %s", self.name, self.feedback_message)
        # SL-04-001/SL-04-006: embargo teardown is a protocol milestone.
        log_em_transition(
            self.logger,
            self.actor_id or "<unknown>",
            self.case_id,
            current_em,
            em_after,
        )
        return Status.SUCCESS


class ApplyEmbargoTeardownNode(DataLayerActionWithPorts, StateWriteCapable):
    """Apply receiver-side embargo teardown.

    Terminates the register's ``ACTIVE`` entry and cancels every open
    proposal in one step, so EM derives ``EXITED``; participant consent needs
    no write, because with no embargo in force nobody is bound (ADR-0122).
    Handles idempotency: if EM state is already EXITED, logs and returns
    SUCCESS without modifying the DataLayer.

    A case with no embargo in force is left unchanged with a WARNING: the
    register is never forced into a state its rules refuse.

    When ``case_id`` is not provided at construction (``None``), the node
    reads it from the log entry in the blackboard ``activity`` key.  This
    allows the node to be shared between the ``RemoveEmbargoFromCaseBT``
    (construction-time ``case_id``) and the
    ``AnnounceLogEntryReceivedBT`` participant subtree (blackboard
    ``activity``).
    """

    def __init__(self, case_id: str | None = None, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def initialise(self) -> None:
        super().initialise()
        if self.case_id is None:
            try:
                self._activity = self.get_input("activity")
            except (NoDataAvailable, NotImplementedError):
                self._activity = None
        else:
            self._activity = None

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        if self.case_id is not None:
            case_id = self.case_id
        else:
            entry = _require_log_entry(self._activity, self.name)
            case_id = entry.case_id

        # AC-1: delegate EM state read/write to canonical nodes.
        clear_node = ClearActiveEmbargoNode(case_id=case_id)
        clear_node.datalayer = self.datalayer
        clear_node.actor_id = self.actor_id
        if clear_node.update() != Status.SUCCESS:
            self.feedback_message = (
                f"Case '{case_id}' not found — teardown skipped"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

        if not clear_node.applied:
            self.feedback_message = clear_node.feedback_message
            return Status.SUCCESS

        self.feedback_message = f"Embargo teardown applied on case '{case_id}'"
        self.logger.debug("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class SendAnnounceEmbargoEventNode(_SendEmbargoActivityBase):
    """Emit an ``Announce(EmbargoEvent)`` after embargo teardown.

    Resolves the Case Manager actor ID from the case, builds the outbound
    ``Announce(EmbargoEvent)`` activity via ``trigger_activity_factory``,
    and queues it to the actor's outbox.

    Best-effort semantics: returns SUCCESS with a WARNING log when the
    factory is unavailable, no Case Manager can be resolved, or the outbox
    write fails after the activity is already constructed — teardown must
    not be blocked by notification gaps.  Returns FAILURE only on hard data
    errors (case read fails, case not found, factory dispatch raises).

    Used immediately after ``ClearActiveEmbargoNode`` in the CASE_MANAGER's
    ``ActiveTeardown`` sequence of ``remove_embargo_from_case_tree`` so
    that all participants receive a protocol-level announcement of the
    embargo termination; a participant replica's arm never runs it
    (BT-17-008).
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(case_id=case_id, name=name)
        self._embargo_id = embargo_id
        self._recipients: list[str] = []

    def _on_factory_unavailable(self) -> Status:
        self.feedback_message = (
            "trigger_activity_factory not available"
            " — Announce(EmbargoEvent) skipped"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS

    def _resolve_embargo_and_manager(self) -> "tuple[str, str] | Status":
        assert self.datalayer is not None
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        case_manager_id = resolve_case_manager_id(case, self.datalayer)
        if case_manager_id is None:
            self.feedback_message = (
                f"No Case Manager found for case '{self._case_id}'"
                " — Announce(EmbargoEvent) skipped"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

        # Recipients are every *other* participant, not the Case Manager.  This
        # node runs in the CASE_MANAGER arm of `remove_embargo_from_case_tree`
        # (its `manager_effects`), so the executing actor *is* the manager —
        # addressing the announce to the manager addressed it to itself and the
        # teardown reached nobody.  The Case Manager is still resolved above,
        # because "the case has a manager" remains the precondition for
        # announcing canonical case state at all.
        # Only active participants receive the announce (CM-10-004); the shared
        # selection decides who those are (CM-10-007).
        self._recipients = case_content_recipients(
            case, self.datalayer, excluding={self.actor_id or ""}
        )
        if not self._recipients:
            self.feedback_message = (
                f"No other participants on case '{self._case_id}'"
                " — Announce(EmbargoEvent) skipped"
            )
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

        return self._embargo_id, case_manager_id

    def _call_factory(
        self, actor_id: str, embargo_id: str, case_manager_id: str
    ) -> tuple[str, object]:
        assert self.trigger_activity_factory is not None
        return self.trigger_activity_factory.announce_embargo(
            embargo_id=embargo_id,
            case_id=self._case_id,
            actor=actor_id,
            to=self._recipients,
        )

    def _on_outbox_write_failure(
        self, activity_id: str, exc: Exception
    ) -> Status:
        self.feedback_message = (
            f"Outbox write failed for Announce(EmbargoEvent)"
            f" '{activity_id}': {exc}"
            " — activity constructed but not queued"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS
