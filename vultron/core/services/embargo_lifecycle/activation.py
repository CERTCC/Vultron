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

"""Active-embargo register operations: activate.

``activate_embargo`` changes the register's ``ACTIVE`` entry rather than a
consent row — activation is the case owner's
``Accept(EmbargoEvent, target=Case)`` (the creation-time accept is
``initialize_creation_embargo`` in ``creation.py``, one write per
EP-04-002).  Termination is handled by :func:`decide_termination` (the
decide half) plus the one apply function
:func:`~vultron.core.models.embargo_apply.apply_embargo_change` (ADR-0124).
"""

import logging
from datetime import datetime

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_apply import RegisterStep, RegisterStepKind
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_termination import (
    EmbargoTermination,
    TerminationRequest,
    ThreatSignalTermination,
    end_time_violations,
    has_reached_end_time,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.embargo_lifecycle.pec_activation import (
    _PecActivationMixin,
)
from vultron.core.services.embargo_lifecycle.results import (
    EmbargoLifecycleResult,
    TransitionMode,
)
from vultron.core.services.embargo_ordering import read_embargo_event
from vultron.core.states.embargo_register import TerminationReason
from vultron.errors import VultronInvalidStateTransitionError

logger = logging.getLogger(__name__)


def embargo_in_force(
    store: CasePersistence, case: VulnerabilityCase
) -> EmbargoEvent | None:
    """The embargo in force on *case*, or ``None`` when there is none.

    Read inline from the register when carried there, else from *store*,
    failing closed (EMB-18-003).

    Raises:
        VultronNotFoundError: the embargo in force cannot be read.
        VultronNotAnEmbargoError: its record is not an ``EmbargoEvent``.
    """
    active = case.active_embargo
    embargo_id = case.active_embargo_id
    if active is None or embargo_id is None:
        return None
    if isinstance(active, EmbargoEvent):
        return active
    return read_embargo_event(store, embargo_id)


def termination_timing_violations(
    store: CasePersistence,
    case: VulnerabilityCase,
    termination: EmbargoTermination,
    at: datetime | None,
) -> list[str]:
    """Why *termination* of *case*'s embargo in force may not apply at *at*.

    An ``END_TIME_REACHED`` termination claimed before the embargo's end
    time is refused (ADR-0122); see
    :func:`~vultron.core.models.embargo_termination.end_time_violations`.
    The embargo is read by :func:`embargo_in_force`.  No embargo in force, or
    an ``EARLY`` termination, has nothing to check.

    Raises:
        VultronNotFoundError: the embargo in force cannot be read.
    """
    if termination.reason != TerminationReason.END_TIME_REACHED:
        return []
    embargo = embargo_in_force(store, case)
    if embargo is None:
        return []
    return end_time_violations(termination, end_time=embargo.end_time, at=at)


def embargo_end_time_passed(
    store: CasePersistence, case: VulnerabilityCase, at: datetime
) -> bool:
    """Whether *case*'s embargo in force has reached its end time at *at*.

    ``False`` when no embargo is in force.  The embargo is read by
    :func:`embargo_in_force`; the rule is
    :func:`~vultron.core.models.embargo_termination.has_reached_end_time`.

    Raises:
        VultronNotFoundError: the embargo in force cannot be read.
    """
    embargo = embargo_in_force(store, case)
    return embargo is not None and has_reached_end_time(embargo.end_time, at)


def decide_termination(
    store: CasePersistence,
    case: VulnerabilityCase,
    termination: TerminationRequest,
    terminated_at: datetime | None,
) -> RegisterStep:
    """The CASE_MANAGER's decision to end *case*'s embargo in force.

    The decide half of a termination (ADR-0124): the ``TERMINATE`` register
    step the ``Remove(EmbargoEvent)`` entry carries, naming the embargo in
    force and the termination its ``TERMINATED`` entry records.  A
    :class:`ThreatSignalTermination` is resolved here against the case's PXA
    state, so the entry names the signals set; an ``END_TIME_REACHED``
    claimed at *terminated_at* before the embargo's end time is refused
    (ADR-0122).  Nothing is written: the step is committed, then applied
    through :func:`~vultron.core.models.embargo_apply.apply_embargo_change`.

    Raises:
        VultronInvalidStateTransitionError: no embargo is in force, the
            threat signals are not set, or the termination is not yet due.
        VultronNotFoundError: the embargo in force cannot be read.
    """
    embargo_id = case.active_embargo_id
    if embargo_id is None:
        raise VultronInvalidStateTransitionError(
            f"Case '{case.id_}' has no active embargo to terminate."
        )
    if isinstance(termination, ThreatSignalTermination):
        try:
            termination = termination.resolve(case.current_status.pxa.state)
        except ValueError as exc:
            raise VultronInvalidStateTransitionError(
                f"Case '{case.id_}': {exc}"
            ) from exc
    violations = termination_timing_violations(
        store, case, termination, terminated_at
    )
    if violations:
        raise VultronInvalidStateTransitionError(
            f"Refused termination of embargo '{embargo_id}' on case"
            f" '{case.id_}': " + "; ".join(violations)
        )
    return RegisterStep(
        kind=RegisterStepKind.TERMINATE,
        embargo=embargo_id,
        termination=termination,
    )


class _ActivationOperationsMixin(_PecActivationMixin):
    """``activate_embargo``."""

    def activate_embargo(
        self,
        *,
        case_id: str,
        embargo_id: str,
        actor_id: str | None = None,
        transition_mode: TransitionMode = TransitionMode.STRICT,
    ) -> EmbargoLifecycleResult:
        """Apply the case owner's activation of a proposed embargo.

        ``Accept(EmbargoEvent, target=Case)`` (ADR-0122): ``ACTIVATE``
        *embargo_id*'s register entry and ``SUPERSEDE`` any ``ACTIVE`` one in
        the same step, so EM derives ``ACTIVE``, or ``REVISE`` while another
        proposal stays open as a revision (ADR-0130).  In ``STRICT`` mode the entry
        must be an open proposal and P/X/A must be clear (EMB-02-002).  In
        ``OBSERVED`` mode a replica that never saw the proposal records it
        first, and a step the register refuses is skipped (EP-09-007).

        The consent effect (EP-05-001, MSM-07-005) runs in both modes, so a
        replica syncing an announced activation keeps its consent rows in
        step with the CASE_MANAGER: the owner's row for *embargo_id* becomes
        ``AGREED`` unless it already is (activation is the owner's decision,
        so the owner is never lapsed by it), and when this replaces an active
        embargo A with a B that ends no later, every signatory of A is
        carried over to B by ``CARRY_OVER``; under a longer B the signatories
        who have not agreed to it have lapsed by derivation (CM-18-001).
        Whoever holds an ``AGREED`` row for B — its proposer, for one — is a
        signatory by lookup, with nothing to advance.  An owner whose row for
        *embargo_id* is ``DECLINED`` has changed its answer by activating it:
        its row moves straight to ``AGREED``, in either mode (MSM-07-008).

        Args:
            case_id: ID of the ``VulnerabilityCase`` to update.
            embargo_id: ID of the ``EmbargoEvent`` to set as active.
            actor_id: Optional ID of the activating actor (logging only).
            transition_mode: ``STRICT`` (default) or ``OBSERVED``.

        Returns:
            :class:`EmbargoLifecycleResult` describing what changed.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case,
                or the embargo being activated or the one it replaces cannot
                be read (EMB-18-003, EP-05-001) — in either mode, before any
                write.
            VultronValidationError: If either embargo record is not an
                ``EmbargoEvent``.
            VultronInvalidStateTransitionError: In ``STRICT`` mode, if
                *embargo_id* is not an open proposal of the case or P/X/A is
                set.
        """
        case = self._read_case(case_id)

        em_before = case.em_state
        previous_embargo_id = case.active_embargo_id
        # Read the activated (and any replaced) embargo and decide the
        # EP-05-001 arm before anything is written (fail closed, EMB-18-003).
        ends_no_later = self._activation_arm(
            previous_embargo_id=previous_embargo_id,
            activated_embargo_id=embargo_id,
        )
        if transition_mode == TransitionMode.STRICT:
            self._assert_pxa_embargo_eligible(
                case.current_status.pxa.state, case_id, "activate embargo"
            )

        if not self._activate_entry(
            case,
            embargo_id,
            transition_mode=transition_mode,
            actor_id=actor_id,
        ):
            return self._unchanged_result(em_before)
        self._persistence.save(case)
        em_after = case.em_state

        participant_changes = self._consent_at_activation(
            case,
            embargo_id=embargo_id,
            previous_embargo_id=previous_embargo_id,
            ends_no_later=ends_no_later,
        )

        logger.info(
            "Actor '%s' activated embargo '%s' on case '%s' (EM %s → %s)",
            actor_id,
            embargo_id,
            case_id,
            em_before,
            em_after,
        )

        return self._activation_result(
            em_before=em_before,
            em_after=em_after,
            participant_changes=participant_changes,
        )
