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

"""Trigger-side behavior tree for create-case workflow."""

from collections.abc import Callable
from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction, UpdateActorOutbox
from vultron.core.models.case import VultronCase


class _CreateCaseRecordNode(DataLayerAction):
    """Create and persist VulnerabilityCase; publish case_id to blackboard."""

    def __init__(
        self,
        case_name: str,
        case_content: str,
        report_id: str | None,
        result_out: dict[str, Any],
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_name = case_name
        self._case_content = case_content
        self._report_id = report_id
        self._result_out = result_out

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.WRITE
        )

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        case = VultronCase(
            name=self._case_name,
            content=self._case_content,
            attributed_to=self.actor_id,
        )
        if self._report_id is not None:
            case.vulnerability_reports.append(self._report_id)
        self.datalayer.create(case)
        self.blackboard.case_id = case.id_
        self._result_out["case_id"] = case.id_
        return Status.SUCCESS


class _BuildCreateCaseActivityNode(DataLayerAction):
    """Create Create(Case) activity and publish activity_id to blackboard."""

    def __init__(
        self,
        activity_builder: Callable[[str], tuple[str, dict[str, Any]]],
        result_out: dict[str, Any],
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._activity_builder = activity_builder
        self._result_out = result_out

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="activity_id", access=py_trees.common.Access.WRITE
        )

    def update(self) -> Status:
        try:
            case_id = self.blackboard.get("case_id")
        except KeyError:
            self.feedback_message = "case_id not found in blackboard"
            return Status.FAILURE
        if not isinstance(case_id, str):
            self.feedback_message = "case_id must be a string"
            return Status.FAILURE

        try:
            activity_id, activity_dict = self._activity_builder(case_id)
        except Exception as exc:
            self.feedback_message = (
                f"CreateCase activity construction failed: {exc}"
            )
            self.logger.error(self.feedback_message)
            return Status.FAILURE

        self.blackboard.activity_id = activity_id
        self._result_out["activity"] = activity_dict
        return Status.SUCCESS


def create_case_trigger_bt(
    *,
    case_name: str,
    case_content: str,
    report_id: str | None,
    result_out: dict[str, Any],
    activity_builder: Callable[[str], tuple[str, dict[str, Any]]],
) -> py_trees.behaviour.Behaviour:
    """Return trigger-side BT for case creation + outbound Create activity."""
    return py_trees.composites.Sequence(
        name="CreateCaseTriggerBT",
        memory=False,
        children=[
            _CreateCaseRecordNode(
                case_name=case_name,
                case_content=case_content,
                report_id=report_id,
                result_out=result_out,
            ),
            _BuildCreateCaseActivityNode(
                activity_builder=activity_builder,
                result_out=result_out,
            ),
            UpdateActorOutbox(),
        ],
    )
