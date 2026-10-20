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

"""Whole accept or reject for a received CaseStatus (RSH-09-005, ADR-0107).

A received ``Add(CaseStatus, VulnerabilityCase)`` is accepted as sent or
refused whole, like a participant status (RSH-09-001): the EM it carries must
be the EM the case derives from its embargo register, and its P/X/A must
confirm or advance the case's.  :class:`CheckCaseStatusAcceptableNode` is the
read-only precondition guard that decides it before ``GuardedCommit``
(CLP-10-006).

:class:`_CsStatusGuardBase` is the shared base of the CaseStatus precondition
guards, here and in :mod:`.cs_invariant_guards`.
"""

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.protocols import PersistableModel
from vultron.core.states.cs import CS_pxa, is_pxa_assertion_acceptable
from vultron.core.states.em import EM, is_em_assertion_acceptable


class _CsStatusGuardBase(DataLayerConditionWithPorts):
    """Shared init and _resolve_asserted for CS status guard nodes.

    Subclasses accept ``(case_id, status_id, status_obj_fallback, name)`` and
    can resolve the asserted :class:`~vultron.core.models.case_status.CaseStatus`
    from the DataLayer, falling back to ``status_obj_fallback`` when not found.
    Private; not part of the public API.
    """

    def __init__(
        self,
        case_id: str | None,
        status_id: str,
        status_obj_fallback: PersistableModel | None = None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.status_id = status_id
        self.status_obj_fallback = status_obj_fallback

    def _resolve_asserted(self) -> CaseStatus | None:
        assert self.datalayer is not None
        obj = self.datalayer.read(self.status_id)
        if isinstance(obj, CaseStatus):
            return obj
        obj = self.status_obj_fallback
        return obj if isinstance(obj, CaseStatus) else None


def case_status_refusals(
    case_em: EM, current_pxa: CS_pxa | None, asserted: CaseStatus
) -> list[str]:
    """Return every reason to refuse *asserted*, or ``[]`` to accept it.

    EM is derived from the case's embargo register, which only embargo
    messages change (ADR-0122), so a status may carry the case's EM but never
    move it; this holds for the case's first status too.  P/X/A must be the
    case's or a monotone forward move from it; multi-step advances are legal
    on the received path (CSB-16-002 applies only to local writes).  A case
    holding no status yet (*current_pxa* ``None``) has no P/X/A to regress
    from.  Every failing rule is reported (EH-07-001).
    """
    reasons: list[str] = []
    if not is_em_assertion_acceptable(case_em, asserted.em.state):
        reasons.append(
            f"em: {asserted.em.state.name} differs from the case's"
            f" {case_em.name}, which only the embargo register moves"
        )
    if current_pxa is not None and not is_pxa_assertion_acceptable(
        current_pxa, asserted.pxa.state
    ):
        reasons.append(
            f"pxa: {current_pxa.name} → {asserted.pxa.state.name} is not a"
            " forward move"
        )
    return reasons


class CheckCaseStatusAcceptableNode(_CsStatusGuardBase):
    """Accept or refuse a received CaseStatus as a whole (RSH-09-005).

    Read-only precondition guard (CLP-10-006).

    Returns:
        SUCCESS when the tree has no case and when every rule accepts the
        status.  A case holding no status yet has no P/X/A to judge against,
        but its first status must still carry the register-derived EM.

        FAILURE when the case is not in the DataLayer or the asserted status
        cannot be resolved — the tree must not commit a ledger entry for
        either (CLP-10-009) — and when any rule refuses the status, with
        ``feedback_message`` naming every reason.
    """

    def update(self) -> Status:
        if not self.case_id:
            return Status.SUCCESS
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        asserted = self._resolve_asserted()
        if asserted is None:
            self.feedback_message = (
                f"CaseStatus '{self.status_id}' cannot be resolved"
            )
            self.logger.warning(
                "%s: %s (not in DataLayer, no fallback); aborting before"
                " GuardedCommit (CLP-10-009)",
                self.name,
                self.feedback_message,
            )
            return Status.FAILURE

        try:
            current_pxa: CS_pxa | None = case.current_status.pxa.state
        except ValueError:
            current_pxa = None  # first CaseStatus ever: no P/X/A baseline

        reasons = case_status_refusals(case.em_state, current_pxa, asserted)
        if not reasons:
            return Status.SUCCESS

        self.feedback_message = (
            f"CaseStatus '{self.status_id}' refused for case"
            f" '{self.case_id}': " + "; ".join(reasons)
        )
        self.logger.warning(
            "%s: %s (RSH-09-005)", self.name, self.feedback_message
        )
        return Status.FAILURE
