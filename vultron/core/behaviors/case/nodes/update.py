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

"""Nodes that announce a CASE_MANAGER's case update to the participants."""

from __future__ import annotations

from py_trees.common import Status

from vultron.core.behaviors.case.update_support import (
    broadcast_case_update,
    find_excluded_actor_ids,
)
from vultron.core.behaviors.emit_capable import EmitCapable
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.errors import VultronError


class CaptureCaseUpdateBroadcastExclusionsNode(DataLayerConditionWithPorts):
    """Resolve embargo-based broadcast exclusions for the case update."""

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "excluded_actor_ids": PortInformation(data_type=object, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"excluded_actor_ids": "/excluded_actor_ids"}

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1: case must exist (ADR-0087)

        self._set_output(
            "excluded_actor_ids", find_excluded_actor_ids(case, self.datalayer)
        )
        return Status.SUCCESS


class BroadcastCaseUpdateNode(DataLayerActionWithPorts, EmitCapable):
    """Broadcast the updated case to eligible participants (CM-06-001).

    MUST be wrapped in a ``CheckIsCaseManagerNode`` gate: only the case's
    ``CASE_MANAGER`` may announce canonical case state, and this node authors
    the ``Announce`` as the executing actor. ``create_engage_case_tree``
    places it in the factory's CASE_MANAGER-gated ``manager_effects``.
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "excluded_actor_ids": PortInformation(data_type=object, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"excluded_actor_ids": "/excluded_actor_ids"}

    def initialise(self) -> None:
        super().initialise()
        self.excluded_actor_ids: set = self.get_input("excluded_actor_ids")

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1: case must exist (ADR-0087)
        if (f := self._require_factory()) is not None:
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return f
        assert self.trigger_activity_factory is not None

        try:
            broadcast_case_update(
                self.datalayer,
                self.case_id,
                case,
                self.actor_id,
                self.trigger_activity_factory,
                excluded_actor_ids=self.excluded_actor_ids,
            )
        except VultronError as exc:
            # The adapter refuses to build an Announce it cannot complete —
            # e.g. a report the case names that this store does not hold
            # (CBT-01-007).  That is a reported outcome of this node, not a
            # fault in the service (BT-HELPER-01).
            self.feedback_message = (
                f"{self.name}: could not broadcast case '{self.case_id}':"
                f" {exc}"
            )
            self.logger.warning("%s", self.feedback_message)
            return Status.FAILURE
        return Status.SUCCESS
