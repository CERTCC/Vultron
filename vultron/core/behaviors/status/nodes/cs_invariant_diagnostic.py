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

"""Post-cascade PXA↔EM cross-machine invariant diagnostic node.

Calls :func:`~vultron.core.states.composite_state_invariants.violation_pxa_em_entailment`
after :class:`~vultron.core.behaviors.status.nodes.threat_termination.ThreatTerminationBranchNode`
has had a chance to terminate the embargo.  When the invariant is still
violated — embargo still active with PXA P/X/A bit set — the CASE_MANAGER
records a note on the case as its own ``add_note_to_case`` entry (#4829).
A declaration the CASE_MANAGER itself made ahead of its teardown entry gets
no note (RSH-03-004): that gap is expected, not a violation worth reporting.

Per CSB-18-002, CSB-18-003, CSB-18-004. Resolves CONCERN-3008.
"""

import logging

from vultron.core.behaviors.note.case_manager_note import (
    CaseManagerNote,
    _CommitCaseManagerNoteBase,
)
from vultron.core.behaviors.status.nodes.threat_termination import (
    resolve_pxa_threat_state,
    teardown_left_to_case_manager,
)
from vultron.core.models.protocols import PersistableModel
from vultron.core.states.composite_state_invariants import (
    violation_pxa_em_entailment,
)

logger = logging.getLogger(__name__)


class PxaEmInvariantDiagnosticNode(_CommitCaseManagerNoteBase):
    """Post-cascade PXA↔EM cross-machine invariant check (CSB-18-002..004).

    Reads fresh EM state from the DataLayer after
    :class:`~vultron.core.behaviors.status.nodes.threat_termination.ThreatTerminationBranchNode`
    has run. When the invariant is still violated — embargo active with PXA
    P/X/A bit set — the CASE_MANAGER records a note naming the violation and
    attaches it to the case; participants, the sender among them, learn of
    it from the ledger fan-out
    (:class:`~vultron.core.behaviors.note.case_manager_note._CommitCaseManagerNoteBase`).
    The node runs in the tree's CASE_MANAGER-gated effects, as every commit
    of a CASE_MANAGER act does.

    This node runs whether or not the authorization gate permitted teardown,
    because :class:`~vultron.core.behaviors.status.add_case_status_tree.add_case_status_tree`
    wraps the gate and teardown in a ``FailureIsSuccess`` decorator.  Reading
    fresh DataLayer state after that block therefore reflects the post-teardown
    (or post-block) EM value, allowing accurate post-hoc detection.

    No violation, no case context or an unresolvable case is a no-op
    SUCCESS (lenient diagnostic, ADR-0087).  The note is best-effort: a
    missing trigger-activity port or a refused commit is logged and the node
    succeeds; an internal error propagates.

    Per CSB-18-002, CSB-18-003, CSB-18-004.
    """

    _BEST_EFFORT = True

    def __init__(
        self,
        status_obj: PersistableModel | None,
        case_id: str | None,
        sender_actor_id: str | None = None,
        name: str | None = None,
    ):
        # No case context is a no-op (``_compose``), never a commit.
        super().__init__(
            case_id=case_id or "", name=name or self.__class__.__name__
        )
        self.status_obj = status_obj
        self.case_id = case_id
        self.sender_actor_id = sender_actor_id

    def _get_pxa_state(self):
        """Return PXA state from status_obj if a threat is present; None otherwise."""
        case_status = getattr(self.status_obj, "case_status", None)
        if case_status is None:
            case_status = self.status_obj
        return resolve_pxa_threat_state(case_status)

    def _compose(self) -> CaseManagerNote | None:
        if not self.case_id:
            return None

        pxa = self._get_pxa_state()
        if pxa is None:
            return None

        assert self.datalayer is not None

        # Lenient diagnostic (ADR-0087): this node only *warns* on an invariant
        # violation and never fails the tree. An unresolvable case has nothing
        # to diagnose (conformance allowlist).
        case = self.datalayer.read_case(self.case_id)
        if case is None:
            return None

        violation = violation_pxa_em_entailment(pxa, case.em_state)
        if violation is None:
            return None

        if teardown_left_to_case_manager(
            case, self.datalayer, self.sender_actor_id, self.actor_id
        ):
            # RSH-03-004: the CASE_MANAGER declared this status after its
            # own teardown, so the violation is only this replica lagging
            # the committed entry.  Telling the manager is noise.
            logger.info(
                "PxaEmInvariantDiagnosticNode: case '%s' awaits the"
                " CASE_MANAGER's teardown entry (%s); no Note posted",
                self.case_id,
                violation,
            )
            return None

        logger.warning(
            "PxaEmInvariantDiagnosticNode: CSB-18 violation in case '%s': %s",
            self.case_id,
            violation,
        )
        return CaseManagerNote(
            name=f"CSB-18 invariant violation in case {self.case_id}",
            content=violation,
        )


__all__ = ["PxaEmInvariantDiagnosticNode"]
