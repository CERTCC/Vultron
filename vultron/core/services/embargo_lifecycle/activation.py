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

"""Active-embargo register operations: activate and terminate.

Both change the register's ``ACTIVE`` entry rather than a consent row —
activation is the case owner's ``Accept(EmbargoEvent, target=Case)`` (the
creation-time accept is ``initialize_creation_embargo`` in ``creation.py``,
one write per EP-04-002), termination is the ``ET`` teardown that
terminates the embargo in force and cancels every open proposal
in the same step (EP-08-004, ADR-0122).
"""

import logging

from vultron.core.models.embargo_register import termination_changes
from vultron.core.services.embargo_lifecycle.pec_activation import (
    _PecActivationMixin,
)
from vultron.core.services.embargo_lifecycle.results import (
    EmbargoLifecycleResult,
    TransitionMode,
)
from vultron.core.states.embargo_register import TerminationReason
from vultron.errors import VultronInvalidStateTransitionError

logger = logging.getLogger(__name__)


class _ActivationOperationsMixin(_PecActivationMixin):
    """``terminate_active_embargo`` and ``activate_embargo``."""

    def terminate_active_embargo(
        self,
        *,
        case_id: str,
        reason: TerminationReason,
        actor_id: str | None = None,
        transition_mode: TransitionMode = TransitionMode.STRICT,
    ) -> EmbargoLifecycleResult:
        """Terminate the active embargo on a case.

        One register step: the ``ACTIVE`` entry is ``TERMINATED`` with
        *reason* and every ``PROPOSED`` entry is ``CANCELLED`` (EP-08-004,
        ADR-0113: one active embargo makes every open proposal a revision of
        it, and a revision of an embargo that no longer exists cannot be
        accepted), so EM derives ``EXITED``.  No participant's consent is
        written: with no ``ACTIVE`` entry nobody is bound, and nothing more
        can be consented to (ADR-0118, ADR-0122).  The teardown replay node
        runs this in ``OBSERVED`` mode, so the rule holds on every replica;
        there, a case already ``EXITED`` is left as it is.

        Args:
            case_id: ID of the ``VulnerabilityCase`` to update.
            reason: Why the embargo ended.  Required on the step and logged;
                not stored on the entry until #4293 carries it on the wire.
            actor_id: Optional ID of the terminating actor (logging only).
            transition_mode: ``STRICT`` (default) or ``OBSERVED``.

        Returns:
            :class:`EmbargoLifecycleResult` describing what changed.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case.
            VultronInvalidStateTransitionError: In ``STRICT`` mode, if the
                case has no active embargo to terminate.
        """
        case = self._read_case(case_id)
        em_before = case.em_state
        embargo_id = case.active_embargo_id
        if embargo_id is None:
            if transition_mode == TransitionMode.STRICT:
                raise VultronInvalidStateTransitionError(
                    f"Case '{case_id}' has no active embargo to terminate."
                )
            logger.warning(
                "OBSERVED mode: case '%s' has no active embargo to terminate"
                " (EM %s); case left unchanged",
                case_id,
                em_before,
            )
            return self._unchanged_result(em_before)

        if not self._apply_register_step(
            case,
            termination_changes(case.embargo_register, reason),
            transition_mode=transition_mode,
            actor_id=actor_id,
        ):
            return self._unchanged_result(em_before)
        self._persistence.save(case)

        logger.info(
            "Actor '%s' terminated embargo '%s' on case '%s' (%s; EM %s → %s)",
            actor_id,
            embargo_id,
            case_id,
            reason,
            em_before,
            case.em_state,
        )

        return EmbargoLifecycleResult(
            em_before=em_before,
            em_after=case.em_state,
            case_changed=True,
            case_embargo_changed=True,
        )

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
        the same step, so EM derives ``ACTIVE``.  In ``STRICT`` mode the entry
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
        *embargo_id* is ``DECLINED`` cannot activate it, in either mode: it is
        invited again first.

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
                set; in either mode, if the owner's row for it is
                ``DECLINED``.
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
        self._assert_owner_may_activate(case, embargo_id)

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
