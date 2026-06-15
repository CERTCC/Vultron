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

"""Embargo persistence and log-cascade BT nodes."""

from typing import Any, cast

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.ports.case_persistence import CaseOutboxPersistence


class PersistEmbargoEventNode(DataLayerAction):
    """Persist the trigger-created embargo event before outbound fan-out."""

    def __init__(self, embargo: EmbargoEvent, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._embargo = embargo

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE
        try:
            self.datalayer.create(self._embargo)
        except ValueError:
            self.logger.warning(
                "EmbargoEvent '%s' already exists", self._embargo.id_
            )
        return Status.SUCCESS


class CommitLogCascadeNode(DataLayerAction):
    """Commit a CaseLedgerEntry and cascade to all participants.

    Resolves the CaseActor ID from case_id and triggers the
    ``commit_log_entry_trigger`` to create a log entry and fan it out
    to all participants.

    Returns SUCCESS when cascade succeeds. Returns FAILURE if cascade
    dispatch fails (per BT-14-001: peer broadcast nodes must not mask
    delivery failure with SUCCESS).

    This node is protocol-visible (fan-out to all participants). Per the
    spec requirement, it MUST propagate FAILURE to the BT when any step
    of the cascade (activity construction or outbox enqueue) fails.
    Masking failures with SUCCESS would cause silent state divergence.

    Idempotent: silently succeeds if case_id or object_id is None.
    """

    def __init__(
        self,
        case_id: str,
        object_id: str,
        event_type: str,
        name: str | None = None,
        payload_snapshot: dict[str, Any] | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.object_id = object_id
        self.event_type = event_type
        self.payload_snapshot = payload_snapshot

    def update(self) -> Status:
        from vultron.core.use_cases.received.actor import (
            _find_case_actor_id,
        )
        from vultron.core.use_cases.triggers.sync import (
            commit_log_entry_trigger,
        )

        if self.datalayer is None:
            return Status.SUCCESS

        if not self.case_id or not self.object_id:
            self.logger.warning(
                "%s: missing case_id or object_id — cascade skipped",
                self.name,
            )
            return Status.SUCCESS

        actor_id = _find_case_actor_id(self.datalayer, self.case_id)
        if actor_id is None:
            self.logger.warning(
                "%s: cannot resolve CaseActor for case '%s'"
                " — cascade skipped",
                self.name,
                self.case_id,
            )
            return Status.SUCCESS

        try:
            commit_log_entry_trigger(
                case_id=self.case_id,
                object_id=self.object_id,
                event_type=self.event_type,
                actor_id=actor_id,
                dl=cast(CaseOutboxPersistence, self.datalayer),
                sync_port=None,
                payload_snapshot=self.payload_snapshot,
            )
        except Exception as exc:
            self.feedback_message = (
                f"Cascade failed for case '{self.case_id}': {exc}"
            )
            self.logger.error(
                "%s: %s (BT-14-001: returning FAILURE)",
                self.name,
                self.feedback_message,
            )
            return Status.FAILURE

        self.feedback_message = (
            f"Committed log entry '{self.event_type}' for case"
            f" '{self.case_id}'"
        )
        return Status.SUCCESS
