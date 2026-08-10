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

"""Ledger effect node for Offer(VulnerabilityReport) entries.

Provides :class:`ApplyOfferReportFromLedgerNode`, which creates a
``VultronOfferRecord`` when an invited actor processes the canonical
``submit_report`` ledger entry backfilled from the case owner.

Per ADR-0035 DL-06-002, SYNC-02-002, ISSUE-2134.
"""

from __future__ import annotations

from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.behaviors.sync.nodes.effects import _extract_id_from_field


class ApplyOfferReportFromLedgerNode(DataLayerAction):
    """Apply a ``submit_report`` ledger entry to the local DataLayer.

    When an invited actor receives ``Announce(CaseLedgerEntry)`` for the
    canonical ``Offer(VulnerabilityReport)`` entry (``event_type="submit_report"``),
    this node creates a :class:`~vultron.core.models.offer_record.VultronOfferRecord`
    keyed by ``VultronOfferRecord.build_id(offer_id)`` so that
    ``SvcValidateReportUseCase`` can proceed without spoofing.

    The record is derived entirely from the ledger entry's ``payload_snapshot``:

    - ``log_object_id`` → ``offer_id``
    - ``payload_snapshot["object"]["id"]`` → ``report_id``
    - ``payload_snapshot["actor"]`` → ``offer_actor_id``
    - ``payload_snapshot["to"]`` → ``offer_to``

    Idempotent: if the record already exists the node returns SUCCESS without
    overwriting.  Lenient on missing data — if the snapshot is incomplete the
    node returns SUCCESS to avoid blocking the ``Announce`` processing flow.

    Per ADR-0035 DL-06-002: domain facts from a received protocol message MUST
    be recorded as core state at extraction time.  SYNC-02-002, ISSUE-2134.
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
        from vultron.core.models.offer_record import VultronOfferRecord

        entry = _require_log_entry(self.blackboard.activity, self.name)

        # Only handle submit_report entries.
        if entry.event_type != "submit_report":
            return Status.SUCCESS

        offer_id = entry.log_object_id
        if not offer_id:
            self.logger.debug(
                "%s: ledger entry has no log_object_id — skipping (non-fatal)",
                self.name,
            )
            return Status.SUCCESS

        offer_record_id = VultronOfferRecord.build_id(offer_id)
        if self.datalayer.read(offer_record_id) is not None:
            self.logger.debug(
                "%s: VultronOfferRecord '%s' already present — idempotent no-op",
                self.name,
                offer_record_id,
            )
            return Status.SUCCESS

        snapshot = entry.payload_snapshot
        offer_actor_id = _extract_id_from_field(snapshot.get("actor"))
        object_data = snapshot.get("object")
        report_id = (
            _extract_id_from_field(object_data)
            if isinstance(object_data, (str, dict))
            else None
        )
        offer_to = snapshot.get("to", [])
        if isinstance(offer_to, str):
            offer_to = [offer_to]

        if not offer_actor_id or not report_id:
            self.logger.debug(
                "%s: payload_snapshot missing 'actor' or 'object.id'"
                " — skipping offer-record creation (non-fatal)",
                self.name,
            )
            return Status.SUCCESS

        try:
            record = VultronOfferRecord(
                offer_id=offer_id,
                report_id=report_id,
                offer_actor_id=offer_actor_id,
                offer_to=list(offer_to) if offer_to else [],
            )
            self.datalayer.save(record)
        except Exception as exc:
            self.logger.warning(
                "%s: failed to create VultronOfferRecord for offer '%s': %s",
                self.name,
                offer_id,
                exc,
            )
            return Status.SUCCESS

        self.logger.info(
            "%s: created VultronOfferRecord '%s' for offer '%s'"
            " (ADR-0035 DL-06-002, ISSUE-2134)",
            self.name,
            offer_record_id,
            offer_id,
        )
        return Status.SUCCESS
