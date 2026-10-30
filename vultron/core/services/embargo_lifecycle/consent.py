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
``record_embargo_rejection``, ``record_embargo_withdrawal``,
``record_embargo_invite``) and the public eligibility check callers use
before creating anything (``assert_embargo_eligible``, EP-04-008).  Lazy
RSVP-deadline enforcement (EMB-17) is in :mod:`.expiry`.
"""

import logging
from datetime import datetime

from vultron.core.services.embargo_lifecycle.pec import (
    _consent_change,
    _PecEffectsMixin,
)
from vultron.core.services.embargo_lifecycle.results import (
    EmbargoLifecycleResult,
    ParticipantConsentChange,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    PEC_Trigger,
)

logger = logging.getLogger(__name__)


def _unchanged(
    em_state: EM,
    *,
    participant_changes: list[ParticipantConsentChange] | None = None,
    is_expired: bool = False,
) -> EmbargoLifecycleResult:
    """A result for an operation that moved neither EM state nor the case."""
    return EmbargoLifecycleResult(
        em_before=em_state,
        em_after=em_state,
        case_changed=False,
        case_embargo_changed=False,
        participant_changes=participant_changes or [],
        is_expired=is_expired,
    )


class _ConsentOperationsMixin(_PecEffectsMixin):
    """Consent and eligibility operations with no EM transition."""

    def record_embargo_invite(
        self,
        *,
        case_id: str,
        invitee_id: str,
        embargo_id: str,
        rsvp_deadline: datetime | None = None,
    ) -> EmbargoLifecycleResult:
        """Record that *invitee_id* was invited to *embargo_id*, without moving EM.

        Applies PEC ``INVITE`` to the invitee's row for *embargo_id* where it
        is legal — from ``UNINVITED``, ``DECLINED`` or ``TIMED_OUT`` — so an
        ``AGREED`` row stays agreed.  The row belongs to *embargo_id* alone: a
        signatory asked about a revision has its revision row invited and
        keeps its row for the embargo in force, so its binding is untouched
        (EP-09-004, ADR-0122).  *rsvp_deadline* goes on the invited row
        (CM-28-013); an Invite sent again to a row still ``INVITED`` moves no
        state but replaces the row's deadline, so a passed one cannot time out
        the fresh invitation.  A row whose register entry is final is frozen
        and records nothing.  The CASE_MANAGER calls this as it relays the
        Invite; a replica calls it as it replays the relay's ledger entry
        (EP-09-007), so both stores apply one rule.

        Args:
            case_id: ID of the ``VulnerabilityCase`` that owns the participant.
            invitee_id: ID of the invited actor.
            embargo_id: ID of the ``EmbargoEvent`` the Invite names.
            rsvp_deadline: The Invite's RSVP deadline, when it carries one.

        Returns:
            :class:`EmbargoLifecycleResult` with ``em_before == em_after`` and
            ``case_changed == False``; ``participant_changes`` carries the
            invitee's row change, empty when ``INVITE`` did not apply.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case,
                *invitee_id* has no participant record on it, or the register
                has no entry for *embargo_id*.
        """
        case = self._read_case(case_id)
        em_state = case.em_state
        participant_id, participant = self._require_participant(
            case, invitee_id
        )
        entry_status = case.embargo_register_status(embargo_id)

        before = participant.consent_for(embargo_id)
        moved = participant.apply_pec_transition_if_legal(
            embargo_id,
            PEC_Trigger.INVITE,
            entry_status=entry_status,
            rsvp_deadline=rsvp_deadline,
        )
        restamped = not moved and participant.restamp_rsvp_deadline(
            embargo_id, rsvp_deadline, entry_status=entry_status
        )
        if moved or restamped:
            self._persistence.save(participant)

        changes = (
            [_consent_change(participant_id, embargo_id, before, participant)]
            if moved
            else []
        )
        logger.info(
            "Recorded embargo invite of '%s' to embargo '%s' on case '%s'"
            " (consent %s → %s, RSVP deadline %s)",
            invitee_id,
            embargo_id,
            case_id,
            before,
            participant.consent_for(embargo_id),
            participant.rsvp_deadline_for(embargo_id),
        )
        return _unchanged(em_state, participant_changes=changes)

    def record_embargo_rejection(
        self,
        *,
        case_id: str,
        actor_id: str,
        embargo_id: str,
    ) -> EmbargoLifecycleResult:
        """Record *actor_id*'s rejection of *embargo_id* without moving EM.

        The effect of a ``Reject(Invite(EmbargoEvent))``, which is always the
        sender's own consent, the case owner's included (ADR-0122).  Applies
        the MSM-07-004 rule: the actor's row for the named embargo becomes
        ``DECLINED`` and no register entry moves (MSM-07-013).  Refusing a
        *proposed* embargo leaves the actor's row for the embargo in force
        untouched (MSM-07-015); a Reject of the embargo *in force* answers it
        from a row that has not agreed to it.  A Reject of the embargo in force
        from an ``AGREED`` row is not a withdrawal and is refused (MSM-07-014):
        withdrawal is :meth:`record_embargo_withdrawal` (MSM-07-010).  The owner's decision
        on a proposal is :meth:`reject_embargo_proposal`.

        Args:
            case_id: ID of the ``VulnerabilityCase`` that owns the participant.
            actor_id: ID of the rejecting actor.
            embargo_id: ID of the ``EmbargoEvent`` the Reject names.

        Returns:
            :class:`EmbargoLifecycleResult` with ``em_before == em_after`` and
            ``case_changed == False``; ``participant_changes`` carries the
            actor's row change, if any.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case.
            VultronValidationError: If *embargo_id* is neither the active
                embargo nor an open proposal of the case, or the Reject names
                the embargo in force and the actor's row for it is
                ``AGREED``.
        """
        case = self._read_case(case_id)
        em_state = case.em_state
        self._assert_rejectable(case, embargo_id)
        participant_changes = self._rejection_consent(
            case, actor_id, embargo_id
        )
        logger.info(
            "Recorded rejection of embargo '%s' by actor '%s' on case '%s'"
            " (%d consent row change(s))",
            embargo_id,
            actor_id,
            case_id,
            len(participant_changes),
        )
        return _unchanged(em_state, participant_changes=participant_changes)

    def record_embargo_withdrawal(
        self,
        *,
        case_id: str,
        actor_id: str,
        embargo_id: str,
    ) -> EmbargoLifecycleResult:
        """Record *actor_id*'s withdrawal from the embargo in force, moving no EM.

        The effect of a ``Leave(EmbargoEvent)`` (MSM-07-010, ADR-0122): the
        actor's ``AGREED`` row for the active embargo becomes ``DECLINED``,
        and so does every open proposal's row it had agreed to, since each
        open proposal is a revision of the embargo it left (EP-08-004).  No
        register entry moves, so the embargo stays in force for everyone
        else; the actor is no longer bound by it (VP-13-017).

        Args:
            case_id: ID of the ``VulnerabilityCase`` that owns the participant.
            actor_id: ID of the withdrawing actor.
            embargo_id: ID of the ``EmbargoEvent`` the Leave names.

        Returns:
            :class:`EmbargoLifecycleResult` with ``em_before == em_after`` and
            ``case_changed == False``; ``participant_changes`` carries every
            row the withdrawal declined.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case.
            VultronValidationError: If *embargo_id* is not the embargo in
                force, the actor has no participant record or its row for the
                embargo is not ``AGREED``, or the actor is the case owner.
        """
        case = self._read_case(case_id)
        em_state = case.em_state
        participant_changes = self._withdrawal_consent(
            case, actor_id, embargo_id
        )
        logger.info(
            "Recorded withdrawal of actor '%s' from embargo '%s' on case '%s'"
            " (%d consent row change(s), MSM-07-010)",
            actor_id,
            embargo_id,
            case_id,
            len(participant_changes),
        )
        return _unchanged(em_state, participant_changes=participant_changes)

    def record_participant_consent(
        self,
        *,
        case_id: str,
        actor_id: str,
        embargo_id: str,
        pec_trigger: PEC_Trigger,
    ) -> EmbargoLifecycleResult:
        """Apply a PEC trigger to one participant's row without changing EM state.

        Useful for recording individual consent signals (invite, agree,
        decline) that change no embargo register entry.  The trigger is
        applied to the row for *embargo_id*; an illegal trigger, or one on a
        row whose register entry is final, raises (CM-18-009, ADR-0122).

        Args:
            case_id: ID of the ``VulnerabilityCase`` that owns the participant.
            actor_id: ID of the actor whose participant record to update.
            embargo_id: ID of the ``EmbargoEvent`` whose row the trigger moves.
            pec_trigger: The PEC trigger to apply.

        Returns:
            :class:`EmbargoLifecycleResult` with ``em_before == em_after``
            and ``case_changed == False`` (participant records are updated
            separately).  ``participant_changes`` records the row change when
            the row moved.
        """
        case = self._read_case(case_id)

        em_state = case.em_state

        resolved = self._find_participant(case, actor_id)
        if resolved is None:
            logger.warning(
                "record_participant_consent: actor '%s' has no participant"
                " record in case '%s' — skipping",
                actor_id,
                case_id,
            )
            return _unchanged(em_state)
        participant_id, participant = resolved

        before = participant.consent_for(embargo_id)
        participant.apply_pec_transition(
            embargo_id,
            pec_trigger,
            entry_status=case.embargo_register_status(embargo_id),
        )
        self._persistence.save(participant)

        logger.info(
            "Recorded consent for actor '%s' on case '%s' (embargo '%s',"
            " %s → %s via %s)",
            actor_id,
            case_id,
            embargo_id,
            before,
            participant.consent_for(embargo_id),
            pec_trigger,
        )

        return _unchanged(
            em_state,
            participant_changes=[
                _consent_change(
                    participant_id, embargo_id, before, participant
                )
            ],
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
