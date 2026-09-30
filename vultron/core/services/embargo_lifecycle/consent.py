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

"""Operations that leave the EM state alone.

Per-participant consent bookkeeping (``record_participant_consent``,
``record_embargo_rejection``), lazy RSVP-deadline enforcement
(``detect_and_apply_lapse``, EMB-17) and the public eligibility check
callers use before creating anything (``assert_embargo_eligible``,
EP-04-008).
"""

import logging
from datetime import datetime

from vultron.core.models._helpers import _as_id
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.services.embargo_lifecycle.pec import _PecEffectsMixin
from vultron.core.services.embargo_lifecycle.results import (
    EmbargoLifecycleResult,
    ParticipantPECChange,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    PEC,
    PEC_Trigger,
)

logger = logging.getLogger(__name__)


def _unchanged(
    em_state: EM,
    *,
    participant_changes: list[ParticipantPECChange] | None = None,
    is_lapsed: bool = False,
) -> EmbargoLifecycleResult:
    """A result for an operation that moved neither EM state nor the case."""
    return EmbargoLifecycleResult(
        em_before=em_state,
        em_after=em_state,
        case_changed=False,
        case_embargo_changed=False,
        pec_reset=False,
        participant_changes=participant_changes or [],
        is_lapsed=is_lapsed,
    )


