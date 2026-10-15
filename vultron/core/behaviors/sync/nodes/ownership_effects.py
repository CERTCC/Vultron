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

"""Ownership-transfer side-effect node for Announce(CaseLedgerEntry) processing.

Provides :class:`ApplyOwnershipTransferFromLedgerNode`, which copies the new
Case Owner onto the local ``VulnerabilityCase.attributed_to`` when a
participant receives the CASE_MANAGER's ``update_case_owner`` entry
(CM-21-002, CLP-07-013, SYNC-02-002).
"""

from __future__ import annotations

import logging

from py_trees.common import Status

from vultron.core.behaviors.sync.nodes._helpers import (
    _extract_id_from_field,
    _LedgerEffectNode,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.wire_keys import wire_key

logger = logging.getLogger(__name__)

#: How the carried case spells ``attributed_to`` (ARCH-25-002).
_ATTRIBUTED_TO = wire_key("attributed_to", VulnerabilityCase)


class ApplyOwnershipTransferFromLedgerNode(_LedgerEffectNode):
    """Apply an ``update_case_owner`` ledger entry to the local case replica.

    An ownership transfer is the ``Accept`` the CASE_MANAGER records as
    received, followed by one entry of its own per object the transfer
    changes (CLP-07-013, ADR-0124): each participant record whose
    ``CASE_OWNER`` role moved (``update_case_participant``), then the case,
    whose ``attributed_to`` names the new owner (``update_case_owner``).  This
    node applies the last: it copies ``attributed_to`` from the case the entry
    carries.  It reads no role, sender or offer and computes no owner, so a
    replica holds the owner the CASE_MANAGER recorded (CM-23-016).

    Only ``attributed_to`` is copied because it is the one case field the
    transfer changes: the rest of the carried case is what a replica at that
    ledger position already holds, each part from an entry of its own (the
    participant records from the ``update_case_participant`` entries before
    this one), as for ``case_fully_closed``.  Copying the whole carried case
    is the one-apply-function end state of ADR-0124 (#4532).

    Lenient on a replica that holds no copy of the case (Regime 2, ADR-0087),
    and an idempotent no-op when the case already names that owner.  FAILURE,
    so the entry is not persisted (SYNC-12-001), when the entry carries no
    case owner to copy.

    Per specs/case-management.yaml CM-21-002, CM-21-007, CM-23-016,
    specs/sync-ledger-replication.yaml SYNC-02-002.
    """

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        entry = self._get_entry()
        case_id = entry.case_id
        carried = entry.payload_snapshot.get("object")
        new_owner_id = (
            _extract_id_from_field(carried.get(_ATTRIBUTED_TO))
            if isinstance(carried, dict)
            else None
        )
        if not new_owner_id:
            self.feedback_message = (
                f"{self.name}: the entry carries no case owner to copy"
            )
            self.logger.warning("%s", self.feedback_message)
            return Status.FAILURE

        case = self._resolve_case_replica(case_id)
        if case is None:
            return Status.SUCCESS  # Regime 2 (ADR-0087): partial replica, skip

        if _as_id(case.attributed_to) == new_owner_id:
            self.logger.debug(
                "%s: case '%s' already attributed to '%s' — idempotent no-op",
                self.name,
                case_id,
                new_owner_id,
            )
            return Status.SUCCESS

        case.attributed_to = new_owner_id  # type: ignore[assignment]
        self.datalayer.save_many(
            [case]
        )  # CM-21-004, BTND-06-008: attributed_to must use save_many
        self.logger.info(
            "%s: copied the new owner of case '%s' from the ledger:"
            " attributed_to = '%s' (CM-21-002, CM-23-016, SYNC-02-002)",
            self.name,
            case_id,
            new_owner_id,
        )
        return Status.SUCCESS
