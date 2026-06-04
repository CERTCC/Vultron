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

"""
BT nodes for receive-side embargo lifecycle workflows.

Implements the receiver-side embargo removal workflow triggered by receipt
of a ``Remove(EmbargoEvent)`` activity (protocol ET message):

    RemoveEmbargoFromCaseBT (Sequence)
    ├─ ValidateCaseExistsNode          # case must be found and pass is_case_model
    ├─ RemoveFromProposedEmbargoesNode # idempotent cleanup of proposed list
    ├─ IsActiveEmbargoNode             # guard: is this the active embargo?
    └─ ApplyEmbargoTeardownNode        # ACTIVE/REVISE→EXITED, clear, reset PEC

``ApplyEmbargoTeardownNode`` is also used in the
``AnnounceLogEntryReceivedBT`` participant subtree (via
``announce_tree.create_announce_log_entry_tree``), where it reads the
``case_id`` from the log entry on the blackboard instead of receiving it
at construction time.

Per specs/behavior-tree-integration.yaml BT-06-001.
"""

from typing import cast

import py_trees
from py_trees.common import Status
from transitions import MachineError

from vultron.core.behaviors.helpers import DataLayerAction, DataLayerCondition
from vultron.core.models.protocols import CaseModel, is_case_model
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.states.em import (
    EM,
    EMAdapter,
    create_em_machine,
    is_valid_em_transition,
)
from vultron.core.use_cases._helpers import (
    _resolve_case_manager_id,
    reset_case_participant_embargo_consent,
)
from vultron.core.use_cases.triggers._helpers import add_activity_to_outbox


