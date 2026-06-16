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

"""Embargo accept trigger use case."""

import logging

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.trigger_tree import (
    accept_embargo_trigger_bt,
)
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.services.embargo_lifecycle import EmbargoLifecycleResult
from vultron.core.use_cases.triggers._helpers import (
    _is_case_owner,
    _resolve_embargo_id_from_proposal,
    _resolve_embargo_proposal,
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptEmbargoTriggerRequest,
)
from vultron.errors import VultronValidationError

logger = logging.getLogger(__name__)


class SvcAcceptEmbargoUseCase:
    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AcceptEmbargoTriggerRequest,
        trigger_activity: TriggerActivityPort | None = None,
    ) -> None:
        self._dl = dl
        self._request: AcceptEmbargoTriggerRequest = request
        self._trigger_activity = trigger_activity

    def execute(self) -> dict:
        request = self._request
        dl = self._dl

        actor = resolve_actor(request.actor_id, dl)
        actor_id = actor.id_
        case = resolve_case(request.case_id, dl)
        proposal = _resolve_embargo_proposal(case, request.proposal_id, dl)
        embargo_id = _resolve_embargo_id_from_proposal(proposal)

        embargo = dl.read(embargo_id)
        if embargo is None:
            raise VultronValidationError(
                f"Could not resolve EmbargoEvent '{embargo_id}'."
            )

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcAcceptEmbargoUseCase requires a TriggerActivityPort"
            )

        factory = self._trigger_activity
        captured: dict = {}
        result_out: dict[str, object] = {}

        def _build_activities(case_manager_id: str) -> list[str]:
            accept_id, accept_dict = factory.accept_embargo(
                proposal_id=proposal.id_,
                case_id=case.id_,
                actor=actor_id,
                to=[case_manager_id],
            )
            captured["activity"] = accept_dict
            return [accept_id]

        bridge = BTBridge(datalayer=dl, trigger_activity=factory)
        tree = accept_embargo_trigger_bt(
            case_id=case.id_,
            embargo_id=embargo_id,
            result_out=result_out,
            activity_builder=_build_activities,
        )
        result = bridge.execute_with_setup(tree, actor_id=actor_id)
        if result.status != Status.SUCCESS:
            error = result_out.get("error")
            if isinstance(error, Exception):
                raise error
            raise VultronValidationError(
                f"AcceptEmbargo failed: {BTBridge.get_failure_reason(tree)}"
            )
        lifecycle_result = result_out.get("lifecycle_result")
        if not isinstance(lifecycle_result, EmbargoLifecycleResult):
            raise RuntimeError(
                "AcceptEmbargo did not capture lifecycle result in BT output"
            )

        if (
            _is_case_owner(case, actor_id)
            and lifecycle_result.em_after != lifecycle_result.em_before
        ):
            logger.info(
                "Actor '%s' accepted embargo proposal '%s'; activated embargo"
                " '%s' on case '%s' (EM %s → %s)",
                actor_id,
                proposal.id_,
                embargo_id,
                case.id_,
                lifecycle_result.em_before,
                lifecycle_result.em_after,
            )
        else:
            logger.info(
                "Actor '%s' accepted embargo proposal '%s'; recorded"
                " participant consent for embargo '%s' on case '%s'"
                " (EM unchanged at %s)",
                actor_id,
                proposal.id_,
                embargo_id,
                case.id_,
                lifecycle_result.em_after,
            )

        return {"activity": captured.get("activity")}


SvcEvaluateEmbargoUseCase = SvcAcceptEmbargoUseCase
