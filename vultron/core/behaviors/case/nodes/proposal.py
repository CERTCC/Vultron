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
from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.ports.case_persistence import CaseOutboxPersistence


class ProposeReportCaseToActorNode(DataLayerAction):
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
        except Exception as exc:
            self.feedback_message = f"create_case_proposal failed: {exc}"
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
            self.actor_id, activity_id
        )
        self.logger.info(
            "%s: queued Create(as_CaseProposal) '%s' to outbox"
            " for case-actor '%s' (report '%s')",
            self.name,
            activity_id,
            case_actor_id,
            self.report_id,
        )
        return Status.SUCCESS
