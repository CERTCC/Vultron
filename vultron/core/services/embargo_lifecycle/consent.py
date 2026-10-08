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
``record_embargo_rejection``, ``record_embargo_invite``), lazy RSVP-deadline enforcement
(``assess_invite_expiry``, ``record_invite_expiry``,
``detect_and_apply_expiry``, EMB-17) and the public eligibility check
callers use before creating anything (``assert_embargo_eligible``,
EP-04-008).
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
from vultron.core.states.embargo_register import FINAL_REGISTER_STATUSES
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
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
    """Consent, invite-expiry and eligibility operations with no EM transition."""

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

        The consent half of :meth:`reject_embargo_invite`, for a receiver
        that records what a participant answered but does not decide the
        proposal in this call — the received ``Reject(Invite(EmbargoEvent))``
        tree.  Applies the MSM-07-004 rule by which embargo the Reject names
        (ADR-0093): the case's *active* embargo is consent withdrawal —
        the actor's row for it becomes ``DECLINED``, a signatory's included;
        a *proposed* embargo is a refusal of those terms — only that
        embargo's row becomes ``DECLINED``, and the actor's row for the
        embargo in force is untouched.  The owner's EJ (the owner refusing a proposed
        revision while an embargo is in force) changes nobody's record.

        Args:
            case_id: ID of the ``VulnerabilityCase`` that owns the participant.
            actor_id: ID of the rejecting actor.
            embargo_id: ID of the ``EmbargoEvent`` the Reject names.

        Returns:
            :class:`EmbargoLifecycleResult` with ``em_before == em_after`` and
            ``case_changed == False``; ``participant_changes`` carries the
            actor's row changes, if any.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case.
            VultronValidationError: If *embargo_id* is neither the active
                embargo nor an open proposal of the case.
        """
        case = self._read_case(case_id)
        em_state = case.em_state
        is_active = self._assert_rejectable(case, embargo_id)
        participant_changes = self._rejection_consent(
            case, actor_id, embargo_id, is_active=is_active
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

    def assess_invite_expiry(
        self,
        *,
        case_id: str,
        actor_id: str,
        embargo_id: str,
        now: datetime,
    ) -> tuple[bool, bool]:
        """Read-only check: has the invitation to *embargo_id* timed out?

        Returns a ``(is_expired, needs_apply)`` pair where:

        * ``is_expired`` — ``True`` when the invitation is closed — its
          deadline has passed, or the embargo's register entry is final (the
          terms are stale, EMB-17-003) — **and** the participant is not a
          signatory to the active embargo.  Used by EMB-17 routing.
        * ``needs_apply`` — ``True`` when the row for *embargo_id* is still
          ``INVITED`` **and** its deadline has passed.  When ``True``, the
          caller MUST call :meth:`record_invite_expiry` after committing the
          ledger entry (CLP-10-006).

        Only the row for *embargo_id* is read: an RSVP deadline belongs to
        one invitation (CM-28-001, CM-28-012), and the participant's other
        invitations keep their own.  This method makes **no writes**, so a
        BT node can assess the situation, the commit node can persist the
        ledger entry, and only then the effect node calls
        :meth:`record_invite_expiry` (guard → commit → effect, CLP-10-006,
        BT-06-006).

        Args:
            case_id: ID of the ``VulnerabilityCase``.
            actor_id: ID of the actor whose participant record to check.
            embargo_id: ID of the ``EmbargoEvent`` the invitation was for.
            now: Current UTC datetime used for deadline comparison.

        Returns:
            ``(is_expired, needs_apply)`` — both ``False`` when the actor has
            no participant record, the row has no deadline, or the deadline
            has not yet passed.
        """
        case = self._read_case(case_id)
        resolved = self._find_participant(case, actor_id)
        if resolved is None:
            return False, False
        _, participant = resolved
        is_expired = not participant.is_signatory(case.active_embargo_id)
        entry = case.embargo_register_entry(embargo_id)
        if entry is not None and entry.status in FINAL_REGISTER_STATUSES:
            # The terms were superseded, rejected, cancelled or terminated:
            # the invitation is closed whatever its deadline, and its row is
            # frozen, so there is nothing to time out (ADR-0122).  The
            # caller's EMB-17 routing answers with the current embargo.
            return is_expired, False
        deadline = participant.rsvp_deadline_for(embargo_id)
        if deadline is None or now < deadline:
            return False, False
        # Only an INVITED row carries a deadline (CM-28-013) and the entry is
        # open, so the row times out.
        return is_expired, True

    def record_invite_expiry(
        self,
        *,
        case_id: str,
        actor_id: str,
        embargo_id: str,
    ) -> EmbargoLifecycleResult:
        """Apply PEC ``TIME_OUT`` (``INVITED → TIMED_OUT``) after the commit.

        This is the **effect** half of the guard → commit → effect trio
        (CLP-10-006, BT-06-006).  The CASE_MANAGER calls it only after its
        expiry entry has been committed by
        :func:`~vultron.core.behaviors.sync.commit_tree.create_commit_log_entry_tree`,
        and a replica calls it as it replays that entry.  Only the row for
        *embargo_id* moves: the deadline that passed belongs to that one
        invitation (CM-28-001, CM-28-012).

        Idempotent: a row that is no longer ``INVITED`` (already
        ``TIMED_OUT``, or any other state), or whose register entry is final,
        is left as it is.  An actor with no participant record is logged and
        skipped.

        Args:
            case_id: ID of the ``VulnerabilityCase``.
            actor_id: ID of the actor whose invite timed out.
            embargo_id: ID of the ``EmbargoEvent`` the invitation was for.

        Returns:
            :class:`EmbargoLifecycleResult` with ``is_expired=True`` when
            ``TIME_OUT`` was applied, ``is_expired=False`` when the row had
            already left ``INVITED`` (idempotent call).
        """
        case = self._read_case(case_id)
        em_state = case.em_state
        resolved = self._find_participant(case, actor_id)
        if resolved is None:
            logger.debug(
                "record_invite_expiry: actor '%s' has no participant"
                " record in case '%s' — skipping",
                actor_id,
                case_id,
            )
            return _unchanged(em_state)
        participant_id, participant = resolved
        participant_changes = self._apply_where_legal(
            case, participant_id, participant, embargo_id, PEC_Trigger.TIME_OUT
        )
        if participant_changes:
            logger.info(
                "Invite to embargo '%s' timed out for actor '%s' on case '%s'"
                " (PEC INVITED → TIMED_OUT — recorded after commit)",
                embargo_id,
                actor_id,
                case_id,
            )
        return _unchanged(
            em_state,
            participant_changes=participant_changes,
            is_expired=bool(participant_changes),
        )

    def honour_late_accept(
        self,
        *,
        case_id: str,
        actor_id: str,
        embargo_id: str,
    ) -> EmbargoLifecycleResult:
        """Apply the honour decision: ``TIMED_OUT → AGREED`` (or ``DECLINED → INVITED → AGREED``).

        This is the **effect** of :data:`HONOUR_LATE_ACCEPT_EVENT_TYPE`
        (EMB-17-001, ADR-0118).  Called by the replica replay node
        :class:`~vultron.core.behaviors.embargo.nodes.expiry.ApplyHonourLateAcceptFromLedgerNode`
        **and** by the CASE_MANAGER's
        :class:`~vultron.core.behaviors.embargo.nodes.expiry.HonourLateAcceptNode`
        **after** the entry is committed (CLP-10-006).

        A participant whose row for *embargo_id* is ``DECLINED`` is first
        invited again (``DECLINED → INVITED``, since ``AGREE`` is not legal
        from ``DECLINED``), then the shared
        :meth:`~vultron.core.services.embargo_lifecycle.pec._PecEffectsMixin._record_actor_acceptance`
        applies ``AGREE`` to that row.

        Idempotent: a participant whose row is already ``AGREED`` is not
        changed.

        Args:
            case_id: ID of the ``VulnerabilityCase``.
            actor_id: ID of the honouring actor.
            embargo_id: ID of the active ``EmbargoEvent`` to agree to.

        Returns:
            :class:`EmbargoLifecycleResult` describing the PEC transitions.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case or
                *actor_id* has no participant record on it.
        """
        case = self._read_case(case_id)
        em_state = case.em_state
        participant_id, participant = self._require_participant(case, actor_id)

        participant_changes: list[ParticipantConsentChange] = []
        # DECLINED is not a legal AGREE source (CM-18-003); invite again first.
        if participant.consent_for(embargo_id) == EmbargoConsentState.DECLINED:
            participant_changes = self._apply_where_legal(
                case,
                participant_id,
                participant,
                embargo_id,
                PEC_Trigger.INVITE,
            )
            logger.info(
                "honour_late_accept: re-invited DECLINED actor '%s'"
                " on case '%s' before AGREE (DECLINED → INVITED)",
                actor_id,
                case_id,
            )

        accept_changes = self._record_actor_acceptance(
            case, actor_id, embargo_id
        )
        all_changes = participant_changes + accept_changes
        logger.info(
            "honour_late_accept: honoured late Accept for actor '%s'"
            " on case '%s' (embargo '%s', EMB-17-001;"
            " %d consent row change(s))",
            actor_id,
            case_id,
            embargo_id,
            len(all_changes),
        )
        return _unchanged(em_state, participant_changes=all_changes)

    def detect_and_apply_expiry(
        self,
        *,
        case_id: str,
        actor_id: str,
        embargo_id: str,
        now: datetime,
    ) -> EmbargoLifecycleResult:
        """Lazily enforce one invitation's RSVP deadline: apply ``TIME_OUT`` if it passed.

        Reads the row for *embargo_id* on *actor_id*'s participant record.
        If the row is ``INVITED`` and its deadline has passed, applies
        ``PEC_Trigger.TIME_OUT`` (``INVITED → TIMED_OUT``).  A timed-out
        invitation is not a refusal, so ``DECLINE`` is never the timer path
        (ADR-0118, CM-18-002), and the participant's other invitations keep
        their own deadlines (CM-28-001).

        Idempotent: a row already ``TIMED_OUT`` (or in any state other than
        ``INVITED``) is not moved.  The result still carries
        ``is_expired=True`` when the deadline has passed and the participant
        is not a signatory to the active embargo, so the caller can branch on
        whether the invite window closed without re-deriving it.

        Args:
            case_id: ID of the VulnerabilityCase.
            actor_id: ID of the actor whose participant record to check.
            embargo_id: ID of the ``EmbargoEvent`` the invitation was for.
            now: Current UTC datetime used for deadline comparison.

        Returns:
            :class:`EmbargoLifecycleResult` with ``is_expired`` reflecting
            whether the deadline has passed.
        """
        case = self._read_case(case_id)
        em_state = case.em_state

        resolved = self._find_participant(case, actor_id)
        if resolved is None:
            logger.debug(
                "detect_and_apply_expiry: actor '%s' has no participant"
                " record in case '%s' — skipping",
                actor_id,
                case_id,
            )
            return _unchanged(em_state)
        participant_id, participant = resolved

        deadline = participant.rsvp_deadline_for(embargo_id)
        if deadline is None or now < deadline:
            return _unchanged(em_state)

        participant_changes = self._apply_where_legal(
            case, participant_id, participant, embargo_id, PEC_Trigger.TIME_OUT
        )
        if participant_changes:
            logger.info(
                "Invite to embargo '%s' timed out for actor '%s' on case '%s'"
                " (deadline=%s, PEC INVITED → TIMED_OUT)",
                embargo_id,
                actor_id,
                case_id,
                deadline,
            )

        # A signatory to the embargo in force has already agreed; a stale
        # deadline is not a real expiry.  Anyone else past the deadline
        # (just timed out, already timed out, or declined) triggers the EMB-17
        # late-Accept routing in the caller.
        return _unchanged(
            em_state,
            participant_changes=participant_changes,
            is_expired=not participant.is_signatory(case.active_embargo_id),
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
