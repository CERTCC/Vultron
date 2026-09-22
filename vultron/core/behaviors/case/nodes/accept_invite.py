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

import json
import logging
from typing import cast

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.helpers import (
    _EmitSingleActivityBase,
)
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.vultron_types import VultronParticipant
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.behaviors.case.nodes.suggest_actor._snapshot import (
    _snapshot_with_context,
)
from vultron.errors import VultronValidationError

logger = logging.getLogger(__name__)


class EmitAddCaseParticipantNode(_EmitSingleActivityBase):
    """Emit Add(CaseParticipant, Case) and commit a canonical ledger entry.

    Called by the CaseActor after persisting the new invitee participant
    (``PersistInviteeParticipantNode``).  Fans the ``Add(CaseParticipant, Case)``
    activity out to all current case participants so they can update their
    local replica, and commits the corresponding canonical
    ``CaseLedgerEntry`` to the hash chain.

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
        super().__init__(name=name)
        self.case_id = case_id
        self.invitee_id = invitee_id

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["new_invite_participant"] = PortInformation(
            data_type=object, required=False
        )
        ports["invitee_already_participant"] = PortInformation(
            data_type=bool, required=False
        )
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "new_invite_participant": "/new_invite_participant",
            "invitee_already_participant": "/invitee_already_participant",
        }

    def initialise(self) -> None:
        super().initialise()
        self._new_invite_participant_bb = None
        self._invitee_already_participant_bb = None
        try:
            self._new_invite_participant_bb = self.get_input(
                "new_invite_participant"
            )
        except (NoDataAvailable, NotImplementedError):
            pass
        try:
            self._invitee_already_participant_bb = self.get_input(
                "invitee_already_participant"
            )
        except (NoDataAvailable, NotImplementedError):
            pass

    def _is_already_done(self) -> bool:
        """Return True if invitee was already a participant (idempotency skip)."""
        return bool(self._invitee_already_participant_bb)

    def _resolve_actor_recipients(self, case) -> list[str]:
        """Return HTTP actor URLs for all existing participants, excluding the new invitee.

        Uses ``case.actor_participant_index`` (keys are actor HTTP URLs) rather
        than ``case.case_participants`` (which may contain bare UUID strings that
        are not valid delivery addresses). The case is resolved (and its absence
        hard-failed) by ``update()`` via ``_require_case`` — Regime 1, ADR-0087.
        """
        return [
            actor_url
            for actor_url in case.actor_participant_index
            if actor_url != self.invitee_id
        ]

    def _build_snapshot(self, activity_id: str) -> dict:
        stored = self.datalayer.read(activity_id)  # type: ignore[union-attr]
        if stored is None or not hasattr(stored, "model_dump"):
            raise VultronValidationError(
                f"Add(CaseParticipant) activity '{activity_id}' not found in"
                " DataLayer; cannot build payload snapshot (ARCH-15-001)"
            )
        # ARCH-20-001 permits this ``by_alias=True``: the subject is the stored
        # ``Add(CaseParticipant)`` activity read straight back out of the
        # DataLayer, which hands it back already wire-shaped, and the result is a
        # ledger payload snapshot — AS2-shaped by definition (CLP-07-001).  No
        # wire shape is being synthesised for a core-branch object here.
        raw: dict = stored.model_dump(
            mode="json",
            by_alias=True,
            serialize_as_any=True,
            exclude_none=True,
        )
        snapshot: dict = _snapshot_with_context(raw, self.case_id)
        if not snapshot.get("actor") and self.actor_id:
            snapshot = {**snapshot, "actor": self.actor_id}
        return snapshot

    def _call_factory(self) -> tuple[str, str]:
        """Build Add(CaseParticipant) activity and commit the canonical ledger entry."""
        assert self.datalayer is not None
        assert self.actor_id is not None
        assert self.trigger_activity_factory is not None

        participant = self._new_invite_participant_bb
        participant_id = _as_id(participant)
        if not participant_id:
            raise ValueError(
                f"{self.name}: could not resolve participant_id from {participant!r}"
            )
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            raise RuntimeError(f"{self.name}: case '{self.case_id}' not found")
        others = self._resolve_actor_recipients(case)
        activity_id = self.trigger_activity_factory.add_participant_to_case(
            participant_id=participant_id,
            case_id=self.case_id,
            actor=self.actor_id,
            to=others or None,
        )
        snapshot = self._build_snapshot(activity_id)
        commit_tree = create_commit_log_entry_tree(
            case_id=self.case_id,
            object_id=activity_id,
            event_type="add_case_participant",
            payload_snapshot=snapshot,
        )
        result = BTBridge(
            datalayer=cast(CaseOutboxPersistence, self.datalayer)
        ).execute_with_setup(tree=commit_tree, actor_id=self.actor_id)
        if result.status != Status.SUCCESS:
            raise RuntimeError(
                f"{self.name}: ledger commit failed for"
                f" add_case_participant/{participant_id}"
            )
        return activity_id, json.dumps(snapshot)

    def _on_success(self, activity_id: str, activity_blob: str) -> None:
        participant_id = _as_id(self._new_invite_participant_bb)
        self.logger.info(
            "%s: emitted Add(CaseParticipant '%s') for case '%s'"
            " and committed canonical ledger entry",
            self.name,
            participant_id,
            self.case_id,
        )

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        if self._is_already_done():
            return Status.SUCCESS

        # SHOULD-level (ADR-0087): no factory is not an error for this node.
        if self.trigger_activity_factory is None:
            self.logger.warning(
                "%s: trigger_activity_factory not available;"
                " cannot emit Add(CaseParticipant) for case '%s'",
                self.name,
                self.case_id,
            )
            return Status.SUCCESS

        participant = self._new_invite_participant_bb
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

        try:
            activity_id, activity_blob = self._call_factory()
            self._emit_through_seam(activity_id, activity_blob)
        except Exception as exc:
            # Includes Regime 1 (ADR-0087, #3101) case-not-found:
            # a missing case is an anomaly, not a silent empty-recipient
            # emit+commit.
            self.logger.error(
                "%s: add_case_participant emit failed: %s", self.name, exc
            )
            return Status.FAILURE
        self._on_success(activity_id, activity_blob)
        return Status.SUCCESS


__all__ = ["EmitAddCaseParticipantNode"]