class ValidateCaseExistsNode(DataLayerCondition):
    """Check that the target case exists in the DataLayer.

    Returns SUCCESS if the case is found and passes ``is_case_model``.
    Returns FAILURE otherwise, halting the parent Sequence.
    """

    def __init__(self, case_id: str, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE

        case = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            self.feedback_message = (
                f"Case '{self.case_id}' not found or not a valid case model"
            )
            self.logger.warning(
                "ValidateCaseExists: %s", self.feedback_message
            )
            return Status.FAILURE

        return Status.SUCCESS


class ApplyEmbargoTeardownNode(DataLayerAction):
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

    def setup(self, **kwargs: object) -> None:
        super().setup(**kwargs)
        if self.case_id is None:
            self.blackboard.register_key(
                key="activity", access=py_trees.common.Access.READ
            )

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE

        if self.case_id is not None:
            case_id = self.case_id
        else:
            from vultron.core.behaviors.sync.nodes import _require_log_entry

            entry = _require_log_entry(self.blackboard.activity, self.name)
            case_id = entry.case_id

        case = self.datalayer.read(case_id)
        if not is_case_model(case):
            self.feedback_message = f"Case '{case_id}' not found"
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

        current_em = case.current_status.em_state

        if current_em == EM.EXITED:
            self.feedback_message = (
                f"Case '{case_id}' EM already EXITED — idempotent no-op"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

        if not is_valid_em_transition(current_em, EM.EXITED):
            self.logger.warning(
                "%s: EM transition %s → EXITED is not a standard machine"
                " transition for case '%s'; applying state-sync override",
                self.name,
                current_em,
                case_id,
            )

        case.current_status.em_state = EM.EXITED
        case.active_embargo = None
        reset_case_participant_embargo_consent(self.datalayer, case)
        self.datalayer.save(case)

        self.feedback_message = (
            f"Embargo teardown applied on case '{case_id}'"
            f" (EM {current_em} → EXITED)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class IsActiveEmbargoNode(DataLayerCondition):
    """Check that the given embargo is the active embargo on the case.

    Returns SUCCESS if ``case.active_embargo`` resolves to ``embargo_id``.
    Returns FAILURE if the embargo is not active (e.g. it was only proposed),
    halting the parent Sequence so the teardown path is skipped.
    """

    def __init__(self, case_id: str, embargo_id: str, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.embargo_id = embargo_id

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE

        case = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            self.feedback_message = f"Case '{self.case_id}' not found"
            return Status.FAILURE

        active = case.active_embargo
        active_id = (
            active if isinstance(active, str) else getattr(active, "id_", None)
        )
        if active_id != self.embargo_id:
            self.feedback_message = (
                f"Embargo '{self.embargo_id}' is not the active embargo"
                f" on case '{self.case_id}'"
            )
            return Status.FAILURE

        return Status.SUCCESS


class RemoveFromProposedEmbargoesNode(DataLayerAction):
    """Remove the embargo from the case's proposed_embargoes list.

    Idempotent: returns SUCCESS even if the embargo is not in proposed_embargoes.
    Saves the case only when a change is made.
    """

    def __init__(self, case_id: str, embargo_id: str, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.embargo_id = embargo_id

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE

        case = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            self.feedback_message = f"Case '{self.case_id}' not found"
            return Status.FAILURE

        def _as_id(obj: object) -> str | None:
            return obj if isinstance(obj, str) else getattr(obj, "id_", None)

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


class TerminateEmbargoNode(DataLayerAction):
    """Trigger-side embargo teardown for a given case.

    Applies the ACTIVE/REVISE → EXITED EM state transition via the state
    machine, clears ``active_embargo``, resets all participant embargo
    consent states, and queues a ``Terminate(EmbargoEvent)`` activity when a
    ``trigger_activity_factory`` is available.

    Always returns SUCCESS.  Failures (no active embargo, invalid EM
    transition, activity dispatch errors) are logged as WARNING and are
    treated as non-fatal.
    """

    def __init__(self, case_id: str | None, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def update(self) -> Status:
        if self.datalayer is None or not self.case_id:
            return Status.SUCCESS

        case = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            return Status.SUCCESS

        if case.active_embargo is None:
            self.logger.info(
                "%s: no active embargo on case '%s' — skipping",
                self.name,
                self.case_id,
            )
            return Status.SUCCESS

        em_state = case.current_status.em_state
        adapter = EMAdapter(em_state)
        em_machine = create_em_machine()
        em_machine.add_model(adapter, initial=em_state)

        try:
            getattr(adapter, "terminate")()
        except MachineError:
            self.logger.warning(
                "%s: EM %s → EXITED blocked for case '%s'",
                self.name,
                em_state,
                self.case_id,
            )
            return Status.SUCCESS

        embargo_id = (
            case.active_embargo
            if isinstance(case.active_embargo, str)
            else getattr(case.active_embargo, "id_", None)
        )
        case_manager_id = _resolve_case_manager_id(
            cast(CaseModel, case), self.datalayer
        )

        case.current_status.em_state = EM(adapter.state)
        case.active_embargo = None
        reset_case_participant_embargo_consent(self.datalayer, case)
        self.datalayer.save(case)

        self.logger.info(
            "%s: embargo terminated on case '%s' (EM %s → %s)",
            self.name,
            self.case_id,
            em_state,
            adapter.state,
        )

        self._dispatch_activity(embargo_id, case_manager_id)
        return Status.SUCCESS

    def _dispatch_activity(
        self, embargo_id: str | None, case_manager_id: str | None
    ) -> None:
        """Queue a Terminate(EmbargoEvent) activity to the case manager's outbox.

        No-ops when ``trigger_activity_factory`` is unavailable, ``embargo_id``
        is missing, or the case manager cannot be resolved.  Activity dispatch
        failures are logged as WARNING and do not affect the BT return value.
        """
        if (
            self.trigger_activity_factory is None
            or embargo_id is None
            or self.datalayer is None
        ):
            return

        if case_manager_id is None:
            self.logger.warning(
                "%s: no CASE_MANAGER found for case '%s'"
                " — activity dispatch skipped",
                self.name,
                self.case_id,
            )
            return

        try:
            case_id: str = self.case_id  # type: ignore[assignment]  # guarded above
            announce_id, _ = self.trigger_activity_factory.terminate_embargo(
                embargo_id=embargo_id,
                case_id=case_id,
                actor=case_manager_id,
                to=[case_manager_id],
            )
            add_activity_to_outbox(
                case_manager_id,
                announce_id,
                cast(CaseOutboxPersistence, self.datalayer),
            )
        except Exception as exc:
            self.logger.warning(
                "%s: activity dispatch failed for case '%s': %s",
                self.name,
                self.case_id,
                exc,
            )
