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

"""EmbargoLifecycle service — consolidated EM + PEC state management.

This service is the single authoritative place for all Embargo Management (EM)
and Participant Embargo Consent (PEC) state transitions.  Callers — trigger use
cases, received use cases, and BT nodes — inject an ``EmbargoLifecycle`` instance
and call named operations; they never instantiate ``EMAdapter`` or
``create_em_machine()`` directly.

Usage::

    from vultron.core.services.embargo_lifecycle import (
        EmbargoLifecycle,
        EmbargoLifecycleResult,
        TransitionMode,
    )

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.propose_embargo(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=actor.id_,
    )
    # result.em_before, result.em_after, result.case_changed, ...

Tracked in: https://github.com/CERTCC/Vultron/issues/538
Scaffold (#746); full operations (#747)
"""

import logging
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field
from transitions import MachineError

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM, EM_Trigger, EMAdapter, create_em_machine
from vultron.core.states.participant_embargo_consent import (
    PEC,
    PEC_Trigger,
    apply_pec_trigger,
)
from vultron.core.use_cases._helpers import _as_id
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronNotFoundError,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class TransitionMode(StrEnum):
    """Controls how strict the EM state machine is during a transition.

    ``STRICT``   — Used by BT behaviors and trigger use cases.  The service
                   enforces that the requested transition is valid for the
                   current EM state and raises
                   :exc:`~vultron.errors.VultronInvalidStateTransitionError`
                   otherwise.

    ``OBSERVED`` — Used by received use cases.  The remote party has already
                   asserted the new state; the service syncs local state even
                   if the local machine would not have initiated that
                   transition.  Implemented in follow-up issue #747.
    """

    STRICT = "STRICT"
    OBSERVED = "OBSERVED"


class ParticipantPECChange(BaseModel):
    """Records a single participant's PEC state change during a lifecycle op."""

    participant_id: str
    pec_before: str
    pec_after: str


class EmbargoLifecycleResult(BaseModel):
    """Structured result returned by every :class:`EmbargoLifecycle` operation.

    Enables test assertions at the service boundary without inspecting
    DataLayer internals.

    Attributes:
        em_before: EM state before the operation.
        em_after: EM state after the operation.
        case_changed: True if the case object was mutated and persisted.
        case_embargo_changed: True if ``case.active_embargo`` was modified
            (e.g. an embargo was activated or cleared).
        pec_reset: True if a full PEC reset was performed across all
            participants (e.g. on embargo termination).
        participant_changes: Per-participant PEC state changes that occurred
            during the operation (e.g. signatories lapsed on REVISE).
    """

    em_before: EM
    em_after: EM
    case_changed: bool
    case_embargo_changed: bool
    pec_reset: bool
    participant_changes: list[ParticipantPECChange] = Field(
        default_factory=list
    )


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