class _ConsentOperationsMixin(_PecEffectsMixin):
    """Consent, lapse and eligibility operations with no EM transition."""

    def record_embargo_rejection(
        self,
        *,
        case_id: str,
        actor_id: str,
        embargo_id: str,
    ) -> EmbargoLifecycleResult:
        """Record *actor_id*'s rejection of *embargo_id* without moving EM.

        The consent half of :meth:`reject_embargo_invite`, for a receiver
        that records what a participant answered but does not decide the
        proposal in this call — the received ``Reject(Invite(EmbargoEvent))``
        tree.  Applies the MSM-07-004 rule by which embargo the Reject names
        (ADR-0093): the case's *active* embargo is consent withdrawal —
        ``DECLINE`` from any state, ``SIGNATORY`` included; a *proposed*
        embargo is a refusal of those terms — the id leaves the actor's
        ``accepted_embargo_ids`` and ``DECLINE`` applies only to an actor not
        yet ``SIGNATORY``.  The owner's EJ (the owner refusing a proposed
        revision while an embargo is in force) changes nobody's record.

        Args:
            case_id: ID of the ``VulnerabilityCase`` that owns the participant.
            actor_id: ID of the rejecting actor.
            embargo_id: ID of the ``EmbargoEvent`` the Reject names.

        Returns:
            :class:`EmbargoLifecycleResult` with ``em_before == em_after`` and
            ``case_changed == False``; ``participant_changes`` carries the
            actor's PEC state change, if any.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case.
            VultronValidationError: If *embargo_id* is neither the active
                embargo nor an open proposal of the case.
        """
        case = self._read_case(case_id)
        em_state = case.current_status.em.state

        is_owner = _as_id(case.attributed_to) == actor_id
        is_active = self._assert_rejectable(case, embargo_id)
        if is_owner and not is_active and case.active_embargo_id is not None:
            # EJ: the owner keeps the embargo in force (MSM-07-004).
            logger.info(
                "Owner '%s' rejected proposed revision '%s' on case '%s';"
                " no consent record changes",
                actor_id,
                embargo_id,
                case_id,
            )
            return _unchanged(em_state)

        participant_changes = self._record_actor_pec_rejection(
            case, actor_id, embargo_id, withdrawal=is_active
        )
        logger.info(
            "Recorded rejection of embargo '%s' by actor '%s' on case '%s'"
            " (%s; %d PEC state change(s))",
            embargo_id,
            actor_id,
            case_id,
            "active embargo — withdrawal" if is_active else "proposed terms",
            len(participant_changes),
        )
        return _unchanged(em_state, participant_changes=participant_changes)

    def record_participant_consent(
        self,
        *,
        case_id: str,
        actor_id: str,
        pec_trigger: PEC_Trigger,
        embargo_id: str | None = None,
        em_before: EM | None = None,
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
            em_before: When provided by the caller (e.g. by a BT node that
                already read the case), this value is used directly instead of
                reading it from the case.

        Returns:
            :class:`EmbargoLifecycleResult` with ``em_before == em_after``
            and ``case_changed == False`` (participant records are updated
            separately).  ``participant_changes`` records the PEC state change
            when the transition was valid.
        """
        case = self._read_case(case_id)

        em_state = (
            em_before
            if em_before is not None
            else case.current_status.em.state
        )

        participant_id = case.actor_participant_index.get(actor_id)
        if not participant_id:
            logger.warning(
                "record_participant_consent: actor '%s' has no participant"
                " record in case '%s' — skipping",
                actor_id,
                case_id,
            )
            return _unchanged(em_state)

        participant = self._persistence.read(participant_id)
        if not isinstance(participant, CaseParticipant):
            return _unchanged(em_state)

        pec_before = participant.embargo_consent_state
        changed = False

        participant.apply_pec_transition(pec_trigger)
        if participant.embargo_consent_state != pec_before:
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

        return _unchanged(em_state, participant_changes=participant_changes)

    def detect_and_apply_lapse(
        self,
        *,
        case_id: str,
        actor_id: str,
        now: datetime,
    ) -> EmbargoLifecycleResult:
        """Lazily enforce RSVP deadline: apply DECLINE if invite has lapsed.

        Reads the participant record for *actor_id* in *case_id*.  If the
        participant is in ``INVITED`` state and ``invite_rsvp_deadline`` is
        set and ``now >= invite_rsvp_deadline``, applies ``PEC_Trigger.DECLINE``
        and returns a result with ``is_lapsed=True``.

        Idempotent: if the participant is already ``DECLINED`` (or any state
        other than ``INVITED``), no PEC transition is applied.  The result
        still carries ``is_lapsed=True`` when the deadline has passed, so the
        caller can branch on whether the invite window closed without
        re-deriving it.

        Args:
            case_id: ID of the VulnerabilityCase.
            actor_id: ID of the actor whose participant record to check.
            now: Current UTC datetime used for deadline comparison.

        Returns:
            :class:`EmbargoLifecycleResult` with ``is_lapsed`` reflecting
            whether the deadline has passed.
        """
        case = self._read_case(case_id)

        em_state = case.current_status.em.state

        participant_id = case.actor_participant_index.get(actor_id)
        if not participant_id:
            logger.debug(
                "detect_and_apply_lapse: actor '%s' has no participant"
                " record in case '%s' — skipping",
                actor_id,
                case_id,
            )
            return _unchanged(em_state)

        participant = self._persistence.read(participant_id)
        if not isinstance(participant, CaseParticipant):
            return _unchanged(em_state)

        deadline = participant.invite_rsvp_deadline
        is_lapsed = deadline is not None and now >= deadline

        if not is_lapsed:
            return _unchanged(em_state)

        # Deadline has passed — apply DECLINE if still in INVITED state.
        # Idempotent: DECLINED and other terminal states are left unchanged.
        participant_changes: list[ParticipantPECChange] = []
        if participant.embargo_consent_state == PEC.INVITED.value:
            pec_before = participant.embargo_consent_state
            participant.apply_pec_transition(PEC_Trigger.DECLINE)
            self._persistence.save(participant)
            participant_changes.append(
                ParticipantPECChange(
                    participant_id=participant_id,
                    pec_before=pec_before,
                    pec_after=participant.embargo_consent_state,
                )
            )
            logger.info(
                "Invite lapsed for actor '%s' on case '%s'"
                " (deadline=%s, PEC INVITED → DECLINED)",
                actor_id,
                case_id,
                deadline,
            )

        # A SIGNATORY participant has already accepted; a stale deadline is not
        # a real lapse.  Only DECLINED (just-lapsed or already-declined) triggers
        # the EMB-17 late-Accept routing in the caller.
        is_lapsed = participant.embargo_consent_state != PEC.SIGNATORY.value

        return _unchanged(
            em_state,
            participant_changes=participant_changes,
            is_lapsed=is_lapsed,
        )

    def assert_embargo_eligible(self, *, case_id: str, operation: str) -> None:
        """Raise unless the case is still embargo-eligible (P/X/A all clear).

        The public form of the guard ``propose_embargo`` applies in STRICT
        mode, for callers that must decide *before* creating anything — the
        default embargo at case creation is not created at all for an
        ineligible case (EP-04-008).

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case.
            VultronInvalidStateTransitionError: When any of P/X/A is set.
        """
        case = self._read_case(case_id)
        self._assert_pxa_embargo_eligible(
            case.current_status.pxa.state, case_id, operation
        )
