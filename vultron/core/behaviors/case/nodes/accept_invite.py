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
"""BT leaf node for emitting Add(CaseParticipant) after a successful invite acceptance."""

import logging
from typing import cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.vultron_types import VultronParticipant
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.behaviors.case.nodes.suggest_actor._snapshot import (
    _snapshot_with_context,
)

logger = logging.getLogger(__name__)


class EmitAddCaseParticipantNode(DataLayerAction):
    """Emit Add(CaseParticipant, Case) and commit a canonical ledger entry.

    Called by the CaseActor after persisting the new invitee participant
    (``PersistInviteeParticipantNode``).  Fans the ``Add(CaseParticipant, Case)``
    activity out to all current case participants so they can update their
    local replica, and commits the corresponding canonical
    ``CaseLedgerEntry(disposition="recorded")`` to the hash chain.

    Uses ``trigger_activity_factory.add_participant_to_case()`` to build and
    persist the activity.  The activity's ``payloadSnapshot`` is built with
    ``context=case_id`` injected so ``_validate_canonical_entry`` can verify
    the ``("Add", "CaseParticipant")`` signature (CLP-07-005).

    Fan-out recipients are resolved from ``case.actor_participant_index`` (HTTP
    actor URLs), excluding the newly added invitee.  The index keys are always
    proper HTTP URIs, unlike ``case.case_participants`` which may contain bare
    UUID participant IDs that cannot serve as inbox delivery targets.
    """

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.invitee_id = invitee_id

    def setup(self, **kwargs) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="new_invite_participant",
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key="invitee_already_participant",
            access=py_trees.common.Access.READ,
        )

    def _is_already_done(self) -> bool:
        """Return True if invitee was already a participant (idempotency skip)."""
        try:
            return bool(self.blackboard.get("invitee_already_participant"))
        except KeyError:
            return False

    def _resolve_actor_recipients(self) -> list[str]:
        """Return HTTP actor URLs for all existing participants, excluding the new invitee.

        Uses ``case.actor_participant_index`` (keys are actor HTTP URLs) rather
        than ``case.case_participants`` (which may contain bare UUID strings that
        are not valid delivery addresses).
        """
        case = self.datalayer.read(self.case_id)  # type: ignore[union-attr]
        if not isinstance(case, VulnerabilityCase):
            return []
        return [
            actor_url
            for actor_url in case.actor_participant_index
            if actor_url != self.invitee_id
        ]

    def _build_snapshot(self, activity_id: str) -> dict:
        stored = self.datalayer.read(activity_id)  # type: ignore[union-attr]
        if stored is not None and hasattr(stored, "model_dump"):
            raw: dict = stored.model_dump(
                mode="json",
                by_alias=True,
                serialize_as_any=True,
                exclude_none=True,
            )
            snapshot: dict = _snapshot_with_context(raw, self.case_id)
        else:
            snapshot = {
                "type": "Add",
                "actor": self.actor_id or "",
                "object_": {"type": "CaseParticipant"},
                "context": self.case_id,
            }
        if not snapshot.get("actor") and self.actor_id:
            snapshot = {**snapshot, "actor": self.actor_id}
        return snapshot

    def _emit_activity(
        self, participant_id: str, actor_id: str, others: list[str]
    ) -> str:
        factory = self.trigger_activity_factory
        return factory.add_participant_to_case(  # type: ignore[union-attr]
            participant_id=participant_id,
            case_id=self.case_id,
            actor=actor_id,
            to=others or None,
        )

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        if self._is_already_done():
            return Status.SUCCESS

        if self.trigger_activity_factory is None:
            self.logger.warning(
                "%s: trigger_activity_factory not available;"
                " cannot emit Add(CaseParticipant) for case '%s'",
                self.name,
                self.case_id,
            )
            return Status.SUCCESS

        participant = self.blackboard.get("new_invite_participant")
        if not isinstance(participant, (CaseParticipant, VultronParticipant)):
            self.logger.error(
                "%s: new_invite_participant not available", self.name
            )
            return Status.FAILURE

        participant_id = _as_id(participant)
        if not participant_id:
            self.logger.error(
                "%s: could not resolve participant_id from %r",
                self.name,
                participant,
            )
            return Status.FAILURE

        others = self._resolve_actor_recipients()
        actor_id: str = self.actor_id  # type: ignore[assignment]
        try:
            activity_id = self._emit_activity(participant_id, actor_id, others)
        except Exception as exc:
            self.logger.error(
                "%s: add_participant_to_case failed: %s", self.name, exc
            )
            return Status.FAILURE

        snapshot = self._build_snapshot(activity_id)
        commit_tree = create_commit_log_entry_tree(
            case_id=self.case_id,
            object_id=activity_id,
            event_type="add_case_participant",
            payload_snapshot=snapshot,
            disposition="recorded",
        )
        result = BTBridge(
            datalayer=cast(CaseOutboxPersistence, self.datalayer)
        ).execute_with_setup(
            tree=commit_tree,
            actor_id=self.actor_id,
        )
        if result.status != Status.SUCCESS:
            self.logger.error(
                "%s: ledger commit failed for add_case_participant/%s",
                self.name,
                participant_id,
            )
            return Status.FAILURE

        cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
            self.actor_id, activity_id
        )
        self.logger.info(
            "%s: emitted Add(CaseParticipant '%s') for case '%s'"
            " and committed canonical ledger entry",
            self.name,
            participant_id,
            self.case_id,
        )
        return Status.SUCCESS


__all__ = ["EmitAddCaseParticipantNode"]
