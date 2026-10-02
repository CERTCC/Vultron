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

"""Active-embargo EM operations: activate and terminate.

Both operate on ``case.active_embargo`` directly rather than answering an
invite — activation is a replica's sync of an announced activation (the
creation-time accept is ``initialize_creation_embargo`` in ``creation.py``,
one write per EP-04-002), termination is
the ``ET`` teardown that also resets every participant's consent and decides
every open proposal (EP-08-004).
"""

import logging

from vultron.core.models._helpers import _as_id
from vultron.core.models.dimensions import EmDimension
from vultron.core.services.embargo_lifecycle.pec import (
    _PecEffectsMixin,
)
from vultron.core.services.embargo_lifecycle.results import (
    EmbargoLifecycleResult,
    TransitionMode,
)
from vultron.core.states.em import EM, EM_Trigger
from vultron.errors import VultronInvalidStateTransitionError

logger = logging.getLogger(__name__)


class _ActivationOperationsMixin(_PecEffectsMixin):
    """``terminate_active_embargo`` and ``activate_embargo``."""

    def terminate_active_embargo(
        self,
        *,
        case_id: str,
        actor_id: str | None = None,
        transition_mode: TransitionMode = TransitionMode.STRICT,
        em_before: EM | None = None,
    ) -> EmbargoLifecycleResult:
        """Terminate the active embargo on a case.

        Drives ``ACTIVE → EXITED`` (or ``REVISE → EXITED``), clears
        ``case.active_embargo``, forgets **every** open proposal in both
        records (EP-08-004, ADR-0113: one active embargo makes every open
        proposal a revision of it, and a revision of an embargo that no
        longer exists cannot be accepted), and resets all participants' PEC
        state to ``UNBOUND`` via :meth:`_cascade_pec_reset`.  The teardown
        replay node runs this in ``OBSERVED`` mode, so the rule holds on
        every replica.

        Args:
            case_id: ID of the ``VulnerabilityCase`` to update.
            actor_id: Optional ID of the terminating actor (logging only).
            transition_mode: ``STRICT`` (default) or ``OBSERVED``.
            em_before: When provided, the service uses this value directly
                instead of reading it from the case.

        Returns:
            :class:`EmbargoLifecycleResult` describing what changed.
            ``pec_reset`` is always ``True`` when this method succeeds.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case.
            VultronInvalidStateTransitionError: In ``STRICT`` mode, if the EM
                state does not allow TERMINATE or ``active_embargo`` is
                ``None``.
        """
        case = self._read_case(case_id)

        if em_before is None:
            em_before = case.current_status.em.state
        assert em_before is not None

        # In STRICT mode, require an active embargo to be identified
        embargo_id = _as_id(case.active_embargo)
        if transition_mode == TransitionMode.STRICT and embargo_id is None:
            raise VultronInvalidStateTransitionError(
                f"Case '{case_id}' has no active embargo to terminate."
            )

        em_after = self._drive_em_transition(
            case_id=case_id,
            em_before=em_before,
            trigger=EM_Trigger.TERMINATE,
            transition_mode=transition_mode,
            fallback_dest=EM.EXITED,
            actor_id=actor_id,
        )

        case.current_status.em = EmDimension(state=em_after)
        case.active_embargo = None
        # Termination decides every open proposal, not only the terminated
        # embargo's own entry (EP-08-004).
        case.discard_all_proposed_embargoes()

        participant_changes = self._cascade_pec_reset(case)

        self._persistence.save(case)

        logger.info(
            "Actor '%s' terminated embargo '%s' on case '%s' (EM %s → %s)",
            actor_id,
            embargo_id,
            case_id,
            em_before,
            em_after,
        )

        return EmbargoLifecycleResult(
            em_before=em_before,
            em_after=em_after,
            case_changed=True,
            case_embargo_changed=True,
            pec_reset=True,
            participant_changes=participant_changes,
        )

    def activate_embargo(
        self,
        *,
        case_id: str,
        embargo_id: str,
        actor_id: str | None = None,
        transition_mode: TransitionMode = TransitionMode.STRICT,
    ) -> EmbargoLifecycleResult:
        """Activate an embargo on a case, driving EM state to ACTIVE.

        Drives ``PROPOSED → ACTIVE`` (or ``REVISE → ACTIVE``) via the ACCEPT
        trigger and sets ``case.active_embargo`` to *embargo_id*.  In ``STRICT``
        mode only PROPOSED and REVISE are valid sources.  In ``OBSERVED`` mode
        the transition is applied unconditionally (state-sync override).

        When this replaces an active embargo A with *embargo_id* (B), the
        case owner's acceptance of B is recorded (activation is the owner's
        decision, so the owner is never lapsed by it) and every participant's
        consent is re-evaluated against B (EP-05-001, MSM-07-005) exactly as
        the owner's ``accept_embargo_invite`` does:
        a shorter-or-equal B carries every signatory over, a longer B lapses
        the signatories whose ``accepted_embargo_ids`` lack it.  On every
        activation, first or replacement, a non-signatory that already holds
        B (its proposer, for one) becomes ``SIGNATORY``.  The cascade runs in
        both modes, so a replica syncing an announced activation keeps its
        consent records in step with the CASE_MANAGER.

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
            VultronInvalidStateTransitionError: In ``STRICT`` mode, if the EM
                state does not allow an ACCEPT trigger (valid sources: PROPOSED,
                REVISE).
        """
        case = self._read_case(case_id)

        em_before = case.current_status.em.state
        previous_embargo_id = case.active_embargo_id
        # Read the activated (and any replaced) embargo and decide the
        # EP-05-001 arm before anything is written (fail closed, EMB-18-003).
        ends_no_later = self._activation_arm(
            previous_embargo_id=previous_embargo_id,
            activated_embargo_id=embargo_id,
        )

        em_after = self._drive_em_transition(
            case_id=case_id,
            em_before=em_before,
            trigger=EM_Trigger.ACCEPT,
            transition_mode=transition_mode,
            fallback_dest=EM.ACTIVE,
            actor_id=actor_id,
        )

        self._save_activation(case, em_after=em_after, embargo_id=embargo_id)

        # The embargo in force changed: the same consent effect as the owner
        # path of accept_embargo_invite (EP-05-001; on a replacement the
        # owner's acceptance of B is recorded first, so the owner is never
        # lapsed by its own activation).
        participant_changes = self._consent_at_activation(
            case, embargo_id=embargo_id, ends_no_later=ends_no_later
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
