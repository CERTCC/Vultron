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

"""EmbargoTeardownAuthorizationGate threat-termination BT node for add_case_status_tree.

Provides :class:`ThreatTerminationBranchNode` which fires embargo teardown
when a CaseStatus signals a threat (CS.P, CS.X, or CS.A set): an active
embargo is terminated, and while EM is ``PROPOSED`` every open proposal is
abandoned instead (EMB-16-001, #4145).  A replica that receives a P/X/A
status the CASE_MANAGER declared leaves the teardown to the manager's
committed entry and asks nothing (RSH-03-004, #4149).

Per RSH-03-001 to RSH-03-004, ADR-0046.
"""

import logging
from typing import cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.embargo.trigger_tree import (
    reject_proposed_embargo_bt,
    terminate_embargo_bt,
)
from vultron.core.behaviors.helpers import (
    DataLayerConditionWithPorts,
    resolve_case_replica,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.protocols import PersistableModel
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.states.cs import CS_pxa

logger = logging.getLogger(__name__)


def read_pxa_state(case_status: object) -> object | None:
    """Return the raw PXA state carried by *case_status*, or None.

    Reads ``case_status.pxa.state`` when the object has a ``pxa``
    attribute (a ``None`` ``pxa`` yields None), else ``pxa_state``.
    """
    if case_status is None:
        return None
    if hasattr(case_status, "pxa"):
        pxa = getattr(case_status, "pxa", None)
        return None if pxa is None else pxa.state
    return getattr(case_status, "pxa_state", None)


def resolve_pxa_threat_state(case_status: object) -> CS_pxa | None:
    """Return the PXA state if a threat is present; return None otherwise.

    A threat is any ``CS_pxa`` state other than ``pxa`` (all-lowercase —
    no P, X, or A set).  Accepts the resolved ``case_status`` object
    (not the outer ``status_obj`` wrapper).

    Returns ``None`` when:
    - ``case_status`` is None
    - ``case_status`` has no PXA attribute
    - The resolved state is ``CS_pxa.pxa``
    """
    pxa_state = read_pxa_state(case_status)
    if pxa_state is None:
        return None
    if pxa_state == CS_pxa.pxa:
        return None
    return cast(CS_pxa, pxa_state)


def pxa_embargo_teardown_bt(
    *, case_id: str, result_out: dict[str, object]
) -> py_trees.behaviour.Behaviour:
    """The embargo teardown a P/X/A signal calls for, by EM state.

    A ``Selector`` that terminates an active embargo (ACTIVE/REVISE,
    EMB-07-001/002) and otherwise abandons every open proposal (PROPOSED,
    EMB-16-001).  Each subtree checks its own EM precondition first, so at
    most one of them writes, and only as the CASE_MANAGER (EP-09-008).
    """
    return py_trees.composites.Selector(
        name="TeardownSelector",
        memory=False,
        children=[
            terminate_embargo_bt(case_id=case_id, result_out=result_out),
            reject_proposed_embargo_bt(case_id=case_id, result_out=result_out),
        ],
    )


class _ThreatTerminationSkipConditionNode(DataLayerConditionWithPorts):
    """Inner guard for :class:`ThreatTerminationBranchNode`.

    Returns SUCCESS (skip teardown) when:
    - The resolved CaseStatus has no pxa state, OR
    - The pxa state is ``pxa`` (all-lowercase — no P, X, or A set), OR
    - DataLayer or case_id is unavailable, OR
    - The case has neither an active embargo nor an open proposal (nothing
      to terminate or abandon).

    Returns FAILURE (proceed to teardown) when the pxa state indicates at
    least one of P=True, X=True, or A=True AND an active embargo or an open
    proposal exists (EMB-16-001).

    Per RSH-03-001 to RSH-03-003.
    """

    def __init__(
        self,
        status_obj: PersistableModel | None,
        case_id: str | None,
        name: str | None = None,
        use_datalayer_fallback: bool = False,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.status_obj = status_obj
        self.case_id = case_id
        self.use_datalayer_fallback = use_datalayer_fallback

    def _case_status_from_datalayer(self) -> object:
        """Read case.current_status from the DataLayer; returns None on any miss."""
        if self.datalayer is None or not self.case_id:
            return None
        # Lenient best-effort read (ADR-0087): a post-mutation state fallback;
        # an unresolvable case simply yields no status (None), which the caller
        # treats as "no threat info" (conformance allowlist).
        case_obj = self.datalayer.read_case(self.case_id)
        if case_obj is None:
            return None
        try:
            return case_obj.current_status
        except (ValueError, IndexError):
            return None

    def _threat_present(self) -> bool:
        """Return True if pxa state has at least one of P, X, or A set."""
        case_status: object = getattr(self.status_obj, "case_status", None)
        if case_status is None:
            case_status = self.status_obj

        # When status_obj carries no PXA info AND the caller has explicitly
        # opted in to the DataLayer fallback (set only by callers that know
        # EmitCaseStatusUpdateNode has already written the post-mutation
        # state), read case.current_status from the DataLayer.
        if self.use_datalayer_fallback and (
            case_status is None
            or (
                not hasattr(case_status, "pxa")
                and not hasattr(case_status, "pxa_state")
            )
        ):
            case_status = self._case_status_from_datalayer()

        return resolve_pxa_threat_state(case_status) is not None

    def update(self) -> Status:
        if not self._threat_present():
            return Status.SUCCESS

        if self.datalayer is None or not self.case_id:
            return Status.SUCCESS

        # Lenient guard (ADR-0087): returns FAILURE only to *signal* that an
        # active embargo must be terminated, or the open proposals abandoned,
        # on threat; every other path is SUCCESS ("nothing to tear down"). An
        # unresolvable case holds neither, so SUCCESS is correct (allowlist).
        case = self.datalayer.read_case(self.case_id)
        if case is None:
            return Status.SUCCESS

        if (
            _as_id(case.active_embargo) is None
            and not case.proposed_embargo_ids
        ):
            return Status.SUCCESS

        return Status.FAILURE


class _DeclaredByCaseManagerNode(DataLayerConditionWithPorts):
    """Skip guard: the status came from the CASE_MANAGER (RSH-03-004, #4149).

    The CASE_MANAGER tears the embargo down on its own P/X/A detection and
    commits the teardown, and its status declaration can reach a replica
    before those entries do.  Asking the manager then to do what it has
    already done only earns a refusal, so a replica that is not the sender
    waits for the committed entry (EP-09-007).

    This is not an authorization gate (RSH-03-002): it decides nothing about
    whether the teardown is allowed, only who carries it out.

    Returns SUCCESS (skip) when the sender holds ``CVDRole.CASE_MANAGER`` on
    the case and the executing actor is someone else; FAILURE (proceed)
    otherwise, including when the sender or the case is unknown.
    """

    def __init__(
        self,
        sender_actor_id: str | None,
        case_id: str | None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.sender_actor_id = sender_actor_id
        self.case_id = case_id

    def update(self) -> Status:
        sender = self.sender_actor_id
        if not sender or sender == self.actor_id:
            return Status.FAILURE
        # Regime 2 (ADR-0087): a case this replica does not hold is not a
        # status the manager declared, so the teardown branch decides.
        case = resolve_case_replica(self, self.case_id)
        if case is None or self.datalayer is None:
            return Status.FAILURE
        if resolve_case_manager_id(case, self.datalayer) != sender:
            return Status.FAILURE
        self.feedback_message = (
            f"P/X/A status on case '{self.case_id}' was declared by the"
            f" CASE_MANAGER '{sender}': its committed entry carries the"
            " teardown, so nothing is asked (RSH-03-004)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class ThreatTerminationBranchNode(py_trees.composites.Selector):
    """EmbargoTeardownAuthorizationGate: Trigger embargo teardown when CaseStatus signals a threat.

    Fires when the CaseStatus has at least one of P=True, X=True, or A=True
    (any ``CS_pxa`` state other than ``pxa``) AND the case has an active
    embargo or an open proposal.

    Does NOT gate on sender role (RSH-03-002) — authorization was
    already verified at StatusAdoptionGate before this node is reached.
    With ``sender_actor_id`` given, a status the CASE_MANAGER declared skips
    the teardown on every other actor (RSH-03-004): the manager has already
    torn down, and its committed entry carries the change.

    Delegates to :func:`pxa_embargo_teardown_bt`: ``terminate_embargo_bt``
    for an active embargo (BT-19-002), ``reject_proposed_embargo_bt`` while
    EM is ``PROPOSED`` (EMB-16-001).  Skips silently (returns SUCCESS) when
    teardown conditions are not met.

    Implemented as a ``py_trees.composites.Selector`` (memory=False):

    - Child 1 ``_ThreatTerminationSkipConditionNode``: SUCCESS → skip.
    - Child 2 ``_DeclaredByCaseManagerNode``: SUCCESS → skip.
    - Child 3 ``TeardownSelector``: SUCCESS on teardown; FAILURE on routing
      prerequisites absent or dispatch failure (BT-14-001).

    Per RSH-03-001 to RSH-03-003, ADR-0046.
    """

    def __init__(
        self,
        status_obj: PersistableModel | None,
        case_id: str | None,
        name: str | None = None,
        use_datalayer_fallback: bool = False,
        sender_actor_id: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__, memory=False)
        result_out: dict[str, object] = {}
        terminate_subtree = (
            pxa_embargo_teardown_bt(case_id=case_id, result_out=result_out)
            if case_id is not None
            else py_trees.behaviours.Success(name="TerminateEmbargoSkipped")
        )
        self.add_children(
            [
                _ThreatTerminationSkipConditionNode(
                    status_obj=status_obj,
                    case_id=case_id,
                    name="SkipCondition",
                    use_datalayer_fallback=use_datalayer_fallback,
                ),
                _DeclaredByCaseManagerNode(
                    sender_actor_id=sender_actor_id,
                    case_id=case_id,
                    name="DeclaredByCaseManager",
                ),
                terminate_subtree,
            ]
        )


__all__ = [
    "_DeclaredByCaseManagerNode",
    "pxa_embargo_teardown_bt",
    "resolve_pxa_threat_state",
    "_ThreatTerminationSkipConditionNode",
    "ThreatTerminationBranchNode",
]
