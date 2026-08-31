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

"""Ledger effect node for ``accept_invite_actor_to_case`` events.

Per specs/sync-ledger-replication.yaml SYNC-02-002, ADR-0022,
and specs/multi-actor-demo.yaml DEMOMA-07-003.
"""

from __future__ import annotations

import logging

from py_trees.common import Status

from vultron.core.behaviors.sync.nodes._helpers import (
    _LedgerEffectNode,
    _extract_id_from_field,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.enums.roles import validate_roles

logger = logging.getLogger(__name__)


class ApplyInviteAcceptFromLedgerNode(_LedgerEffectNode):
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

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        entry = self._get_entry()
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

        obj_snapshot = snapshot.get("object")
        raw_roles = (
            obj_snapshot.get("roles")
            if isinstance(obj_snapshot, dict)
            else None
        )
        try:
            case_roles = validate_roles(raw_roles) if raw_roles else []
        except (TypeError, ValueError, KeyError):
            case_roles = []

        participant = CaseParticipant(
            id_=f"{case_id}/participants/{invitee_id.rstrip('/').rsplit('/', 1)[-1]}",
            attributed_to=invitee_id,
            context=case_id,
            case_roles=case_roles,
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
