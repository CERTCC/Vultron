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

"""Trigger use case for the ``leave-case`` verb: send Leave(VulnerabilityCase).

Any participant calls it to close its part in a case (TRIG-13-001, ADR-0145).
It runs the leaving actor's ``PreCloseAction`` call-out first (TRIG-13-002),
refuses a Case Owner whose replica records an embargo in force before that
(TRIG-13-003), and then emits ``Leave(VulnerabilityCase)`` to the Case Actor
inbox.  The Case Actor
commits a ``close_case`` :class:`~vultron.core.models.case_ledger_entry
.CaseLedgerEntry` recording the Leave, then one
``add_participant_status_to_participant`` entry per RM transition it writes
for the departing actor, and broadcasts each.  Every replica advances the
departing actor to ``RM.CLOSED`` only by applying those status entries
(ADR-0050, CM-23-001, CM-23-002/CM-23-003).

Per specs/case-management.yaml CM-23-002, CM-23-003 and
specs/triggerable-behaviors.yaml TRIG-13-001 through TRIG-13-003.
"""

import json
import logging
from typing import TYPE_CHECKING, cast

import py_trees.behaviour

from vultron.core.behaviors.call_out.bundles.close_report import (
    CLOSE_REPORT_DETERMINISTIC,
    CloseReportCallOutBundle,
)
from vultron.core.behaviors.case.leave_case_trigger_tree import (
    create_leave_case_trigger_tree,
)
from vultron.core.use_cases.triggers._base import SvcActivityTriggerBase
from vultron.core.use_cases.triggers._helpers import (
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import LeaveCaseTriggerRequest

if TYPE_CHECKING:
    from vultron.core.ports.case_outbox import CaseOutboxPersistence
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

logger = logging.getLogger(__name__)


class SvcLeaveCaseUseCase(SvcActivityTriggerBase):
    """Send Leave(VulnerabilityCase) to the Case Actor (ADR-0050, CM-23-002/003).

    Routes ``Leave(VulnerabilityCase)`` to the Case Actor inbox so the Case
    Actor can commit a ``close_case`` ledger entry and broadcast it.  The
    receiver-side role semantics (owner closes all, non-owner departs only)
    are applied in :func:`~vultron.core.behaviors.case.receive_close_case_tree
    .create_close_case_received_tree` on the Case Actor, which records each RM
    step as its own ledger entry and fans it out to every replica still
    receiving case content, the departing actor's own included (CM-23-004).

    The sender does NOT update their own RM state here — its replica, like
    every other, applies the status entries the Case Actor commits, received
    via ``Announce(CaseLedgerEntry)`` (ADR-0050, CM-23-004).

    Before the Leave is built, the tree refuses the Case Owner while its
    replica records an embargo in force (``VultronInvalidStateTransitionError``,
    HTTP 409, TRIG-13-003) and then runs the ``PreCloseAction`` backend from
    *call_out*; a failing backend fails the trigger with nothing queued
    (TRIG-13-002).
    """

    def __init__(
        self,
        dl: "CaseOutboxPersistence",
        request: object,
        trigger_activity: "TriggerActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
        sync_port: "SyncActivityPort | None" = None,
        call_out: CloseReportCallOutBundle = CLOSE_REPORT_DETERMINISTIC,
    ) -> None:
        super().__init__(
            dl=dl,
            request=request,
            trigger_activity=trigger_activity,
            wire_render_port=wire_render_port,
            sync_port=sync_port,
        )
        self._close_call_out = call_out

    def _prepare(self) -> None:
        request = cast(LeaveCaseTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_
        self._case_id = resolve_case(request.case_id, self._dl).id_

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        def _build_activities(case_manager_id: str) -> list[str]:
            activity_id, activity_dict = self._factory.close_case(
                case_id=self._case_id,
                actor=self._actor_id,
                to=[case_manager_id],
            )
            self._captured["activity"] = json.loads(activity_dict)
            return [activity_id]

        return create_leave_case_trigger_tree(
            actor_id=self._actor_id,
            case_id=self._case_id,
            activity_builder=_build_activities,
            result_out=self._result_out,
            call_out=self._close_call_out,
        )

    def _handle_result(self) -> None:
        logger.info(
            "Actor '%s' sent Leave(VulnerabilityCase) for case '%s'"
            " (ADR-0050, TRIG-13-001)",
            self._actor_id,
            self._case_id,
        )
