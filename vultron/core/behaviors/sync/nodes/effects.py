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

"""Side-effect action nodes for Announce(CaseLedgerEntry) received processing.

Provides action nodes that apply protocol-significant side effects when a
non-Case-Actor participant processes a ledger entry of a specific event type.

Currently implemented effects:

- :class:`ApplyParticipantStatusFromLedgerNode`: applies an
  ``add_participant_status_to_participant`` event to the local participant record.
- :class:`ApplyNoteFromLedgerNode`: applies an ``add_note_to_case`` event to
  the local case replica by attaching the note ID to ``notes``.
- :class:`ApplyInviteAcceptFromLedgerNode`: applies an
  ``accept_invite_actor_to_case`` event to the local case replica by creating
  a stub ``CaseParticipant`` for the new invitee and calling ``add_participant``.

Per specs/multi-actor-demo.yaml DEMOMA-07-003 step 3 and
specs/sync-ledger-replication.yaml SYNC-02-002.
"""

from __future__ import annotations

import logging
from typing import Any, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.participant_status import ParticipantStatus

logger = logging.getLogger(__name__)

_ADD_PARTICIPANT_STATUS_EVENT = "add_participant_status_to_participant"


def _extract_id_from_field(value: Any) -> str | None:
    """Return the string ID from an AS2 object field.

    Handles both inline dict (``{"id": "urn:uuid:..."}`` form) and bare
    string ID form.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("id")
    return None


class ApplyParticipantStatusFromLedgerNode(DataLayerAction):
    """Apply an ``add_participant_status_to_participant`` ledger entry locally.

    When a non-Case-Actor participant receives
    ``Announce(CaseLedgerEntry)`` and the entry's ``event_type`` is
    ``add_participant_status_to_participant``, this node reconstructs the
    :class:`~vultron.core.models.participant_status.ParticipantStatus` from
    the entry's ``payload_snapshot`` and appends it to the matching
    :class:`~vultron.core.models.case_participant.CaseParticipant` in the
    local DataLayer.

    The Case Actor is considered authoritative: RM-state validation is skipped
    (the Case Actor already validated the transition before committing the
    entry).  Idempotency is preserved — if the status ID is already present in
    the participant's list, the node returns SUCCESS without modifying the
    DataLayer.

    Lenient on missing data: if the participant is not found in the local
    DataLayer (this actor may have a partial view of the case), or the
    payload snapshot is incomplete, the node returns SUCCESS without error to
    avoid blocking the ``Announce`` processing flow.

    Per specs/multi-actor-demo.yaml DEMOMA-07-003 step 3,
    specs/sync-ledger-replication.yaml SYNC-02-002.
    """

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        from vultron.core.behaviors.sync.nodes.conditions import (
            _require_log_entry,
        )

        entry = _require_log_entry(self.blackboard.activity, self.name)
        snapshot = entry.payload_snapshot

        status_data = snapshot.get("object")
        target_data = snapshot.get("target")

        status_id = _extract_id_from_field(status_data)
        participant_id = _extract_id_from_field(target_data)

        if not status_id or not participant_id:
            self.logger.debug(
                "%s: payload_snapshot missing 'object' or 'target' id"
                " — skipping status apply (non-fatal)",
                self.name,
            )
            return Status.SUCCESS

        participant = self.datalayer.read(participant_id)
        if not isinstance(participant, CaseParticipant):
            self.logger.debug(
                "%s: participant '%s' not found in local DataLayer"
                " — skipping (non-fatal, partial case view)",
                self.name,
                participant_id,
            )
            return Status.SUCCESS

        existing_ids = [_as_id(s) for s in participant.participant_statuses]
        if status_id in existing_ids:
            self.logger.debug(
                "%s: status '%s' already present on participant '%s'"
                " — idempotent no-op",
                self.name,
                status_id,
                participant_id,
            )
            return Status.SUCCESS

        if not isinstance(status_data, dict):
            self.logger.warning(
                "%s: payload_snapshot 'object' is not a dict"
                " — cannot reconstruct ParticipantStatus for '%s'",
                self.name,
                status_id,
            )
            return Status.SUCCESS

        try:
            status_obj = ParticipantStatus.model_validate(status_data)
        except Exception as exc:
            self.logger.warning(
                "%s: failed to reconstruct ParticipantStatus from"
                " payload_snapshot for '%s': %s",
                self.name,
                status_id,
                exc,
            )
            return Status.SUCCESS

        if self.datalayer.read(status_id) is None:
            self.datalayer.save(status_obj)

        # Read back from the DataLayer to obtain the vocabulary-typed
        # (wire-format) version of the status object.  Appending the
        # core-model instance directly to ``participant_statuses``
        # (typed ``list[WireParticipantStatus]``) causes Pydantic to
        # serialize the list with default field values instead of the
        # actual values, because the declared element type governs
        # serialization when the runtime type differs.  Reading back
        # via the DataLayer reconstructs the object through the
        # vocabulary registry, returning the wire-format class that
        # round-trips correctly.
        status_from_dl = self.datalayer.read(status_id)
        if status_from_dl is None:
            self.logger.warning(
                "%s: status '%s' not readable from DataLayer after"
                " save — skipping participant update",
                self.name,
                status_id,
            )
            return Status.SUCCESS

        participant.participant_statuses.append(
            cast(ParticipantStatus, status_from_dl)
        )
        self.datalayer.save(participant)

        self.logger.info(
            "%s: applied ledger status update '%s' to participant '%s'"
            " (DEMOMA-07-003 step 3 receiver-side)",
            self.name,
            status_id,
            participant_id,
        )
        return Status.SUCCESS


class ApplyNoteFromLedgerNode(DataLayerAction):
    """Apply an ``add_note_to_case`` ledger entry to the local case replica.

    When a non-CaseActor participant receives ``Announce(CaseLedgerEntry)``
    and the entry's ``event_type`` is ``add_note_to_case``, this node
    extracts the note ID from ``payload_snapshot["object"]`` and appends it
    to the local case replica's ``notes`` list (idempotent).

    This is the canonical mechanism by which non-CaseActor participants
    learn about note additions — they must NOT update ``notes`` directly from
    ``Add(Note, Case)`` messages; only the CaseActor does that (ADR-0022,
    SYNC-02-002).

    Lenient on missing data: if the case replica is absent, the note ID is
    not present in the snapshot, or the snapshot is malformed, the node
    returns SUCCESS to avoid blocking the ``Announce`` processing flow.
    """

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        from vultron.core.behaviors.sync.nodes.conditions import (
            _require_log_entry,
        )

        entry = _require_log_entry(self.blackboard.activity, self.name)
        snapshot = entry.payload_snapshot

        note_id = _extract_id_from_field(snapshot.get("object"))
        case_id = entry.case_id

        if not note_id or not case_id:
            self.logger.debug(
                "%s: payload_snapshot missing 'object' id or case_id"
                " — skipping note apply (non-fatal)",
                self.name,
            )
            return Status.SUCCESS

        case = self.datalayer.read(case_id)
        if not isinstance(case, VulnerabilityCase):
            self.logger.debug(
                "%s: case '%s' not found in local DataLayer"
                " — skipping (non-fatal, partial case view)",
                self.name,
                case_id,
            )
            return Status.SUCCESS

        existing_ids = [_as_id(n) for n in case.notes]
        if note_id in existing_ids:
            self.logger.debug(
                "%s: note '%s' already in case '%s' — idempotent no-op",
                self.name,
                note_id,
                case_id,
            )
            return Status.SUCCESS

        case.notes.append(note_id)
        self.datalayer.save(case)
        self.logger.info(
            "%s: applied ledger note attachment '%s' to case '%s' (SYNC-02-002)",
            self.name,
            note_id,
            case_id,
        )
        return Status.SUCCESS


class ApplyInviteAcceptFromLedgerNode(DataLayerAction):
    """Apply an ``accept_invite_actor_to_case`` ledger entry to the local case replica.

    When a non-CaseActor participant receives ``Announce(CaseLedgerEntry)``
    and the entry's ``event_type`` is ``accept_invite_actor_to_case``, this
    node extracts the invitee actor ID from ``payload_snapshot["actor"]``,
    creates a stub ``CaseParticipant``, and calls ``case.add_participant()``
    to add the new participant to the local case replica (idempotent).

    This is the mechanism by which existing participants (e.g. the Finder)
    learn that a new actor (e.g. Vendor2) has joined the case — they MUST NOT
    update ``case_participants`` directly from ``Accept(Invite)`` messages;
    only the CaseActor does that. All other participants learn via this ledger
    entry effect (ADR-0022, SYNC-02-002, DEMOMA-07-003).

    Lenient on missing data: if the case replica is absent, the invitee ID
    cannot be extracted, or the participant is already present, the node
    returns SUCCESS to avoid blocking the ``Announce`` processing flow.
    """

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        from vultron.core.behaviors.sync.nodes.conditions import (
            _require_log_entry,
        )

        entry = _require_log_entry(self.blackboard.activity, self.name)
        snapshot = entry.payload_snapshot
        case_id = entry.case_id

        invitee_id = _extract_id_from_field(snapshot.get("actor"))
        if not invitee_id or not case_id:
            self.logger.debug(
                "%s: payload_snapshot missing 'actor' id or case_id"
                " — skipping invite-accept apply (non-fatal)",
                self.name,
            )
            return Status.SUCCESS

        case = self.datalayer.read(case_id)
        if not isinstance(case, VulnerabilityCase):
            self.logger.debug(
                "%s: case '%s' not found in local DataLayer"
                " — skipping (non-fatal, partial case view)",
                self.name,
                case_id,
            )
            return Status.SUCCESS

        if invitee_id in case.actor_participant_index:
            self.logger.debug(
                "%s: invitee '%s' already in actor_participant_index"
                " for case '%s' — idempotent no-op",
                self.name,
                invitee_id,
                case_id,
            )
            return Status.SUCCESS

        participant = CaseParticipant(
            id_=f"{case_id}/participants/{invitee_id.rstrip('/').rsplit('/', 1)[-1]}",
            attributed_to=invitee_id,
            context=case_id,
        )
        if self.datalayer.read(participant.id_) is None:
            self.datalayer.create(participant)

        case.add_participant(participant)
        self.datalayer.save(case)
        self.logger.info(
            "%s: applied ledger invite-accept for invitee '%s' to case '%s'"
            " (SYNC-02-002, DEMOMA-07-003)",
            self.name,
            invitee_id,
            case_id,
        )
        return Status.SUCCESS
