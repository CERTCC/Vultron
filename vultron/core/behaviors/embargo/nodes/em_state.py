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

"""EM state read/write BT nodes for the embargo lifecycle.

These nodes extract the em_state guard reads and mutations that previously
lived in ``vultron/core/services/embargo_lifecycle.py``, moving them into
the BT layer as named ``DataLayerCondition`` / ``DataLayerAction`` nodes.

AC-1 of issue #1474: the service layer no longer directly inspects or
mutates ``case.current_status.em_state`` — that responsibility belongs here.
AC-2: nodes follow the ``DataLayerCondition`` / ``DataLayerAction`` base class
pattern from ``vultron/core/behaviors/helpers.py``.
AC-3: ``WriteEmStateNode`` is idempotent — when the current state already
equals the target it returns SUCCESS without calling ``datalayer.save``.
Callers that require an active embargo (e.g. terminate / accept) must place
a ``HasActiveEmbargoNode`` guard earlier in the BT sequence to enforce the
``EmbargoedCase`` precondition before reaching this node.
"""

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerAction,
    DataLayerCondition,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.states.em import EM
from vultron.errors import VultronValidationError


class ReadEmStateNode(DataLayerCondition):
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

        case = self.datalayer.read(self._case_id)
        if not isinstance(case, VulnerabilityCase):
            err = VultronValidationError(
                f"Case '{self._case_id}' not found or invalid."
            )
            self._result_out["error"] = err
            self.feedback_message = str(err)
            return Status.FAILURE

        try:
            em_state = EM(case.current_status.em_state)
        except (ValueError, KeyError):
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


class WriteEmStateNode(DataLayerAction):
    """Write a computed EM state back to the case and persist it.

    Replaces the inline ``case.current_status.em_state = em_after`` mutations
    that previously appeared in every ``EmbargoLifecycle`` service method.

    Reads the target EM value from ``result_out["em_after"]`` (written by the
    preceding service-call node) and applies it to the case only when the
    value differs from the current state (idempotent).

    Returns SUCCESS when:
    - the case is persisted with the new EM state, or
    - the current state already equals the target (idempotent no-op).

    Returns FAILURE when:
    - the DataLayer is unavailable,
    - the case cannot be found, or
    - ``result_out["em_after"]`` is absent or not a valid ``EM`` enum value.

    AC-3: where the operation semantics require an active embargo (e.g.
    ``TerminateEmbargoLifecycleNode``), the caller should wrap the BT
    sequence with a prior ``HasActiveEmbargoNode`` guard that enforces the
    ``EmbargoedCase`` precondition before this node is reached.

    Blackboard contract:
    - Reads: ``datalayer`` (set by BTBridge)
    - Writes: nothing (DataLayer mutation is the side effect)
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

        em_after = self._result_out.get("em_after")
        if not isinstance(em_after, EM):
            self.feedback_message = (
                f"result_out['em_after'] missing or not an EM value"
                f" (got {em_after!r})"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        case = self.datalayer.read(self._case_id)
        if not isinstance(case, VulnerabilityCase):
            self.feedback_message = (
                f"Case '{self._case_id}' not found or invalid."
            )
            return Status.FAILURE

        current_em = case.current_status.em_state
        if current_em == em_after:
            self.feedback_message = (
                f"Case '{self._case_id}' em_state already"
                f" {em_after.value} — no-op"
            )
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

        case.current_status.em_state = em_after
        self.datalayer.save(case)
        self.feedback_message = (
            f"Case '{self._case_id}' em_state {current_em} → {em_after.value}"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS
