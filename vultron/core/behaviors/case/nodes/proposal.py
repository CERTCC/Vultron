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

"""
CaseProposal action nodes for the slimmed vendor receive-report tree.

Provides :class:`ProposeReportCaseToActorNode`, the ADR-0041 variant of the
proposal send that operates directly from a ``report_id`` without requiring a
``VulnerabilityCase`` to already exist in the DataLayer.

The pre-ADR-0041 node (:class:`~vultron.core.behaviors.case.nodes.actor.ProposeCaseToActorNode`)
reads ``case_id`` and ``case_actor_id`` from the blackboard (written by
``CreateCaseActorNode``).  This module's node derives ``case_actor_id``
deterministically from ``ActorConfig.case_actor_service_url`` and
``_derive_case_slug(report_id)`` instead.
"""

from typing import cast

from py_trees.common import Status

from vultron.config import get_config
from vultron.core.behaviors.case.nodes.case_setup import _derive_case_slug
from vultron.core.behaviors.helpers import (
    DataLayerAction,
    DataLayerActionWithPorts,
)
from vultron.core.models.pending_create_case_activity import (
    PendingCreateCaseActivity,
)
from vultron.core.ports.case_persistence import CaseOutboxPersistence


class ProposeReportCaseToActorNode(DataLayerActionWithPorts):
    """Send ``Create(as_CaseProposal)`` from ``report_id`` without a prior case.

    Used by the slimmed vendor ``receive_report_case_tree`` (ADR-0041).  Unlike
    :class:`~vultron.core.behaviors.case.nodes.actor.ProposeCaseToActorNode`,
    this node does not require a ``VulnerabilityCase`` to exist — it uses
    ``report_id`` directly and derives ``case_actor_id`` from
    ``ActorConfig.case_actor_service_url`` + a deterministic slug from
    ``report_id``.

    Returns ``FAILURE`` when:

    - DataLayer, ``actor_id``, or ``trigger_activity_factory`` is unavailable.
    - ``case_actor_service_url`` is not configured.
    - ``trigger_activity_factory.create_case_proposal()`` raises an exception.

    Per specs/case-proposal.yaml CP-04-001, CP-04-002 and ADR-0041.
    """

    def __init__(self, report_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id

    def _derive_case_actor_id(self) -> str | None:
        cfg = get_config().actor
        if cfg.case_actor_service_url is None:
            self.feedback_message = (
                f"{self.name}: case_actor_service_url is not configured"
                " (set VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL)"
            )
            self.logger.error(self.feedback_message)
            return None
        base_url = str(cfg.case_actor_service_url).rstrip("/")
        slug = _derive_case_slug(self.report_id)
        return f"{base_url}/actors/case-actor-{slug}"

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        if (f := self._require_factory()) is not None:
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return f

        case_actor_id = self._derive_case_actor_id()
        if case_actor_id is None:
            return Status.FAILURE

        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        try:
            activity_id, _ = (
                self.trigger_activity_factory.create_case_proposal(
                    actor=self.actor_id,
                    report_id=self.report_id,
                    case_actor_id=case_actor_id,
                )
            )
            cast(CaseOutboxPersistence, self.datalayer).outbox_append(
                activity_id
            )
        except Exception as exc:
            self.feedback_message = f"create_case_proposal failed: {exc}"
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        self.logger.info(
            "%s: queued Create(as_CaseProposal) '%s' to outbox"
            " for case-actor '%s' (report '%s')",
            self.name,
            activity_id,
            case_actor_id,
            self.report_id,
        )
        return Status.SUCCESS


class RequeuePendingCreateCaseActivityNode(DataLayerAction):
    """Re-queue a persisted ``Create(VulnerabilityCase)`` obligation.

    Crash recovery: when the process died between persisting a
    ``PendingCreateCaseActivity`` marker and delivering the activity, the
    obligation survives in storage and must be re-queued on the next startup.

    This is protocol-significant behaviour — it causes an outbound delivery —
    so it lives in a BT node rather than in the adapter that schedules the scan
    (BT-15-001).  It previously ran directly in
    ``vultron/adapters/driving/fastapi/pending_retry.py``, bypassing the BT
    audit trail.

    No ``CASE_MANAGER`` gate: recovery makes no new authorship claim.  The
    activity was authored when the marker was written, and this node only
    re-queues it in the store it already belongs to.

    Idempotent (AC-4): ``outbox_append`` does not enforce uniqueness, so an
    activity already present is left alone rather than queued twice — which
    would cause double delivery.  Returns SUCCESS when the activity is in the
    outbox, whether this node put it there or found it.
    """

    def __init__(
        self,
        marker: PendingCreateCaseActivity,
        activity_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.marker = marker
        self.activity_id = activity_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        outbox = cast(CaseOutboxPersistence, self.datalayer)
        try:
            already_queued = self.activity_id in outbox.outbox_list()
        except Exception as exc:  # noqa: BLE001 - recovery must not crash boot
            self.feedback_message = f"could not read outbox: {exc}"
            self.logger.error(
                "%s: could not read outbox for actor '%s': %s",
                self.name,
                self.marker.case_actor_id,
                exc,
            )
            return Status.FAILURE

        if not already_queued:
            try:
                outbox.outbox_append(self.activity_id)
            except Exception as exc:  # noqa: BLE001
                self.feedback_message = f"could not enqueue: {exc}"
                self.logger.error(
                    "%s: could not enqueue Create(VulnerabilityCase) '%s'"
                    " for actor '%s': %s",
                    self.name,
                    self.activity_id,
                    self.marker.case_actor_id,
                    exc,
                )
                return Status.FAILURE
        else:
            self.logger.debug(
                "%s: Create(VulnerabilityCase) '%s' already queued for actor"
                " '%s'; not duplicating.",
                self.name,
                self.activity_id,
                self.marker.case_actor_id,
            )

        # Marker cleanup is best-effort: the obligation is discharged once the
        # activity is queued.  A surviving marker is re-scanned next startup and
        # skipped by the idempotency check above, so failure here is a warning.
        if not self.datalayer.delete(
            "PendingCreateCaseActivity", self.marker.id_
        ):
            self.logger.warning(
                "%s: marker '%s' could not be deleted after successful"
                " re-queue for actor '%s'. The next startup scan will find the"
                " activity already in the outbox and skip it.",
                self.name,
                self.marker.id_,
                self.marker.case_actor_id,
            )

        self.logger.info(
            "Actor '%s' re-queued Create(VulnerabilityCase) '%s' from marker"
            " '%s' (crash recovery)",
            self.marker.case_actor_id,
            self.activity_id,
            self.marker.id_,
        )
        return Status.SUCCESS
