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

"""Read-only precondition guards of the embargo proposal relay (EP-09-001).

Split out of ``relay.py`` for the BTND-07-004 line limit, along the seam the
received tree already has: these run as ``precondition_guards``, ahead of the
guarded commit, and write nothing; ``relay.py`` holds the recipient
collection and the relay emit, and re-exports these names.
"""

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)
from vultron.core.behaviors.embargo.nodes.em_state import read_case_em_state
from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.behaviors.idempotency import SilentIdempotencyGuardMixin
from vultron.core.states.em import is_em_exited
from vultron.errors import BtNodePreconditionError


class EmbargoProposalNotYetRecordedNode(
    SilentIdempotencyGuardMixin, DataLayerConditionWithPorts
):
    """Idempotency guard: this exact Invite has not been applied here before.

    The latch is ``case.pending_embargo_proposal_index[embargo_id] ==
    invite_id``, which the handler writes only after the whole tree succeeded
    (ID-04-005).  A re-delivered proposal — an outbox retry, a replayed
    inbox — would otherwise re-run the counter-proposal branch and relay a
    second round of Invites.  A precondition guard, so the duplicate commits
    no ledger entry (CLP-13-001); the handler reads its FAILURE as SKIPPED
    (HP-01-003).  A case this store does not hold cannot have recorded
    anything, so that is SUCCESS, not a refusal.
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        invite_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._embargo_id = embargo_id
        self._invite_id = invite_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case = self._resolve_case_replica(self._case_id)
        if case is None:
            return Status.SUCCESS
        recorded = case.pending_embargo_proposal_index.get(self._embargo_id)
        if recorded == self._invite_id:
            self.feedback_message = (
                f"Invite '{self._invite_id}' for embargo '{self._embargo_id}'"
                f" was already applied on case '{self._case_id}'"
            )
            return self._idempotent_failure(
                self.logger,
                "%s: %s — skipping (CLP-13-001)",
                self.name,
                self.feedback_message,
            )
        return Status.SUCCESS


class EmStateAdmitsProposalNode(DataLayerConditionWithPorts):
    """Guard: the case's EM state accepts a PROPOSE trigger.

    A read-only precondition guard (CLP-10-009) for the CASE_MANAGER's
    adjudication of a received proposal: ``NONE``, ``PROPOSED``, ``ACTIVE``
    and ``REVISE`` admit one (EP-09-001), ``EXITED`` does not — the EM
    machine never returns from ``EXITED``.  Placed ahead of the guarded
    commit so a refused proposal leaves no canonical entry behind.  Reads the
    state through :class:`ReadEmStateNode` (AC-1, #1474).
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        try:
            em_before = read_case_em_state(self.datalayer, self._case_id)
        except BtNodePreconditionError as exc:
            self.feedback_message = str(exc)
            return Status.FAILURE

        if is_em_exited(em_before):
            # The register accepts no change once its embargo has ended
            # (ADR-0122).
            self.feedback_message = (
                f"Case '{self._case_id}' is at EM {em_before.name}, which"
                " admits no embargo proposal (EP-09-001)"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        return Status.SUCCESS


def case_manager_admits_proposal_guard(
    case_id: str,
) -> py_trees.composites.Selector:
    """Precondition guard: when this actor is the CASE_MANAGER, EM admits a proposal.

    A read-only composite for a received tree's ``precondition_guards``
    (CLP-10-009): skips as SUCCESS for a participant replica and runs
    :class:`EmStateAdmitsProposalNode` for the manager, so a proposal the
    canonical case cannot take is refused before the guarded commit writes
    an entry for it.
    """
    return create_case_manager_gated_tree(
        name="AdmitsEmbargoProposalIfCaseManager",
        case_id=case_id,
        children=[EmStateAdmitsProposalNode(case_id=case_id)],
    )


__all__ = [
    "EmStateAdmitsProposalNode",
    "EmbargoProposalNotYetRecordedNode",
    "case_manager_admits_proposal_guard",
]