class EmbargoLifecycle:
    """Consolidated EM + PEC state management service.

    Owns all Embargo Management (EM) and Participant Embargo Consent (PEC)
    state transition logic.  Hides ``create_em_machine()``, ``EMAdapter``,
    ``MachineError`` handling, actor-to-participant lookup via
    ``actor_participant_index``, PEC trigger application, and idempotent
    ``proposed_embargoes`` / ``accepted_embargo_ids`` management.

    Callers inject a :class:`~vultron.core.ports.case_persistence.CasePersistence`
    instance once at construction.  ``SqliteDataLayer`` satisfies the protocol
    structurally.

    Public operations (all support ``STRICT`` and ``OBSERVED`` modes):
        - :meth:`propose_embargo`
        - :meth:`accept_embargo_invite`
        - :meth:`reject_embargo_invite`
        - :meth:`terminate_active_embargo`
        - :meth:`record_participant_consent` (no EM transition; no mode param)
    """

    def __init__(self, persistence: CasePersistence) -> None:
        self._persistence = persistence

    # ------------------------------------------------------------------
    # Public operations
    # ------------------------------------------------------------------

    def propose_embargo(
        self,
        *,
        case_id: str,
        embargo_id: str,
        actor_id: str | None = None,
        transition_mode: TransitionMode = TransitionMode.STRICT,
    ) -> EmbargoLifecycleResult:
        """Propose or counter-propose an embargo on a case.

        Valid EM transitions (STRICT mode):
            - ``NO_EMBARGO → PROPOSED``  (initial proposal)
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

        Returns:
            :class:`EmbargoLifecycleResult` describing what changed.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case.
            VultronInvalidStateTransitionError: If the current EM state does
                not allow a PROPOSE transition (``STRICT`` mode only), or if
                any of P/X/A is set on the case (``STRICT`` mode only,
                per EMB-01-002).
        """
        # Load and validate case
        case = self._persistence.read(case_id)
        if not isinstance(case, VulnerabilityCase):
            raise VultronNotFoundError("VulnerabilityCase", case_id)

        em_before = EM(case.current_status.em_state)

        if transition_mode == TransitionMode.STRICT:
            self._assert_pxa_embargo_eligible(
                CS_pxa(case.current_status.pxa_state),
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

        # Mutate case — track whether anything actually changed
        case_mutated = False

        if em_after != em_before:
            case.current_status.em_state = em_after
            case_mutated = True

        # Idempotent append: normalise existing refs to strings before checking
        existing_embargo_ids = {
            _as_id(e) for e in case.proposed_embargoes if _as_id(e) is not None
        }
        if embargo_id not in existing_embargo_ids:
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
        case = self._persistence.read(case_id)
        if not isinstance(case, VulnerabilityCase):
            raise VultronNotFoundError("VulnerabilityCase", case_id)

        em_before = EM(case.current_status.em_state)
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
                    CS_pxa(case.current_status.pxa_state),
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
            # Sync em_state and active_embargo whenever owner accepted
            if em_after != em_before:
                case.current_status.em_state = em_after
                case_mutated = True
            # Sync active_embargo independently: handle OBSERVED mode where
            # em_after == em_before == ACTIVE but active_embargo points elsewhere
            if active_embargo_id != embargo_id:
                case.set_embargo(embargo_id)
                case_mutated = True
                case_embargo_changed = True

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
    ) -> EmbargoLifecycleResult:
        """Reject an embargo proposal or revision on a case.

        If *actor_id* is the case owner, drives the EM state machine:
            - ``PROPOSED → NO_EMBARGO``  (initial proposal rejected)
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

        Returns:
            :class:`EmbargoLifecycleResult` describing what changed.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case.
            VultronInvalidStateTransitionError: If the EM state does not allow
                a REJECT transition (``STRICT`` mode, owner only), or if the
                case is in REVISE state with P/X/A set (``STRICT`` mode only,
                per EMB-04-002 — use terminate_active_embargo instead).
        """
        case = self._persistence.read(case_id)
        if not isinstance(case, VulnerabilityCase):
            raise VultronNotFoundError("VulnerabilityCase", case_id)

        em_before = EM(case.current_status.em_state)
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
                    CS_pxa(case.current_status.pxa_state),
                    case_id,
                    "reject embargo revision (use terminate_active_embargo when P/X/A is set)",
                )
            # OBSERVED fallback: REVISE reject → ACTIVE; otherwise → NO_EMBARGO
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
                case.current_status.em_state = em_after
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

    def terminate_active_embargo(
        self,
        *,
        case_id: str,
        actor_id: str | None = None,
        transition_mode: TransitionMode = TransitionMode.STRICT,
    ) -> EmbargoLifecycleResult:
        """Terminate the active embargo on a case.

        Drives ``ACTIVE → EXITED`` (or ``REVISE → EXITED``), clears
        ``case.active_embargo``, and resets all participants' PEC state to
        ``NO_EMBARGO`` via :meth:`_cascade_pec_reset`.

        Args:
            case_id: ID of the ``VulnerabilityCase`` to update.
            actor_id: Optional ID of the terminating actor (logging only).
            transition_mode: ``STRICT`` (default) or ``OBSERVED``.

        Returns:
            :class:`EmbargoLifecycleResult` describing what changed.
            ``pec_reset`` is always ``True`` when this method succeeds.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case.
            VultronInvalidStateTransitionError: In ``STRICT`` mode, if the EM
                state does not allow TERMINATE or ``active_embargo`` is
                ``None``.
        """
        case = self._persistence.read(case_id)
        if not isinstance(case, VulnerabilityCase):
            raise VultronNotFoundError("VulnerabilityCase", case_id)

        em_before = EM(case.current_status.em_state)

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

        case.current_status.em_state = em_after
        case.active_embargo = None

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

    def record_participant_consent(
        self,
        *,
        case_id: str,
        actor_id: str,
        pec_trigger: PEC_Trigger,
        embargo_id: str | None = None,
    ) -> EmbargoLifecycleResult:
        """Apply a PEC trigger to a single participant without changing EM state.

        Useful for recording individual consent signals (invite, accept,
        decline) that do not drive the shared EM machine.  When *pec_trigger*
        is ``ACCEPT`` and *embargo_id* is provided, the ID is added
        idempotently to ``accepted_embargo_ids``; when it is ``DECLINE``,
        the ID is removed.

        Args:
            case_id: ID of the ``VulnerabilityCase`` that owns the participant.
            actor_id: ID of the actor whose participant record to update.
            pec_trigger: The PEC trigger to apply.
            embargo_id: Optional ID of the relevant ``EmbargoEvent``; used
                to maintain ``accepted_embargo_ids`` on ACCEPT/DECLINE.

        Returns:
            :class:`EmbargoLifecycleResult` with ``em_before == em_after``
            and ``case_changed == False`` (participant records are updated
            separately).  ``participant_changes`` records the PEC state change
            when the transition was valid.
        """
        case = self._persistence.read(case_id)
        if not isinstance(case, VulnerabilityCase):
            raise VultronNotFoundError("VulnerabilityCase", case_id)

        em_state = EM(case.current_status.em_state)

        participant_id = case.actor_participant_index.get(actor_id)
        if not participant_id:
            logger.warning(
                "record_participant_consent: actor '%s' has no participant"
                " record in case '%s' — skipping",
                actor_id,
                case_id,
            )
            return EmbargoLifecycleResult(
                em_before=em_state,
                em_after=em_state,
                case_changed=False,
                case_embargo_changed=False,
                pec_reset=False,
            )

        participant = self._persistence.read(participant_id)
        if not isinstance(participant, CaseParticipant):
            return EmbargoLifecycleResult(
                em_before=em_state,
                em_after=em_state,
                case_changed=False,
                case_embargo_changed=False,
                pec_reset=False,
            )

        pec_before = participant.embargo_consent_state
        current_pec = PEC(pec_before)
        changed = False

        new_pec = apply_pec_trigger(current_pec, pec_trigger)
        if new_pec != current_pec:
            participant.embargo_consent_state = new_pec
            changed = True

        if pec_trigger == PEC_Trigger.ACCEPT and embargo_id is not None:
            if embargo_id not in participant.accepted_embargo_ids:
                participant.accepted_embargo_ids = list(
                    dict.fromkeys(
                        participant.accepted_embargo_ids + [embargo_id]
                    )
                )
                changed = True
        elif pec_trigger == PEC_Trigger.DECLINE and embargo_id is not None:
            if embargo_id in participant.accepted_embargo_ids:
                participant.accepted_embargo_ids.remove(embargo_id)
                changed = True

        if changed:
            self._persistence.save(participant)

        participant_changes = (
            [
                ParticipantPECChange(
                    participant_id=participant_id,
                    pec_before=pec_before,
                    pec_after=participant.embargo_consent_state,
                )
            ]
            if changed
            else []
        )

        logger.info(
            "Recorded consent for actor '%s' on case '%s' (PEC %s → %s"
            " via %s)",
            actor_id,
            case_id,
            pec_before,
            participant.embargo_consent_state,
            pec_trigger,
        )

        return EmbargoLifecycleResult(
            em_before=em_state,
            em_after=em_state,
            case_changed=False,
            case_embargo_changed=False,
            pec_reset=False,
            participant_changes=participant_changes,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _assert_pxa_embargo_eligible(
        pxa_state: CS_pxa,
        case_id: str,
        operation: str,
    ) -> None:
        """Raise if the case is no longer embargo-eligible due to P/X/A.

        Per EMB-01-002 and EMB-02-002: once any of P, X, or A is set
        (i.e. ``pxa_state != CS_pxa.pxa``), no new embargo may be proposed
        or accepted.  This guard is only applied in STRICT mode.

        Raises:
            VultronInvalidStateTransitionError: When ``pxa_state != CS_pxa.pxa``.
        """
        if pxa_state != CS_pxa.pxa:
            raise VultronInvalidStateTransitionError(
                f"Cannot {operation} on case '{case_id}': public awareness,"
                f" exploit publication, or attack observation is set"
                f" (pxa_state='{pxa_state.name}')."
            )

    def _drive_em_transition(
        self,
        *,
        case_id: str,
        em_before: EM,
        trigger: EM_Trigger,
        transition_mode: TransitionMode,
        fallback_dest: EM,
        actor_id: str | None = None,
    ) -> EM:
        """Drive an EM state-machine transition.

        In ``STRICT`` mode raises
        :exc:`~vultron.errors.VultronInvalidStateTransitionError` on failure.
        In ``OBSERVED`` mode logs a warning and returns *fallback_dest*
        instead of raising, enabling state-sync with a remote party.
        """
        adapter = EMAdapter(em_before)
        em_machine = create_em_machine()
        em_machine.add_model(adapter, initial=em_before)
        try:
            getattr(adapter, trigger)()
            return EM(adapter.state)
        except MachineError:
            if transition_mode == TransitionMode.STRICT:
                logger.warning(
                    "Invalid EM transition: actor '%s' cannot %s on case"
                    " '%s' (EM state '%s').",
                    actor_id,
                    trigger,
                    case_id,
                    em_before,
                )
                raise VultronInvalidStateTransitionError(
                    f"Cannot apply '{trigger}' to embargo: case '{case_id}'"
                    f" EM state '{em_before}' does not allow this transition."
                )
            else:
                logger.warning(
                    "OBSERVED mode: EM transition '%s' (trigger '%s') failed"
                    " for case '%s' — forcing state-sync to '%s'",
                    em_before,
                    trigger,
                    case_id,
                    fallback_dest,
                )
                return fallback_dest

    def _record_actor_pec_acceptance(
        self, case: Any, actor_id: str, embargo_id: str
    ) -> list[ParticipantPECChange]:
        """Update a participant's PEC to SIGNATORY and track the embargo ID.

        Idempotent: if the participant is already ``SIGNATORY``, only
        ``accepted_embargo_ids`` is updated (if needed).
        """
        participant_id = case.actor_participant_index.get(actor_id)
        if not participant_id:
            logger.warning(
                "Actor '%s' has no CaseParticipant in case '%s'"
                " — cannot record embargo acceptance",
                actor_id,
                _as_id(case),
            )
            return []

        participant = self._persistence.read(participant_id)
        if not isinstance(participant, CaseParticipant):
            return []

        pec_before = participant.embargo_consent_state
        current_pec = PEC(pec_before)
        changed = False

        if current_pec != PEC.SIGNATORY:
            participant.embargo_consent_state = apply_pec_trigger(
                current_pec, PEC_Trigger.ACCEPT
            )
            changed = True

        if embargo_id not in participant.accepted_embargo_ids:
            participant.accepted_embargo_ids = list(
                dict.fromkeys(participant.accepted_embargo_ids + [embargo_id])
            )
            changed = True

        if changed:
            self._persistence.save(participant)

        return (
            [
                ParticipantPECChange(
                    participant_id=participant_id,
                    pec_before=pec_before,
                    pec_after=participant.embargo_consent_state,
                )
            ]
            if changed
            else []
        )

    def _record_actor_pec_rejection(
        self, case: Any, actor_id: str, embargo_id: str
    ) -> list[ParticipantPECChange]:
        """Update a participant's PEC to DECLINED and remove the embargo ID.

        Idempotent: if the participant is already ``DECLINED``, only
        ``accepted_embargo_ids`` is updated (if needed).
        """
        participant_id = case.actor_participant_index.get(actor_id)
        if not participant_id:
            logger.warning(
                "Actor '%s' has no CaseParticipant in case '%s'"
                " — cannot record embargo rejection",
                actor_id,
                _as_id(case),
            )
            return []

        participant = self._persistence.read(participant_id)
        if not isinstance(participant, CaseParticipant):
            return []

        pec_before = participant.embargo_consent_state
        current_pec = PEC(pec_before)
        changed = False

        if current_pec != PEC.DECLINED:
            participant.embargo_consent_state = apply_pec_trigger(
                current_pec, PEC_Trigger.DECLINE
            )
            changed = True

        if embargo_id in participant.accepted_embargo_ids:
            participant.accepted_embargo_ids.remove(embargo_id)
            changed = True

        if changed:
            self._persistence.save(participant)

        return (
            [
                ParticipantPECChange(
                    participant_id=participant_id,
                    pec_before=pec_before,
                    pec_after=participant.embargo_consent_state,
                )
            ]
            if changed
            else []
        )

    def _cascade_pec_reset(self, case: Any) -> list[ParticipantPECChange]:
        """Reset all participants' PEC state to NO_EMBARGO.

        Called when an embargo is terminated.  Returns a list of
        :class:`ParticipantPECChange` for every participant that was updated.
        """
        changes: list[ParticipantPECChange] = []
        for entry in case.case_participants:
            participant_id = _as_id(entry)
            if participant_id is None:
                continue
            participant = self._persistence.read(participant_id)
            if not isinstance(participant, CaseParticipant):
                continue
            if participant.embargo_consent_state == PEC.NO_EMBARGO.value:
                continue
            pec_before = participant.embargo_consent_state
            participant.embargo_consent_state = apply_pec_trigger(
                PEC(pec_before), PEC_Trigger.RESET
            )
            self._persistence.save(participant)
            changes.append(
                ParticipantPECChange(
                    participant_id=participant_id,
                    pec_before=pec_before,
                    pec_after=participant.embargo_consent_state,
                )
            )
        return changes

    def _cascade_pec_revise(self, case: Any) -> list[ParticipantPECChange]:
        """Transition all SIGNATORY participants to LAPSED.

        Called when an embargo transitions to REVISE state, meaning the
        embargo terms are being renegotiated.  Existing signatories temporarily
        lapse until they accept the revised terms.

        Returns a list of :class:`ParticipantPECChange` records for each
        participant whose PEC state was updated.
        """
        changes: list[ParticipantPECChange] = []
        for entry in case.case_participants:
            participant_id = _as_id(entry)
            if participant_id is None:
                continue
            participant = self._persistence.read(participant_id)
            if not isinstance(participant, CaseParticipant):
                continue
            if participant.embargo_consent_state == PEC.SIGNATORY.value:
                pec_before = participant.embargo_consent_state
                participant.embargo_consent_state = apply_pec_trigger(
                    PEC.SIGNATORY, PEC_Trigger.REVISE
                )
                self._persistence.save(participant)
                changes.append(
                    ParticipantPECChange(
                        participant_id=participant_id,
                        pec_before=pec_before,
                        pec_after=participant.embargo_consent_state,
                    )
                )
        return changes
