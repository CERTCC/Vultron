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

"""Proposal-phase EM operations: propose, accept and reject.

These are the operations that answer an ``Invite(EmbargoEvent)``: the owner's
call drives the shared EM machine, and any actor's call records their own
consent on their participant record.
"""

import logging

from vultron.core.models._helpers import _as_id
from vultron.core.models.dimensions import EmDimension
from vultron.core.services.embargo_lifecycle.pec import (
    _PecEffectsMixin,
)
from vultron.core.services.embargo_lifecycle.results import (
    EmbargoLifecycleResult,
    ParticipantPECChange,
    TransitionMode,
)
from vultron.core.states.em import EM, EM_Trigger

logger = logging.getLogger(__name__)


class _ProposalOperationsMixin(_PecEffectsMixin):
    """``propose_embargo``, ``accept_embargo_invite``, ``reject_embargo_invite``."""

    def propose_embargo(
        self,
        *,
        case_id: str,
        embargo_id: str,
        actor_id: str | None = None,
        transition_mode: TransitionMode = TransitionMode.STRICT,
        em_before: EM | None = None,
    ) -> EmbargoLifecycleResult:
        """Propose or counter-propose an embargo on a case.

        Valid EM transitions (STRICT mode):
            - ``NONE → PROPOSED``  (initial proposal)
            - ``PROPOSED → PROPOSED``    (counter-proposal / idempotent)
            - ``ACTIVE → REVISE``        (revision proposal; cascades PEC)
            - ``REVISE → REVISE``        (counter-revision / idempotent)

        The ``EmbargoEvent`` identified by *embargo_id* MUST already exist in
        the DataLayer before this method is called; the caller is responsible
        for creating it.

        Args:
            case_id: ID of the :class:`~...VulnerabilityCase` to update.
            embargo_id: ID of the pre-existing ``EmbargoEvent`` being proposed.
            actor_id: Optional ID of the actor initiating the proposal (used
                for logging only; no ownership gate on propose).
            transition_mode: ``STRICT`` (default) enforces valid transitions.
                ``OBSERVED`` syncs local state even when the transition would
                not normally be valid, forcing ``PROPOSED`` (or ``REVISE``
                when the local state is ``ACTIVE``/``REVISE``).
            em_before: When provided, the service uses this value directly
                instead of reading it from the case.

        Returns:
            :class:`EmbargoLifecycleResult` describing what changed.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case.
            VultronInvalidStateTransitionError: If the current EM state does
                not allow a PROPOSE transition (``STRICT`` mode only), or if
                any of P/X/A is set on the case (``STRICT`` mode only,
                per EMB-01-002).
        """
        case = self._read_case(case_id)

        if em_before is None:
            em_before = case.current_status.em.state
        assert em_before is not None

        if transition_mode == TransitionMode.STRICT:
            self._assert_pxa_embargo_eligible(
                case.current_status.pxa.state,
                case_id,
                "propose embargo",
            )

        # OBSERVED fallback: ACTIVE/REVISE stays in REVISE; otherwise PROPOSED
        fallback = (
            EM.REVISE if em_before in (EM.ACTIVE, EM.REVISE) else EM.PROPOSED
        )
        em_after = self._drive_em_transition(
            case_id=case_id,
            em_before=em_before,
            trigger=EM_Trigger.PROPOSE,
            transition_mode=transition_mode,
            fallback_dest=fallback,
            actor_id=actor_id,
        )

        # Cascade PEC: ACTIVE → REVISE transitions SIGNATORY participants to LAPSED
        participant_changes: list[ParticipantPECChange] = []
        if em_before == EM.ACTIVE and em_after == EM.REVISE:
            participant_changes = self._cascade_pec_revise(case)

        case_mutated = False

        if em_after != em_before:
            case.current_status.em = EmDimension(state=em_after)
            case_mutated = True

        # Idempotent append
        if embargo_id not in case.proposed_embargo_ids:
            case.proposed_embargoes.append(embargo_id)
            case_mutated = True

        if case_mutated or participant_changes:
            self._persistence.save(case)

        if em_after != em_before:
            logger.info(
                "Actor '%s' proposed embargo '%s' on case '%s' (EM %s → %s)",
                actor_id,
                embargo_id,
                case_id,
                em_before,
                em_after,
            )
        else:
            logger.info(
                "Actor '%s' counter-proposed embargo '%s' on case '%s'"
                " (EM %s, no state change)",
                actor_id,
                embargo_id,
                case_id,
                em_before,
            )

        return EmbargoLifecycleResult(
            em_before=em_before,
            em_after=em_after,
            case_changed=case_mutated or bool(participant_changes),
            case_embargo_changed=False,
            pec_reset=False,
            participant_changes=participant_changes,
        )

    def accept_embargo_invite(
        self,
        *,
        case_id: str,
        embargo_id: str,
        actor_id: str,
        transition_mode: TransitionMode = TransitionMode.STRICT,
        em_before: EM | None = None,
    ) -> EmbargoLifecycleResult:
        """Accept an embargo invite on a case.

        If *actor_id* is the case owner (``attributed_to``), drives the EM
        state machine ``PROPOSED → ACTIVE`` (or ``REVISE → ACTIVE``) and
        activates the embargo via ``case.set_embargo(embargo_id)``.  For any
        actor (owner or not) the actor's participant record is updated:
        PEC state transitions to ``SIGNATORY`` and *embargo_id* is added
        idempotently to ``accepted_embargo_ids``.

        Args:
            case_id: ID of the ``VulnerabilityCase`` to update.
            embargo_id: ID of the ``EmbargoEvent`` being accepted.
            actor_id: ID of the accepting actor.
            transition_mode: ``STRICT`` (default) or ``OBSERVED``.
            em_before: When provided, the service uses this value directly
                instead of reading it from the case.

        Returns:
            :class:`EmbargoLifecycleResult` describing what changed.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case.
            VultronInvalidStateTransitionError: If the EM state does not allow
                an ACCEPT transition (``STRICT`` mode, owner only), or if the
                owner would drive EM to ACTIVE but P/X/A is set (``STRICT``
                mode, owner only, per EMB-02-002).  Non-owner callers record
                PEC state only and are not blocked by P/X/A.
        """
        case = self._read_case(case_id)

        if em_before is None:
            em_before = case.current_status.em.state
        assert em_before is not None
        em_after = em_before
        case_mutated = False
        case_embargo_changed = False

        is_owner = _as_id(case.attributed_to) == actor_id
        active_embargo_id = _as_id(case.active_embargo)
        already_active = (
            em_before == EM.ACTIVE and active_embargo_id == embargo_id
        )

        if is_owner and not already_active:
            # Guard only applies when owner would drive the EM machine (EMB-02-002).
            if transition_mode == TransitionMode.STRICT:
                self._assert_pxa_embargo_eligible(
                    case.current_status.pxa.state,
                    case_id,
                    "accept embargo invite",
                )
            em_after = self._drive_em_transition(
                case_id=case_id,
                em_before=em_before,
                trigger=EM_Trigger.ACCEPT,
                transition_mode=transition_mode,
                fallback_dest=EM.ACTIVE,
                actor_id=actor_id,
            )
            if em_after != em_before:
                case.current_status.em = EmDimension(state=em_after)
                case_mutated = True
            # Sync active_embargo independently: handle OBSERVED mode where
            # em_after == em_before == ACTIVE but active_embargo points elsewhere
            if active_embargo_id != embargo_id:
                case.set_embargo(embargo_id)
                case_mutated = True
                case_embargo_changed = True

        if is_owner and case.discard_proposed_embargo(embargo_id):
            # The owner's accept decides the proposal: it is no longer open
            # (EP-08-003).  A participant's accept is consent, not a decision.
            case_mutated = True

        # Record acceptance in actor's participant record (owner or non-owner)
        participant_changes = self._record_actor_pec_acceptance(
            case, actor_id, embargo_id
        )

        if case_mutated or participant_changes:
            self._persistence.save(case)

        if is_owner and em_after != em_before:
            logger.info(
                "Actor '%s' accepted embargo '%s' on case '%s'"
                " (EM %s → %s; embargo activated)",
                actor_id,
                embargo_id,
                case_id,
                em_before,
                em_after,
            )
        else:
            logger.info(
                "Actor '%s' recorded consent for embargo '%s' on case '%s'"
                " (EM unchanged at %s)",
                actor_id,
                embargo_id,
                case_id,
                em_after,
            )

        return EmbargoLifecycleResult(
            em_before=em_before,
            em_after=em_after,
            case_changed=case_mutated or bool(participant_changes),
            case_embargo_changed=case_embargo_changed,
            pec_reset=False,
            participant_changes=participant_changes,
        )

    def reject_embargo_invite(
        self,
        *,
        case_id: str,
        embargo_id: str,
        actor_id: str,
        transition_mode: TransitionMode = TransitionMode.STRICT,
        em_before: EM | None = None,
    ) -> EmbargoLifecycleResult:
        """Reject an embargo proposal or revision on a case.

        If *actor_id* is the case owner, drives the EM state machine:
            - ``PROPOSED → NONE``  (initial proposal rejected)
            - ``REVISE → ACTIVE``        (revision rejected; returns to active)

        Per EMB-04-002, a REVISE rejection that would return the case to ACTIVE
        is blocked in STRICT mode when P/X/A is set — callers must invoke
        :meth:`terminate_active_embargo` (ET) instead.

        For any actor the actor's participant record is updated: PEC
        transitions to ``DECLINED`` and *embargo_id* is removed from
        ``accepted_embargo_ids`` (pocket-veto semantics).

        Args:
            case_id: ID of the ``VulnerabilityCase`` to update.
            embargo_id: ID of the ``EmbargoEvent`` being rejected.
            actor_id: ID of the rejecting actor.
            transition_mode: ``STRICT`` (default) or ``OBSERVED``.
            em_before: When provided, the service uses this value directly
                instead of reading it from the case.

        Returns:
            :class:`EmbargoLifecycleResult` describing what changed.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case.
            VultronInvalidStateTransitionError: If the EM state does not allow
                a REJECT transition (``STRICT`` mode, owner only), or if the
                case is in REVISE state with P/X/A set (``STRICT`` mode only,
                per EMB-04-002 — use terminate_active_embargo instead).
        """
        case = self._read_case(case_id)

        if em_before is None:
            em_before = case.current_status.em.state
        assert em_before is not None
        em_after = em_before
        case_mutated = False

        is_owner = _as_id(case.attributed_to) == actor_id

        if is_owner:
            # In STRICT mode, block REVISE→ACTIVE when P/X/A is set (EMB-04-002):
            # the case must be terminated (ET), not returned to ACTIVE.
            if (
                transition_mode == TransitionMode.STRICT
                and em_before == EM.REVISE
            ):
                self._assert_pxa_embargo_eligible(
                    case.current_status.pxa.state,
                    case_id,
                    "reject embargo revision (use terminate_active_embargo when P/X/A is set)",
                )
            # OBSERVED fallback: REVISE reject → ACTIVE; otherwise → NONE
            fallback = EM.ACTIVE if em_before == EM.REVISE else EM.NONE
            em_after = self._drive_em_transition(
                case_id=case_id,
                em_before=em_before,
                trigger=EM_Trigger.REJECT,
                transition_mode=transition_mode,
                fallback_dest=fallback,
                actor_id=actor_id,
            )
            if em_after != em_before:
                case.current_status.em = EmDimension(state=em_after)
                case_mutated = True
            if case.discard_proposed_embargo(embargo_id):
                # The owner's reject decides the proposal (EP-08-003).
                case_mutated = True

        participant_changes = self._record_actor_pec_rejection(
            case, actor_id, embargo_id
        )

        if case_mutated or participant_changes:
            self._persistence.save(case)

        logger.info(
            "Actor '%s' rejected embargo '%s' on case '%s' (EM %s → %s)",
            actor_id,
            embargo_id,
            case_id,
            em_before,
            em_after,
        )

        return EmbargoLifecycleResult(
            em_before=em_before,
            em_after=em_after,
            case_changed=case_mutated or bool(participant_changes),
            case_embargo_changed=False,
            pec_reset=False,
            participant_changes=participant_changes,
        )
