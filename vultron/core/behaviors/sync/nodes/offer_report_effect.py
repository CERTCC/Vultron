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

"""Ledger effect node for add_report_to_case entries.

Provides :class:`ApplyOfferReportFromLedgerNode`, which creates a
``VultronOfferRecord`` when an invited actor processes the canonical
``add_report_to_case`` ledger entry backfilled from the case owner.

Per ADR-0035 DL-06-002, SYNC-02-002, ISSUE-2134.
"""

from __future__ import annotations

from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.behaviors.sync.nodes.effects import _extract_id_from_field


class ApplyOfferReportFromLedgerNode(DataLayerAction):
    """Apply an ``add_report_to_case`` ledger entry to the local DataLayer.

    When an invited actor receives ``Announce(CaseLedgerEntry)`` for the
    canonical ``add_report_to_case`` entry, this node creates a
    :class:`~vultron.core.models.offer_record.VultronOfferRecord` keyed by
    ``VultronOfferRecord.build_id(offer_id)`` so that ``SvcValidateReportUseCase``
    can proceed without spoofing.

    The record is derived from the ledger entry's ``payload_snapshot``:

    - ``payload_snapshot["offerId"]`` → ``offer_id``
    - ``payload_snapshot["object"]["id"]`` → ``report_id``
    - ``payload_snapshot["offerActorId"]`` (or ``"actor"``) → ``offer_actor_id``

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

        # Only handle add_report_to_case entries.
        if entry.event_type != "add_report_to_case":
            return Status.SUCCESS

        snapshot = (
            entry.payload_snapshot
            if isinstance(entry.payload_snapshot, dict)
            else {}
        )
        offer_id = snapshot.get("offerId")
        if not offer_id:
            self.logger.debug(
                "%s: add_report_to_case entry has no offerId — skipping (non-fatal)",
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

        # offerActorId is the original Offer sender; "actor" is the CaseActor.
        offer_actor_id = _extract_id_from_field(
            snapshot.get("offerActorId") or snapshot.get("actor")
        )
        object_data = snapshot.get("object")
        report_id = (
            _extract_id_from_field(object_data)
            if isinstance(object_data, (str, dict))
            else None
        )

        self._maybe_restore_report(object_data, report_id)

        offer_to = snapshot.get("to", [])
        if isinstance(offer_to, str):
            offer_to = [offer_to]

        if not offer_actor_id or not report_id:
            self.logger.debug(
                "%s: payload_snapshot missing offer actor or object.id"
                " — skipping offer-record creation (non-fatal)",
                self.name,
            )
            return Status.SUCCESS

        return self._save_offer_record(
            offer_id, offer_record_id, report_id, offer_actor_id, offer_to
        )

    def _maybe_restore_report(
        self, object_data: Any, report_id: str | None
    ) -> None:
        # The add_report_to_case snapshot embeds the full report inline
        # (build_add_report_to_case_snapshot -> obj_to_inline_dict).  An invited
        # replica never received the VulnerabilityReport object directly, so
        # reconstruct and store it from the snapshot here — otherwise
        # _reconstitute_offer (and SvcValidateReportUseCase) 404 on the report
        # lookup even though the offer record exists (#2180, ADR-0035 DL-06-002).
        assert self.datalayer is not None
        if not (
            isinstance(object_data, dict)
            and report_id
            and self.datalayer.read(report_id) is None
        ):
            return
        from vultron.core.models.report import VulnerabilityReport

        try:
            self.datalayer.save(
                VulnerabilityReport.model_validate(object_data)
            )
            self.logger.info(
                "%s: stored VulnerabilityReport '%s' from ledger snapshot"
                " for invited replica (#2180)",
                self.name,
                report_id,
            )
        except Exception as exc:
            self.logger.warning(
                "%s: could not reconstruct VulnerabilityReport from"
                " add_report_to_case snapshot: %s",
                self.name,
                exc,
            )

    def _save_offer_record(
        self,
        offer_id: str,
        offer_record_id: str,
        report_id: str,
        offer_actor_id: str,
        offer_to: list,
    ) -> Status:
        assert self.datalayer is not None
        from vultron.core.models.offer_record import VultronOfferRecord

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
