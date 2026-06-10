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

"""Trigger-side behavior tree for add-object-to-case workflows."""

from collections.abc import Callable
from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction, UpdateActorOutbox


class _BuildAddObjectActivityNode(DataLayerAction):
    """Create Add(object,target=case) activity and publish activity_id."""

    def __init__(
        self,
        activity_builder: Callable[[], tuple[str, dict[str, Any]]],
        result_out: dict[str, Any],
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._activity_builder = activity_builder
        self._result_out = result_out

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity_id", access=py_trees.common.Access.WRITE
        )

    def update(self) -> Status:
        try:
            activity_id, activity_dict = self._activity_builder()
        except Exception as exc:
            self.feedback_message = (
                f"AddObject activity construction failed: {exc}"
            )
            self.logger.error(self.feedback_message)
            return Status.FAILURE

        self.blackboard.activity_id = activity_id
        self._result_out["activity"] = activity_dict
        return Status.SUCCESS


def add_object_trigger_bt(
    *,
    result_out: dict[str, Any],
    activity_builder: Callable[[], tuple[str, dict[str, Any]]],
) -> py_trees.behaviour.Behaviour:
    """Return trigger-side BT for Add(object,target=case) + outbox queueing."""
    return py_trees.composites.Sequence(
        name="AddObjectTriggerBT",
        memory=False,
        children=[
            _BuildAddObjectActivityNode(
                activity_builder=activity_builder,
                result_out=result_out,
            ),
            UpdateActorOutbox(),
        ],
    )
