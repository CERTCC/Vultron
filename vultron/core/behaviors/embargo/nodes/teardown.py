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

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.dimensions import EmDimension
from vultron.core.states.em import EM, is_valid_em_transition
from vultron.core.use_cases._helpers import (
    _as_id,
    add_activity_to_outbox,
    reset_case_participant_embargo_consent,
    _resolve_case_manager_id,
)


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
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        if self.case_id is not None:
            case_id = self.case_id
        else:
            from vultron.core.behaviors.sync.nodes import _require_log_entry

            entry = _require_log_entry(self.blackboard.activity, self.name)
            case_id = entry.case_id

        case = self.datalayer.read(case_id)
        if not isinstance(case, VulnerabilityCase):
            self.feedback_message = f"Case '{case_id}' not found"
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

        current_em = case.current_status.em.state

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

        case.current_status.em = EmDimension(state=EM.EXITED)
        case.active_embargo = None
        reset_case_participant_embargo_consent(self.datalayer, case)
        self.datalayer.save(case)

        self.feedback_message = (
            f"Embargo teardown applied on case '{case_id}'"
            f" (EM {current_em} → EXITED)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class SendAnnounceEmbargoEventNode(DataLayerAction):
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
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._embargo_id = embargo_id

    def _build_and_queue_announce(
        self, actor_id: str, case_manager_id: str
    ) -> Status:
        """Build the Announce(EmbargoEvent) activity and write it to the outbox.

        Separated from ``update()`` to keep cyclomatic complexity under the
        project limit.  Returns FAILURE if the factory call raises, SUCCESS
        (best-effort) if the outbox write fails after the activity is already
        constructed.
        """
        assert self.trigger_activity_factory is not None
        assert self.datalayer is not None

        try:
            announce_id, _ = self.trigger_activity_factory.announce_embargo(
                embargo_id=self._embargo_id,
                case_id=self._case_id,
                actor=actor_id,
                to=[case_manager_id],
            )
        except Exception as exc:
            self.feedback_message = (
                f"Announce(EmbargoEvent) factory failed for"
                f" case '{self._case_id}': {exc}"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        try:
            add_activity_to_outbox(
                actor_id,
                announce_id,
                self.datalayer,  # type: ignore[arg-type]
            )
        except Exception as exc:
            self.feedback_message = (
                f"Outbox write failed for Announce(EmbargoEvent)"
                f" '{announce_id}': {exc}"
                " — activity constructed but not queued"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

        self.feedback_message = (
            f"Queued Announce(EmbargoEvent) '{announce_id}'"
            f" for case '{self._case_id}'"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS

    def update(self) -> Status:
        if self.trigger_activity_factory is None:
            self.feedback_message = (
                "trigger_activity_factory not available"
                " — Announce(EmbargoEvent) skipped"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

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

        return self._build_and_queue_announce(self.actor_id, case_manager_id)


class RemoveFromProposedEmbargoesNode(DataLayerAction):
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
