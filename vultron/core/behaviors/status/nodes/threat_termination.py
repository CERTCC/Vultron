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
when a CaseStatus signals a threat (CS.P, CS.X, or CS.A set).

Per RSH-03-001 to RSH-03-003, ADR-0046.
"""

import logging

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.embargo.trigger_tree import terminate_embargo_bt
from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.protocols import PersistableModel
from vultron.core.models._helpers import _as_id

logger = logging.getLogger(__name__)


class _ThreatTerminationSkipConditionNode(DataLayerConditionWithPorts):
    """Inner guard for :class:`ThreatTerminationBranchNode`.

    Returns SUCCESS (skip teardown) when:
    - The resolved CaseStatus has no pxa state, OR
    - The pxa state is ``pxa`` (all-lowercase — no P, X, or A set), OR
    - DataLayer or case_id is unavailable, OR
    - The case has no active embargo (nothing to terminate).

    Returns FAILURE (proceed to teardown) when the pxa state indicates at
    least one of P=True, X=True, or A=True AND an active embargo exists.

    Per RSH-03-001 to RSH-03-003.
    """

    def __init__(
        self,
        status_obj: PersistableModel | None,
        case_id: str | None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.status_obj = status_obj
        self.case_id = case_id

    def _threat_present(self) -> bool:
        """Return True if pxa state has at least one of P, X, or A set."""
        from vultron.core.states.cs import CS_pxa

        case_status: object = getattr(self.status_obj, "case_status", None)
        if case_status is None:
            case_status = self.status_obj
        if case_status is None:
            return False
        if hasattr(case_status, "pxa"):
            pxa_state = getattr(case_status, "pxa").state
        elif hasattr(case_status, "pxa_state"):
            pxa_state = getattr(case_status, "pxa_state")
        else:
            return False
        if pxa_state is None:
            return False
        try:
            return bool(pxa_state != CS_pxa.pxa)
        except Exception:
            return False

    def update(self) -> Status:
        if not self._threat_present():
            return Status.SUCCESS

        if self.datalayer is None or not self.case_id:
            return Status.SUCCESS

        case = self.datalayer.read(self.case_id)
        if not isinstance(case, VulnerabilityCase):
            return Status.SUCCESS

        if _as_id(case.active_embargo) is None:
            return Status.SUCCESS

        return Status.FAILURE


class ThreatTerminationBranchNode(py_trees.composites.Selector):
    """EmbargoTeardownAuthorizationGate: Trigger embargo teardown when CaseStatus signals a threat.

    Fires when the CaseStatus has at least one of P=True, X=True, or A=True
    (any ``CS_pxa`` state other than ``pxa``) AND the case has an active
    embargo.

    Does NOT gate on sender role (RSH-03-002) — authorization was
    already verified at StatusAdoptionGate.  The self-addressed ``Add(CaseStatus)``
    arrives with the CaseActor as sender, not the original peer.

    Delegates to ``terminate_embargo_bt`` (BT-19-002).  Skips silently
    (returns SUCCESS) when teardown conditions are not met.

    Implemented as a ``py_trees.composites.Selector`` (memory=False):

    - Child 1 ``_ThreatTerminationSkipConditionNode``: SUCCESS → skip.
    - Child 2 ``TerminateEmbargoBT``: SUCCESS on teardown; FAILURE on routing
      prerequisites absent or dispatch failure (BT-14-001).

    Per RSH-03-001 to RSH-03-003, ADR-0046.
    """

    def __init__(
        self,
        status_obj: PersistableModel | None,
        case_id: str | None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__, memory=False)
        result_out: dict[str, object] = {}
        terminate_subtree = (
            terminate_embargo_bt(
                case_id=case_id,
                result_out=result_out,
            )
            if case_id is not None
            else py_trees.behaviours.Success(name="TerminateEmbargoSkipped")
        )
        self.add_children(
            [
                _ThreatTerminationSkipConditionNode(
                    status_obj=status_obj,
                    case_id=case_id,
                    name="SkipCondition",
                ),
                terminate_subtree,
            ]
        )


__all__ = [
    "_ThreatTerminationSkipConditionNode",
    "ThreatTerminationBranchNode",
]
