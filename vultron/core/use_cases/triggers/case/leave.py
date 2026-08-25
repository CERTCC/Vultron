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

"""Trigger use case for Leave(VulnerabilityCase).

Emits ``Leave(VulnerabilityCase)`` to the Case Actor inbox.  The Case Actor
commits a ``close_case`` :class:`~vultron.core.models.case_ledger_entry
.VultronCaseLedgerEntry` and broadcasts it; each replica then advances the
departing actor's RM state to ``RM.CLOSED`` via
:class:`~vultron.core.behaviors.sync.nodes.close_case_effect.ApplyCloseCaseFromLedgerNode`
(ADR-0050, CM-23-002/CM-23-003).

Per specs/case-management.yaml DEMOMA-07-001, CM-23-002, CM-23-003.
"""

import logging
from typing import cast

import py_trees.behaviour

from vultron.core.behaviors.sender.send_tree import sender_side_bt
from vultron.core.use_cases.triggers._base import SvcBTTriggerBase
from vultron.core.use_cases.triggers._helpers import (
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import LeaveCaseTriggerRequest

logger = logging.getLogger(__name__)


class SvcLeaveCaseUseCase(SvcBTTriggerBase):
    """Send Leave(VulnerabilityCase) to the Case Actor (ADR-0050, CM-23-002/003).

    Routes ``Leave(VulnerabilityCase)`` to the Case Actor inbox so the Case
    Actor can commit a ``close_case`` ledger entry and broadcast it.  The
    receiver-side role semantics (owner closes all, non-owner departs only)
    are applied in :func:`~vultron.core.behaviors.case.receive_close_case_tree
    .create_close_case_received_tree` on the Case Actor, and fanned out to all
    replicas via :class:`~vultron.core.behaviors.sync.nodes.effects
    .ApplyCloseCaseFromLedgerNode`.

    The sender does NOT update their own RM state here — RM.CLOSED is applied
    on every replica when each replica receives the ``close_case`` ledger entry
    via ``Announce(CaseLedgerEntry)`` (ADR-0050).
    """

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
            self._captured["activity"] = activity_dict
            return [activity_id]

        return sender_side_bt(
            case_id=self._case_id,
            activity_builder=_build_activities,
        )

    def _handle_result(self) -> None:
        logger.info(
            "Actor '%s' sent Leave(VulnerabilityCase) for case '%s'"
            " (ADR-0050, DEMOMA-07-001)",
            self._actor_id,
            self._case_id,
        )
