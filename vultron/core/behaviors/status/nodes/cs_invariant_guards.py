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

"""CS invariant precondition guards for the AddCaseStatusToCase receive path.

Two hard-reject guards enforcing the normatively-specified CS ordering
invariants (CSB-17-012, CSB-17-005):

1. :class:`CheckCsEphemeralStateNode` — pX ephemeral guard (CSB-17-012): when
   the current PXA state is pX (exploit public, public unaware), the incoming
   CaseStatus MUST advance P.  Returns FAILURE otherwise.

2. :class:`CheckCsHistoryPrefixNode` — history prefix guard (CSB-17-005):
   derives the single CS event implied by a current-to-asserted PXA state
   change and verifies it produces a valid CS history prefix.  Multi-event
   advances (remote peers that skip states) are deferred to
   :class:`FilterCsPxaDimensionNode` (RSH-05).  Returns FAILURE when the
   derived event would create an invalid prefix.

Both nodes are placed before :class:`FilterCsEmDimensionNode` in
``precondition_guards`` and return FAILURE to abort the Sequence before any
ledger write (CLP-10-009).
"""

import logging

from py_trees.common import Status

from vultron.core.behaviors.status.nodes.cs_dimension_filter import (
    _CsStatusGuardBase,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.states.cs import (
    CS_vfd,
    is_monotonic_pxa_forward,
    is_pxa_public_aware,
)
from vultron.core.states.cs_invariants import (
    CSEvent,
    cs_from_dimensions,
    cs_transition_event,
    is_valid_cs_history_prefix,
    required_next_cs_events,
)

logger = logging.getLogger(__name__)


class CheckCsEphemeralStateNode(_CsStatusGuardBase):
    """Guard: from a pX state the next CS event MUST be P (CSB-17-012).

    When the current compound CS state is pX (exploit public, public
    unaware), ``required_next_cs_events`` returns ``frozenset({CSEvent.P})``.
    This node returns FAILURE if the asserted PXA state does not advance P —
    aborting the Sequence before any ledger write (CLP-10-009).

    The VFD dimension is not present in :class:`~vultron.core.models.case_status.CaseStatus`.
    A ``CS_vfd.VFD``-complete baseline is used when constructing the compound
    state, which suppresses false vP positives (vendor-unaware + public-aware)
    while preserving the pX check that depends only on PXA.

    Returns SUCCESS when:

    - The case is not found in the DataLayer.
    - No materialized :class:`CaseStatus` exists yet (first-ever status).
    - The asserted status is unresolvable (deferred to
      :class:`FilterCsEmDimensionNode`, which will abort with FAILURE).
    - The current state is not ephemeral.
    - The asserted state satisfies the required-next-event constraint.

    Returns FAILURE when the current state is pX and the asserted PXA does
    not have P=True.

    Must run before :class:`FilterCsEmDimensionNode` in ``precondition_guards``.
    Per issue #2524 AC-1, CSB-17-012.
    """

    def update(self) -> Status:
        if not self.case_id:
            return Status.SUCCESS
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case = self.datalayer.read(self.case_id)
        if not isinstance(case, VulnerabilityCase):
            return Status.SUCCESS

        try:
            current = case.current_status
        except ValueError:
            return (
                Status.SUCCESS
            )  # first CaseStatus ever — no ephemeral constraint

        asserted = self._resolve_asserted()
        if asserted is None:
            # Unresolvable assertion: FilterCsEmDimensionNode will abort.
            return Status.SUCCESS

        current_pxa = current.pxa.state
        # VFD-complete baseline avoids false vP positives; only pX is detectable
        # from PXA-only data (CSB-17-012).
        current_cs = cs_from_dimensions(CS_vfd.VFD, current_pxa)
        required = required_next_cs_events(current_cs)
        if not required:
            return Status.SUCCESS  # not ephemeral

        # With VFD-complete baseline, only pX produces required == {CSEvent.P}.
        asserted_pxa = asserted.pxa.state
        if CSEvent.P in required and not is_pxa_public_aware(asserted_pxa):
            self.feedback_message = (
                f"Ephemeral CS state {current_cs.name!r} requires P next"
                f" (CSB-17-012); asserted PXA {asserted_pxa.name!r}"
                " does not advance P"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        return Status.SUCCESS


class CheckCsHistoryPrefixNode(_CsStatusGuardBase):
    """Guard: proposed single-event PXA transition must yield a valid CS history prefix (CSB-17-005).

    Derives the single CS event implied by the current-to-asserted PXA state
    change via :func:`~vultron.core.states.cs_invariants.cs_transition_event`
    and checks whether applying it from the current state produces a valid CS
    history prefix via
    :func:`~vultron.core.states.cs_invariants.is_valid_cs_history_prefix`.

    Multi-event advances (``cs_transition_event`` returns ``None``) are
    returned as SUCCESS: remote peers may skip states, and the monotone filter
    (:class:`FilterCsPxaDimensionNode`) handles partial-accept for those
    (RSH-05, CSB-16-002).

    The VFD dimension is not present in CaseStatus; a ``CS_vfd.VFD``-complete
    baseline is used to avoid vP false positives (same rationale as
    :class:`CheckCsEphemeralStateNode`).

    Returns FAILURE when the single proposed event would produce an invalid CS
    history prefix (e.g. A from pXa violates CSB-17-012).
    Returns SUCCESS in all other cases (no change, multi-event, or valid step).

    Must run before :class:`FilterCsEmDimensionNode` in ``precondition_guards``.
    Per issue #2524 AC-2, CSB-17-005.
    """

    def update(self) -> Status:
        if not self.case_id:
            return Status.SUCCESS
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case = self.datalayer.read(self.case_id)
        if not isinstance(case, VulnerabilityCase):
            return Status.SUCCESS

        try:
            current = case.current_status
        except ValueError:
            return Status.SUCCESS  # first CaseStatus ever

        asserted = self._resolve_asserted()
        if asserted is None:
            return Status.SUCCESS

        current_pxa = current.pxa.state
        asserted_pxa = asserted.pxa.state
        if current_pxa == asserted_pxa or not is_monotonic_pxa_forward(
            current_pxa, asserted_pxa
        ):
            # No PXA change or regression: deferred to FilterCsPxaDimensionNode (RSH-05).
            return Status.SUCCESS

        # VFD-complete baseline: only PXA bits can change between these two states.
        current_cs = cs_from_dimensions(CS_vfd.VFD, current_pxa)
        asserted_cs = cs_from_dimensions(CS_vfd.VFD, asserted_pxa)

        event = cs_transition_event(current_cs, asserted_cs)
        if event is None:
            # Multi-event skip: deferred to FilterCsPxaDimensionNode (RSH-05).
            return Status.SUCCESS

        if not is_valid_cs_history_prefix([event], start=current_cs):
            self.feedback_message = (
                f"CS history prefix violation: event {event!r} from"
                f" {current_cs.name!r} produces an invalid prefix"
                f" (CSB-17-005)"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        return Status.SUCCESS
