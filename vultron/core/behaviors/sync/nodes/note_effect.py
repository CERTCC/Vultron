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

"""Ledger effect node for ``add_note_to_case`` events.

Per specs/sync-ledger-replication.yaml SYNC-02-002 and ADR-0022.
"""

from __future__ import annotations

import logging

from py_trees.common import Status

from vultron.core.behaviors.sync.nodes._helpers import (
    _LedgerEffectNode,
    _extract_id_from_field,
)
from vultron.core.models.note import VultronNote
from vultron.core.models._helpers import _as_id

logger = logging.getLogger(__name__)


class ApplyNoteFromLedgerNode(_LedgerEffectNode):
    """Apply an ``add_note_to_case`` ledger entry to the local case replica.

    When a non-CaseActor participant receives ``Announce(CaseLedgerEntry)``
    and the entry's ``event_type`` is ``add_note_to_case``, this node
    extracts the note ID from ``payload_snapshot["object"]`` and appends it
    to the local case replica's ``notes`` list (idempotent).

    This is the canonical mechanism by which non-CaseActor participants
    learn about note additions — they must NOT update ``notes`` directly from
    ``Add(Note, Case)`` messages; only the CaseActor does that (ADR-0022,
    SYNC-02-002).

    The note **object** is persisted alongside the reference, from the same
    ``payload_snapshot["object"]``.  Appending the id alone left the recipient
    holding a case that referenced a note it could not read — a bare-URI
    dangling reference of exactly the kind the Actor Knowledge Model exists to
    prevent.  A shared store hid this: the author's note row was visible to
    every actor, so nobody noticed the recipient never stored one
    (ADR-0073, CM-01-001).

    Lenient on missing data: if the case replica is absent, the note ID is
    not present in the snapshot, or the snapshot is malformed, the node
    returns SUCCESS to avoid blocking the ``Announce`` processing flow.  A note
    that cannot be reconstructed is logged and the reference still recorded —
    knowing *that* a note was attached is better than dropping the event.
    """

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        entry = self._get_entry()
        snapshot = entry.payload_snapshot

        note_data = snapshot.get("object")
        note_id = _extract_id_from_field(note_data)
        case_id = entry.case_id

        if not note_id or not case_id:
            self.logger.debug(
                "%s: payload_snapshot missing 'object' id or case_id"
                " — skipping note apply (non-fatal)",
                self.name,
            )
            return Status.SUCCESS

        case = self._resolve_case_replica(case_id)
        if case is None:
            return Status.SUCCESS  # Regime 2 (ADR-0087): partial replica, skip

        existing_ids = [_as_id(n) for n in case.notes]
        if note_id in existing_ids:
            self.logger.debug(
                "%s: note '%s' already in case '%s' — idempotent no-op",
                self.name,
                note_id,
                case_id,
            )
            return Status.SUCCESS

        self._materialise_note(note_data, note_id)

        case.notes.append(note_id)
        self.datalayer.save(case)
        self.logger.info(
            "%s: applied ledger note attachment '%s' to case '%s' (SYNC-02-002)",
            self.name,
            note_id,
            case_id,
        )
        return Status.SUCCESS

    def _materialise_note(self, note_data: object, note_id: str) -> None:
        """Persist the note itself, so the reference about to be added resolves.

        Mirrors ``ApplyParticipantStatusFromLedgerNode``: the canonical entry
        carries the object inline, so the recipient can reconstruct it rather
        than having to fetch it from the author — which the Actor Knowledge Model
        forbids anyway.
        """
        assert self.datalayer is not None

        if self.datalayer.read(note_id) is not None:
            return

        if not isinstance(note_data, dict):
            self.logger.warning(
                "%s: payload_snapshot 'object' for note '%s' is not a dict, so"
                " the note cannot be reconstructed; recording the reference"
                " only, which leaves it unresolvable locally",
                self.name,
                note_id,
            )
            return

        try:
            note = VultronNote.model_validate(note_data)
        except Exception as exc:
            self.logger.warning(
                "%s: failed to reconstruct note '%s' from payload_snapshot:"
                " %s — recording the reference only",
                self.name,
                note_id,
                exc,
            )
            return

        self.datalayer.create(note)
        self.logger.debug(
            "%s: stored note '%s' from the canonical entry", self.name, note_id
        )
