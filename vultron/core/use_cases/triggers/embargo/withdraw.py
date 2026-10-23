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

"""Withdraw-embargo trigger use case (EP-09-013).

A signatory leaves the embargo in force by sending ``Leave(EmbargoEvent)``
to the CASE_MANAGER (MSM-07-010, PCR-08).  Withdrawing is not answering: no
Invite is named or resolved, so a signatory made by seeding or by joining,
which holds no ``Invite(EmbargoEvent)``, can withdraw too.  The accept and
reject triggers never withdraw (EP-09-012).
"""

import json
import logging
from typing import ClassVar, cast

import py_trees.behaviour

from vultron.core.behaviors.embargo.trigger_tree import (
    withdraw_embargo_trigger_bt,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.use_cases.triggers._base import SvcEmbargoTriggerBase
from vultron.core.use_cases.triggers._helpers import (
    resolve_actor,
    resolve_case,
    resolve_embargo_to_withdraw,
)
from vultron.core.use_cases.triggers.requests import (
    WithdrawEmbargoTriggerRequest,
)

logger = logging.getLogger(__name__)


class SvcWithdrawEmbargoUseCase(SvcEmbargoTriggerBase):
    _assertion_semantic_type: ClassVar[str] = (
        MessageSemantics.WITHDRAW_FROM_EMBARGO_ON_CASE.value
    )

    def _prepare(self) -> None:
        request = cast(WithdrawEmbargoTriggerRequest, self._request)
        dl = self._dl

        actor = resolve_actor(request.actor_id, dl)
        self._actor_id = actor.id_
        self._case = resolve_case(request.case_id, dl)
        # The case's active embargo, never an Invite (EP-09-013); refused
        # with the reason when there is none, the actor's row for it is not
        # AGREED, or the actor is the case owner.
        self._embargo_id = resolve_embargo_to_withdraw(
            self._case, self._actor_id, dl
        )

    def _assertion_subject(self) -> str:
        return self._embargo_id

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        def _build_activity(to: list[str] | None) -> tuple[str, str]:
            leave_id, leave_blob = self._factory.withdraw_from_embargo(
                embargo_id=self._embargo_id,
                case_id=self._case.id_,
                actor=self._actor_id,
                to=to,
            )
            self._captured["activity"] = json.loads(leave_blob)
            return leave_id, leave_blob

        return withdraw_embargo_trigger_bt(
            case_id=self._case.id_,
            embargo_id=self._embargo_id,
            result_out=self._result_out,
            activity_builder=_build_activity,
        )

    def _log_lifecycle_result(self) -> None:
        lr = self._lifecycle_result
        logger.info(
            "Actor '%s' withdrew from embargo '%s' on case '%s'"
            " (%d consent row change(s); EM unchanged at %s)",
            self._actor_id,
            self._embargo_id,
            self._case.id_,
            len(lr.participant_changes),
            lr.em_after,
        )
