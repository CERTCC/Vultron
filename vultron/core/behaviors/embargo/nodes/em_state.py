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

"""EM state and embargo-id read nodes, and the EM-state guards, for the lifecycle.

``ReadEmStateNode`` reads the current EM state into result_out so
downstream nodes and service callers have it without a separate DB read.
``read_case_em_state`` runs it from inside another node's ``update()`` and
raises when the state cannot be read.  EM state writes are owned by
``EmbargoLifecycle`` (EMB-18-001).
"""

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.core.models._helpers import _as_id
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.states.em import EM, is_em_embargo_active, is_em_exited
from vultron.errors import (
    BtNodePreconditionError,
    VultronError,
    VultronInvalidStateTransitionError,
    VultronValidationError,
)


class ReadEmStateNode(DataLayerConditionWithPorts):
    """Read a case's EM state, derived from its embargo register, into result_out.

    EM is :attr:`VulnerabilityCase.em_state`, read from the register
    (ADR-0122), never a status field a node could read stale.

    On success the EM enum value is stored in ``result_out["em_before"]``
    for the node's caller to report.

    Returns SUCCESS when the case is found and a valid EM state is available.
    Returns FAILURE when:
    - the DataLayer is unavailable,
    - the case cannot be found.

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
            em_state = case.em_state
        except (ValueError, KeyError, AttributeError, VultronError):
            err = VultronValidationError(
                f"Case '{self._case_id}' has no derivable EM state."
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


def read_case_em_state(
    datalayer: CasePersistence,
    case_id: str,
    result_out: dict[str, object] | None = None,
) -> EM:
    """Return the EM state of *case_id*, read through ``ReadEmStateNode``.

    The in-node EM read (``notes/embargo-lifecycle.md`` § "Guidance for
    Agents", item 6): a node that needs the current EM state inside its own
    ``update()`` calls this instead of reading ``case.em_state``
    inline.  When *result_out* is given, the read writes ``em_before`` (or
    ``error``) into it, as ``ReadEmStateNode`` does, so a node that exposes
    that dict to its caller keeps doing so.

    Raises:
        BtNodePreconditionError: when the case is not in *datalayer* or its
            EM state cannot be read; the message is the read's own
            ``feedback_message``.  A node that returns FAILURE catches it in
            ``update()``; a refusal arm in a Selector lets it propagate
            (``notes/bt-pitfalls.md`` § "A Refusal Arm in a Selector Fails
            Toward 'Admit'").
    """
    out: dict[str, object] = {} if result_out is None else result_out
    read_node = ReadEmStateNode(case_id=case_id, result_out=out)
    read_node.datalayer = datalayer
    # The status, not ``em_before``, decides: a caller-supplied dict may
    # still hold the state an earlier tick read.
    if read_node.update() != Status.SUCCESS:
        raise BtNodePreconditionError(read_node.feedback_message)
    em_state = out["em_before"]
    assert isinstance(em_state, EM)
    return em_state


class ValidateEmbargoRevisionStateNode(DataLayerActionWithPorts):
    """Guard that the case EM state permits a revision proposal.

    Returns SUCCESS when EM state is ACTIVE or REVISE.  Returns FAILURE
    (with error in ``result_out``) for any other state — revision proposals
    require an active embargo; use propose-embargo for initial proposals.

    Uses ``ReadEmStateNode`` to read the EM state (AC-1 of issue #1474) rather
    than reading ``case.em_state`` inline.
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

        # AC-1: read em_state via ReadEmStateNode, not inline.
        try:
            em_state = read_case_em_state(
                self.datalayer, self._case_id, self._result_out
            )
        except BtNodePreconditionError as exc:
            self.feedback_message = str(exc)
            return Status.FAILURE

        if not is_em_embargo_active(em_state):
            bad_state = VultronInvalidStateTransitionError(
                f"Cannot propose embargo revision: case '{self._case_id}'"
                f" EM state '{em_state}' does not allow a revision proposal."
                f" Use propose-embargo for initial proposals."
            )
            self._result_out["error"] = bad_state
            self.feedback_message = str(bad_state)
            return Status.FAILURE

        return Status.SUCCESS


class ValidateEmbargoProposalStateNode(DataLayerActionWithPorts):
    """Guard that the case EM state admits an embargo proposal.

    A read-only precondition for the propose trigger, ahead of the role arms:
    ``EXITED`` admits no proposal, because once an embargo register entry is
    ``TERMINATED`` the register accepts no further change (EP-09-001,
    ADR-0122).  A participant that is not the CASE_MANAGER writes no EM
    state and so runs no ``STRICT`` check (EP-09-008); without this guard its
    proposal would be queued, refused by the CASE_MANAGER's admission guard
    without a ``Reject``, and leave a pending assertion behind.  Returns
    FAILURE with the error in ``result_out``, as
    :class:`ValidateEmbargoRevisionStateNode` does.
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

        try:
            em_state = read_case_em_state(
                self.datalayer, self._case_id, self._result_out
            )
        except BtNodePreconditionError as exc:
            self.feedback_message = str(exc)
            return Status.FAILURE

        if is_em_exited(em_state):
            bad_state = VultronInvalidStateTransitionError(
                f"Cannot propose embargo: case '{self._case_id}' EM state"
                f" '{em_state}' admits no embargo proposal (EP-09-001)."
            )
            self._result_out["error"] = bad_state
            self.feedback_message = str(bad_state)
            return Status.FAILURE

        return Status.SUCCESS


class ReadEmbargoIdNode(DataLayerActionWithPorts):
    """Read the active embargo ID from the case and write it to the blackboard.

    Returns FAILURE when the case is not found, has no active embargo, or
    the DataLayer is unavailable.  Returns SUCCESS and writes ``embargo_id``
    to the blackboard on success.
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "embargo_id": PortInformation(data_type=str, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"embargo_id": "/embargo_id"}

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        embargo_id = _as_id(case.active_embargo)
        if embargo_id is None:
            self.feedback_message = (
                f"No active embargo on case '{self._case_id}'"
            )
            return Status.FAILURE

        self._set_output("embargo_id", embargo_id)
        return Status.SUCCESS
