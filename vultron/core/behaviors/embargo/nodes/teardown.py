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

from vultron.core.behaviors.embargo.nodes.em_state import ReadEmStateNode
from vultron.core.behaviors.embargo.nodes.emit import _SendEmbargoActivityBase
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.narrative_log import log_em_transition
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.dimensions import EmDimension
from vultron.core.states.em import EM, is_valid_em_transition
from vultron.core.use_cases._helpers import (
    _as_id,
    reset_case_participant_embargo_consent,
    _resolve_case_manager_id,
)


class HasEmbargoActiveNode(DataLayerConditionWithPorts):
    """Condition: EM state is ACTIVE or REVISE (embargo is active).

    Returns SUCCESS when ``case.current_status.em.state`` is not EXITED
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

        result_out: dict[str, object] = {}
        read_node = ReadEmStateNode(
            case_id=self.case_id, result_out=result_out
        )
        read_node.datalayer = self.datalayer
        read_status = read_node.update()
        if read_status != Status.SUCCESS:
            self.feedback_message = read_node.feedback_message
            return Status.FAILURE

        em_state = result_out["em_before"]
        assert isinstance(em_state, EM)
        if em_state == EM.EXITED:
            self.feedback_message = f"Case '{self.case_id}' EM already EXITED — teardown not needed"
            return Status.FAILURE

        return Status.SUCCESS


class ClearActiveEmbargoNode(DataLayerActionWithPorts):
    """Apply EM → EXITED transition and clear active_embargo.

    Reads the current EM state via ``ReadEmStateNode``, transitions
    ``em_state`` to EXITED, clears ``active_embargo = None``, and persists
    both fields in a single ``datalayer.save()`` (batched write — AC-3 of
    issue #1554).

    Handles idempotency: returns SUCCESS without modifying state when EM is
    already EXITED.  Logs a WARNING for non-standard transitions (state-sync
    override).
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        result_out: dict[str, object] = {}
        read_node = ReadEmStateNode(
            case_id=self.case_id, result_out=result_out
        )
        read_node.datalayer = self.datalayer
        read_status = read_node.update()
        if read_status != Status.SUCCESS:
            self.feedback_message = read_node.feedback_message
            return Status.FAILURE
        current_em = result_out["em_before"]
        assert isinstance(current_em, EM)

        if current_em == EM.EXITED:
            self.feedback_message = (
                f"Case '{self.case_id}' EM already EXITED — idempotent no-op"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

        if not is_valid_em_transition(current_em, EM.EXITED):
            self.logger.warning(
                "%s: EM transition %s → EXITED is not a standard machine"
                " transition for case '%s'; applying state-sync override",
                self.name,
                current_em,
                self.case_id,
            )

        case = self.datalayer.read(self.case_id)
        if not isinstance(case, VulnerabilityCase):
            self.feedback_message = f"Case '{self.case_id}' not found"
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        case.current_status.em = EmDimension(state=EM.EXITED)
        case.active_embargo = None
        self.datalayer.save(case)

        self.feedback_message = (
            f"Cleared active embargo on case '{self.case_id}'"
            f" (EM {current_em} → EXITED)"
        )
        self.logger.debug("%s: %s", self.name, self.feedback_message)
        # SL-04-001/SL-04-006: embargo teardown is a protocol milestone.
        log_em_transition(
            self.logger,
            self.actor_id or "<unknown>",
            self.case_id,
            current_em,
            EM.EXITED,
        )
        return Status.SUCCESS


class ResetParticipantConsentNode(DataLayerActionWithPorts):
    """Reset all participant embargo consent states to NO_EMBARGO.

    Calls ``reset_case_participant_embargo_consent`` for the given case.
    Returns FAILURE when the case is not found.  Returns SUCCESS when
    consent reset completes (including when the case has no participants).
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case = self.datalayer.read(self.case_id)
        if not isinstance(case, VulnerabilityCase):
            self.feedback_message = f"Case '{self.case_id}' not found"
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        reset_case_participant_embargo_consent(self.datalayer, case)
        self.feedback_message = (
            f"Reset participant embargo consent for case '{self.case_id}'"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class ApplyEmbargoTeardownNode(DataLayerActionWithPorts):
    """Apply receiver-side embargo teardown.

    Performs the ACTIVE/REVISE → EXITED EM state transition, clears
    ``active_embargo``, and resets all participant embargo consent states.
    Handles idempotency: if EM state is already EXITED, logs and returns
    SUCCESS without modifying the DataLayer.

    For unexpected EM states a state-sync override is applied (the sender
    is authoritative) with a WARNING log entry, mirroring the pattern used
    by ``AddEmbargoEventToCaseReceivedUseCase``.

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

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["activity"] = PortInformation(data_type=object, required=False)
        return ports

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
            from vultron.core.behaviors.sync.nodes import _require_log_entry

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

        reset_node = ResetParticipantConsentNode(case_id=case_id)
        reset_node.datalayer = self.datalayer
        reset_node.update()

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

    Used immediately after ``ApplyEmbargoTeardownNode`` in the
    ``ActiveTeardown`` sequence of ``remove_embargo_from_case_tree`` so
    that all participants receive a protocol-level announcement of the
    embargo termination.
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(case_id=case_id, name=name)
        self._embargo_id = embargo_id

    def _on_factory_unavailable(self) -> Status:
        self.feedback_message = (
            "trigger_activity_factory not available"
            " — Announce(EmbargoEvent) skipped"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS

    def _resolve_embargo_and_manager(self) -> "tuple[str, str] | Status":
        assert self.datalayer is not None
        try:
            case = self.datalayer.read(self._case_id)
        except Exception as exc:
            self.feedback_message = (
                f"Failed to read case '{self._case_id}': {exc}"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        if not isinstance(case, VulnerabilityCase):
            self.feedback_message = f"Case '{self._case_id}' not found"
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        case_manager_id = _resolve_case_manager_id(case, self.datalayer)
        if case_manager_id is None:
            self.feedback_message = (
                f"No Case Manager found for case '{self._case_id}'"
                " — Announce(EmbargoEvent) skipped"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
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
            to=[case_manager_id],
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


class RemoveFromProposedEmbargoesNode(DataLayerActionWithPorts):
    """Remove the embargo from the case's proposed_embargoes list.

    Idempotent cleanup: returns SUCCESS if embargo successfully removed or was
    not in proposed_embargoes (nothing to remove). Returns FAILURE only if the
    case cannot be read (critical prerequisite missing).

    Saves the case only when a change is made.
    """

    def __init__(self, case_id: str, embargo_id: str, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.embargo_id = embargo_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case = self.datalayer.read(self.case_id)
        if not isinstance(case, VulnerabilityCase):
            self.feedback_message = f"Case '{self.case_id}' not found"
            return Status.FAILURE

        proposed_ids = [_as_id(e) for e in case.proposed_embargoes]
        if self.embargo_id in proposed_ids:
            case.proposed_embargoes = [
                e
                for e in case.proposed_embargoes
                if _as_id(e) != self.embargo_id
            ]
            self.datalayer.save(case)
            self.feedback_message = (
                f"Removed embargo '{self.embargo_id}' from proposed_embargoes"
                f" of case '{self.case_id}'"
            )
            self.logger.info(
                "RemoveFromProposedEmbargoes: %s", self.feedback_message
            )
        else:
            self.feedback_message = (
                f"Embargo '{self.embargo_id}' not in proposed_embargoes"
                f" of case '{self.case_id}' — nothing to remove"
            )

        return Status.SUCCESS
