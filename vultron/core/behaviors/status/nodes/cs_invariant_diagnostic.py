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
violated — embargo still active with PXA P/X/A bit set — posts a
``Add(Note, VulnerabilityCase)`` to the case record.  A replica that
received the CASE_MANAGER's own P/X/A declaration ahead of its teardown
entry posts nothing (RSH-03-004): that gap is expected, not a violation
worth reporting.

Per CSB-18-002, CSB-18-003, CSB-18-004. Resolves CONCERN-3008.
"""

import logging

from py_trees.common import Status

from vultron.core.behaviors.helpers import _EmitSingleActivityBase
from vultron.core.behaviors.status.nodes.threat_termination import (
    resolve_pxa_threat_state,
    teardown_left_to_case_manager,
)
from vultron.core.models.protocols import PersistableModel
from vultron.core.states.composite_state_invariants import (
    violation_pxa_em_entailment,
)

logger = logging.getLogger(__name__)


class PxaEmInvariantDiagnosticNode(_EmitSingleActivityBase):
    """Post-cascade PXA↔EM cross-machine invariant check (CSB-18-002..004).

    Reads fresh EM state from the DataLayer after
    :class:`~vultron.core.behaviors.status.nodes.threat_termination.ThreatTerminationBranchNode`
    has run. When the invariant is still violated — embargo active with PXA
    P/X/A bit set — creates a ``Note`` and posts it to the case via
    ``Add(Note, VulnerabilityCase)``.

    The ``Add(Note, VulnerabilityCase)`` is a protocol-significant outbound
    activity (AC-3, CSB-18-002/003/004): participants must be notified of
    active-embargo violations so they can respond.  The write therefore goes
    through ``_emit_through_seam`` (OX-14-001, ASK-04-008).

    ``_EmitSingleActivityBase._call_factory()`` is not used here: the emit
    path has complex conditional logic (invariant check, CASE_MANAGER gate,
    note creation) that does not fit the simple guard→factory→queue skeleton.
    ``update()`` is overridden.

    This node runs whether or not the authorization gate permitted teardown,
    because :class:`~vultron.core.behaviors.status.add_case_status_tree.add_case_status_tree`
    wraps the gate and teardown in a ``FailureIsSuccess`` decorator.  Reading
    fresh DataLayer state after that block therefore reflects the post-teardown
    (or post-block) EM value, allowing accurate post-hoc detection.

    Returns :data:`py_trees.common.Status.SUCCESS` in all cases — diagnostic
    failures degrade gracefully so the enclosing Sequence is not aborted.

    Per CSB-18-002, CSB-18-003, CSB-18-004.
    """

    def __init__(
        self,
        status_obj: PersistableModel | None,
        case_id: str | None,
        sender_actor_id: str | None = None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.status_obj = status_obj
        self.case_id = case_id
        self.sender_actor_id = sender_actor_id

    def _get_pxa_state(self):
        """Return PXA state from status_obj if a threat is present; None otherwise."""
        case_status = getattr(self.status_obj, "case_status", None)
        if case_status is None:
            case_status = self.status_obj
        return resolve_pxa_threat_state(case_status)

    def update(self) -> Status:
        if not self.case_id:
            return Status.SUCCESS

        pxa = self._get_pxa_state()
        if pxa is None:
            return Status.SUCCESS

        if self._require_datalayer_and_actor() is not None:
            return Status.SUCCESS

        assert self.datalayer is not None
        assert self.actor_id is not None

        # Lenient diagnostic (ADR-0087): this node only *warns* on an invariant
        # violation and never fails the tree (every path is SUCCESS). An
        # unresolvable case has nothing to diagnose (conformance allowlist).
        case = self.datalayer.read_case(self.case_id)
        if case is None:
            return Status.SUCCESS

        em = case.em_state
        violation = violation_pxa_em_entailment(pxa, em)
        if violation is None:
            return Status.SUCCESS

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
            return Status.SUCCESS

        logger.warning(
            "PxaEmInvariantDiagnosticNode: CSB-18 violation in case '%s': %s",
            self.case_id,
            violation,
        )

        if self.trigger_activity_factory is None:
            logger.warning(
                "PxaEmInvariantDiagnosticNode: no TriggerActivityPort —"
                " cannot post Note for CSB-18 violation in case '%s'",
                self.case_id,
            )
            return Status.SUCCESS

        to_recipients = [self.sender_actor_id] if self.sender_actor_id else []
        try:
            note_id, _ = self.trigger_activity_factory.create_note(
                name=f"CSB-18 invariant violation in case {self.case_id}",
                content=violation,
                context_id=self.case_id,
                attributed_to=self.actor_id,
            )
            activity_id, _ = self.trigger_activity_factory.add_note_to_case(
                note_id=note_id,
                case_id=self.case_id,
                actor=self.actor_id,
                to=to_recipients,
            )
            # Route through the shared emit seam (OX-14-001, ASK-04-008).
            # factory.add_note_to_case returns (id, blob); pass empty blob
            # since no captured dict is present.
            self._emit_through_seam(activity_id, "")
            logger.info(
                "PxaEmInvariantDiagnosticNode: queued Add(Note,Case) '%s'"
                " for CSB-18 violation in case '%s'",
                activity_id,
                self.case_id,
            )
        except Exception as e:  # noqa: BLE001  # ruff-baseline #3768
            logger.warning(
                "PxaEmInvariantDiagnosticNode: failed to post Note for"
                " CSB-18 violation in case '%s': %s",
                self.case_id,
                e,
            )

        return Status.SUCCESS


__all__ = ["PxaEmInvariantDiagnosticNode"]
