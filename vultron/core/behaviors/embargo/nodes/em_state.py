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

"""EM state read BT node for the embargo lifecycle.

``ReadEmStateNode`` reads the current EM state into result_out so
downstream nodes and service callers have it without a separate DB read.
EM state writes are owned by ``EmbargoLifecycle`` (EMB-18-001).
"""

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.errors import VultronValidationError


class ReadEmStateNode(DataLayerConditionWithPorts):
    """Read the current EM state from a case and write it to result_out.

    Replaces the inline ``em_before = EM(case.current_status.em_state)`` reads
    that previously appeared in every ``EmbargoLifecycle`` service method.

    On success the EM enum value is stored in ``result_out["em_before"]``
    so downstream service calls can receive it as a parameter rather than
    re-reading the DataLayer.

    Returns SUCCESS when the case is found and a valid EM state is available.
    Returns FAILURE when:
    - the DataLayer is unavailable,
    - the case cannot be found, or
    - the EM state field cannot be coerced to a valid ``EM`` enum value.

    Blackboard contract:
    - Reads: ``datalayer`` (set by BTBridge)
    - Writes: nothing (side-effects flow through ``result_out``)
    """

    def __init__(
        self,
        case_id: str,
        result_out: dict[str, object],
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._result_out = result_out

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case, failure = self._require_case(self._case_id)
        if failure is not None:
            # Regime 1 (ADR-0087): canonical FAILURE + message/log via the
            # helper; preserve this node's result_out error side-channel.
            self._result_out["error"] = VultronValidationError(
                self.feedback_message
            )
            return failure

        try:
            em_state = case.current_status.em.state
        except (ValueError, KeyError, AttributeError):
            err = VultronValidationError(
                f"Case '{self._case_id}' has no materialized CaseStatus"
                f" or an invalid em_state value."
            )
            self._result_out["error"] = err
            self.feedback_message = str(err)
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        self._result_out["em_before"] = em_state
        self.feedback_message = (
            f"Case '{self._case_id}' em_state={em_state.value}"
        )
        self.logger.debug("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS
