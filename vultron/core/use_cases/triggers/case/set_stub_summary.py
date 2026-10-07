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

"""Demo-only trigger: seed stub_summary on an actor's DataLayer case copy.

:class:`SvcSetStubSummaryUseCase` is the use case behind
``POST /actors/{actor_id}/demo/set-stub-summary``.

It seeds ``stub_summary`` on the requesting actor's local DataLayer copy of
the case so that a subsequent ``invite-actor-to-case`` trigger can build the
stub Invite (CM-17-010, MV-10-001, #4165).

No protocol activity is emitted.  The BT has a single leaf that reads the
case, applies the new value, and saves it back.
"""

import logging
from typing import Any, cast

import py_trees
import py_trees.behaviour
import py_trees.blackboard
import py_trees.common
from py_trees.common import Status

from vultron.core.models.use_case_result import StatusResult
from vultron.core.use_cases.triggers._base import SvcBTTriggerBase
from vultron.core.use_cases.triggers._helpers import (
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    SetStubSummaryTriggerRequest,
)

logger = logging.getLogger(__name__)


class _SetStubSummaryLeaf(py_trees.behaviour.Behaviour):
    """Single-node BT: read the case, set stub_summary, save it back.

    Accesses the DataLayer via the blackboard key ``datalayer`` that
    ``BTBridge.setup_tree`` populates before the tree ticks.
    """

    def __init__(self, case_id: str, stub_summary: str) -> None:
        super().__init__(name="SetStubSummaryLeaf")
        self._case_id = case_id
        self._stub_summary = stub_summary

    def setup(self, **kwargs: Any) -> None:
        """Attach a blackboard client and register the datalayer read key."""
        bb = self.attach_blackboard_client(name=self.name)
        bb.register_key(key="datalayer", access=py_trees.common.Access.READ)
        self._bb = bb

    def update(self) -> Status:
        """Read case, apply stub_summary, persist, return SUCCESS."""
        dl = self._bb.datalayer
        case = dl.read_case(self._case_id)
        if case is None:
            self.feedback_message = (
                f"SetStubSummaryLeaf: case '{self._case_id}' not found"
            )
            return Status.FAILURE
        updated = case.model_copy(update={"stub_summary": self._stub_summary})
        dl.save(updated)
        self.feedback_message = (
            f"SetStubSummaryLeaf: set stub_summary on case '{self._case_id}'"
        )
        return Status.SUCCESS


class SvcSetStubSummaryUseCase(SvcBTTriggerBase[StatusResult]):
    """Seed ``stub_summary`` on the actor's local case copy (demo scaffold).

    Sets ``VulnerabilityCase.stub_summary`` through a BT leaf so a subsequent
    ``invite-actor-to-case`` trigger can build the stub Invite
    (CM-17-010, MV-10-001, #4165).  No activity is emitted.
    """

    #: No outbound activity — this verb only mutates the local DataLayer.
    _requires_trigger_activity = False

    def _prepare(self) -> None:
        request = cast(SetStubSummaryTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id: str = actor.id_
        case = resolve_case(request.case_id, self._dl)
        self._case_id: str = case.id_
        self._stub_summary: str = request.stub_summary
        logger.debug(
            "Actor '%s': seeding stub_summary on case '%s'",
            self._actor_id,
            self._case_id,
        )

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return _SetStubSummaryLeaf(
            case_id=self._case_id,
            stub_summary=self._stub_summary,
        )

    def _handle_result(self) -> None:
        logger.info(
            "Actor '%s': stub_summary set on case '%s' (CM-17-010, #4165)",
            self._actor_id,
            self._case_id,
        )

    def _build_result(self) -> StatusResult:
        return StatusResult(activity_id=None, status_id=None)
