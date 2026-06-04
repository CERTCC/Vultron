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
This issue: https://github.com/CERTCC/Vultron/issues/746
"""

import logging
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field
from transitions import MachineError

from vultron.core.models.protocols import is_case_model, is_participant_model
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.states.em import EM, EM_Trigger, EMAdapter, create_em_machine
from vultron.core.states.participant_embargo_consent import (
    PEC,
    PEC_Trigger,
    apply_pec_trigger,
)
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronNotFoundError,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Private utility
# ---------------------------------------------------------------------------


def _as_id(obj: Any) -> str | None:
    """Return the string ID of *obj*, whether it is a str or an AS2 object.

    Mirrors the same utility in ``vultron.core.use_cases._helpers``.
    TODO: move both copies to a neutral ``vultron.core.utils`` module (#538).
    """
    if obj is None:
        return None
    id_ = getattr(obj, "id_", None)
    if isinstance(id_, str):
        return id_
    return str(obj)


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

    Currently implemented (this issue #746):
        - :meth:`propose_embargo` — ``STRICT`` mode only

    Deferred to #747:
        - :meth:`accept_embargo_invite`
        - :meth:`reject_embargo_invite`
        - :meth:`terminate_active_embargo`
        - :meth:`record_participant_consent`
        - ``OBSERVED`` mode across all operations
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
                ``OBSERVED`` is not yet implemented (tracked in #747).

        Returns:
            :class:`EmbargoLifecycleResult` describing what changed.

        Raises:
            NotImplementedError: If *transition_mode* is ``OBSERVED``
                (deferred to #747).
            VultronNotFoundError: If *case_id* does not resolve to a case.
            VultronInvalidStateTransitionError: If the current EM state does
                not allow a PROPOSE transition (``STRICT`` mode only).
        """
        if transition_mode == TransitionMode.OBSERVED:
            raise NotImplementedError(
                "OBSERVED mode for propose_embargo is not yet implemented; "
                "tracked in https://github.com/CERTCC/Vultron/issues/747"
            )

        # Load and validate case
        case = self._persistence.read(case_id)
        if not is_case_model(case):
            raise VultronNotFoundError("VulnerabilityCase", case_id)

        em_before = EM(case.current_status.em_state)

        # Drive EM state machine
        adapter = EMAdapter(em_before)
        em_machine = create_em_machine()
        em_machine.add_model(adapter, initial=em_before)

        try:
            getattr(adapter, EM_Trigger.PROPOSE)()
        except MachineError:
            logger.warning(
                "Invalid EM transition: actor '%s' cannot PROPOSE on case"
                " '%s' (EM state '%s').",
                actor_id,
                case_id,
                em_before,
            )
            raise VultronInvalidStateTransitionError(
                f"Cannot propose embargo: case '{case_id}' EM state"
                f" '{em_before}' does not allow a PROPOSE transition."
            )

        em_after = EM(adapter.state)

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

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

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
            if not is_participant_model(participant):
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
