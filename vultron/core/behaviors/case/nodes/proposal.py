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
CaseProposal action nodes for the slimmed receive-report tree.

Provides :class:`ProposeReportCaseToActorNode`, the ADR-0041 variant of the
proposal send that operates directly from a ``report_id`` without requiring a
``VulnerabilityCase`` to already exist in the DataLayer.

The pre-ADR-0041 node (``ProposeCaseToActorNode``, now deleted — issue #4353)
read ``case_id`` and ``case_actor_id`` from the blackboard (written by
``CreateCaseActorNode``).  This module's node reads the CaseActor's identity from
:func:`~vultron.core.behaviors.case.case_actor_identity.case_actor_identity`
instead — the container's identity, not a per-case one derived from the report
(#1872).
"""

from py_trees.common import Status

from vultron.config import get_config
from vultron.core.behaviors.case.case_actor_identity import (
    case_actor_identity,
)
from vultron.core.behaviors.case.offer_provenance import find_offer_for_report
from vultron.core.behaviors.helpers import _EmitSingleActivityBase


class ProposeReportCaseToActorNode(_EmitSingleActivityBase):
    """Send ``Create(as_CaseProposal)`` from ``report_id`` without a prior case.

    Used by the slimmed ``receive_report_case_tree`` (ADR-0041).  Unlike
    the deleted ``ProposeCaseToActorNode`` (issue #4353),
    this node does not require a ``VulnerabilityCase`` to exist — it uses
    ``report_id`` directly and addresses the container's CaseActor identity,
    ``{ActorConfig.case_actor_service_url}/actors/case-actor`` (CP-04-003,
    CP-04-005).

    Returns ``FAILURE`` when:

    - DataLayer, ``actor_id``, or ``trigger_activity_factory`` is unavailable.
    - ``case_actor_service_url`` is not configured.
    - ``trigger_activity_factory.create_case_proposal()`` raises an exception.

    The proposal states this actor's ``default_case_roles`` (CFG-07-002), which
    the CASE_MANAGER seats it with alongside ``CASE_OWNER`` (CP-01-011,
    CP-01-013, CP-09-007, ADR-0133).

    Per specs/case-proposal.yaml CP-04-001, CP-04-002 and ADR-0041.
    """

    def __init__(self, report_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id

    def _derive_case_actor_id(self) -> str | None:
        """Return the CaseActor to address, or ``None`` when unconfigured.

        The identity is the container's — ``.../actors/case-actor`` — and carries
        no case. It used to be ``.../actors/case-actor-{slug}``, derived here from
        ``report_id``, which made it a phantom: this node computed it and no
        container hosted it, so delivery 404'd permanently and the round-trip
        never began (#1872). Which case a message concerns travels in
        ``activity.context``, so the slug carried nothing the payload lacked.
        """
        identity = case_actor_identity()
        if identity is None:
            self.feedback_message = (
                f"{self.name}: case_actor_service_url is not configured"
                " (set VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL)"
            )
            self.logger.error("%s", self.feedback_message)
        return identity

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
        assert self.datalayer is not None
        # CP-01-007: this store has the OfferRecord because this actor received
        # the Offer; the CaseActor's own store never will, so the provenance has
        # to be read here and carried on the proposal (#2548).
        offer_id, offer_actor_id = find_offer_for_report(
            self.datalayer, self.report_id
        )
        try:
            activity_id, _ = (
                self.trigger_activity_factory.create_case_proposal(
                    actor=self.actor_id,
                    report_id=self.report_id,
                    case_actor_id=case_actor_id,
                    offer_id=offer_id,
                    offer_actor_id=offer_actor_id,
                    # CP-01-013, ADR-0133: this actor's own roles, which the
                    # CASE_MANAGER cannot read from its own configuration.
                    proposer_case_roles=get_config().actor.default_case_roles,
                )
            )
            # Route through the shared emit seam (OX-14-001, ASK-04-008).
            self._emit_through_seam(activity_id, "")
        except Exception as exc:  # noqa: BLE001  # ruff-baseline #3768
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
