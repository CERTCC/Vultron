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

"""Embargo termination trigger use case."""

import logging
from typing import cast

import py_trees.behaviour

from vultron.core.behaviors.embargo.trigger_tree import (
    terminate_embargo_trigger_bt,
)
from vultron.core.use_cases.triggers._base import SvcEmbargoTriggerBase
from vultron.core.use_cases.triggers._helpers import (
    _coerce_embargo_event,
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    TerminateEmbargoTriggerRequest,
)
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronValidationError,
)

logger = logging.getLogger(__name__)


class SvcTerminateEmbargoUseCase(SvcEmbargoTriggerBase):
    def _prepare(self) -> None:
        request = cast(TerminateEmbargoTriggerRequest, self._request)
        dl = self._dl

        actor = resolve_actor(request.actor_id, dl)
        self._actor_id = actor.id_
        self._case = resolve_case(request.case_id, dl)

        if self._case.active_embargo is None:
            logger.warning(
                "Invalid EM state transition: actor '%s' cannot TERMINATE:"
                " case '%s' has no active embargo.",
                self._actor_id,
                self._case.id_,
            )
            raise VultronInvalidStateTransitionError(
                f"Case '{self._case.id_}' has no active embargo to terminate."
            )

        embargo_id = (
            self._case.active_embargo
            if isinstance(self._case.active_embargo, str)
            else getattr(self._case.active_embargo, "id_", None)
        )
        if embargo_id is None:
            raise VultronValidationError(
                f"Active embargo on case '{self._case.id_}' is missing an ID."
            )

        _coerce_embargo_event(dl.read(embargo_id), embargo_id)
        self._embargo_id = embargo_id

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        def _build_activities(case_manager_id: str) -> list[str]:
            announce_id, announce_dict = self._factory.terminate_embargo(
                embargo_id=self._embargo_id,
                case_id=self._case.id_,
                actor=self._actor_id,
                to=[case_manager_id],
            )
            self._captured["activity"] = announce_dict
            return [announce_id]

        return terminate_embargo_trigger_bt(
            case_id=self._case.id_,
            result_out=self._result_out,
            activity_builder=_build_activities,
        )

    def _log_lifecycle_result(self) -> None:
        lr = self._lifecycle_result
        logger.info(
            "Actor '%s' terminated embargo '%s' on case '%s' (EM %s → %s)",
            self._actor_id,
            self._embargo_id,
            self._case.id_,
            lr.em_before,
            lr.em_after,
        )
