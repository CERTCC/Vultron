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
from vultron.core.models.case import VulnerabilityCase
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

    Lenient on missing data: if the case replica is absent, the note ID is
    not present in the snapshot, or the snapshot is malformed, the node
    returns SUCCESS to avoid blocking the ``Announce`` processing flow.
    """

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        entry = self._get_entry()
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
