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
(``detect_and_apply_expiry``, EMB-17) and the public eligibility check
callers use before creating anything (``assert_embargo_eligible``,
EP-04-008).
"""

import logging
from datetime import datetime

from vultron.core.models.case import VulnerabilityCase
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
from vultron.errors import VultronNotFoundError

logger = logging.getLogger(__name__)


def _unchanged(
    em_state: EM,
    *,
    participant_changes: list[ParticipantPECChange] | None = None,
    is_expired: bool = False,
) -> EmbargoLifecycleResult:
    """A result for an operation that moved neither EM state nor the case."""
    return EmbargoLifecycleResult(
        em_before=em_state,
        em_after=em_state,
        case_changed=False,
        case_embargo_changed=False,
        pec_exited=False,
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
        rsvp_deadline: datetime | None = None,
    ) -> EmbargoLifecycleResult:
        """Record that *invitee_id* was invited to an embargo, without moving EM.

        Applies PEC ``INVITE`` where CM-18-003 allows it — only from
        ``UNBOUND``, ``LAPSED``, ``DECLINED`` or ``EXPIRED``, so a
        ``SIGNATORY`` asked
        about a revision keeps its state (EP-09-004).  When *rsvp_deadline*
        is given the invitee's record takes it (CM-28-013).  The CASE_MANAGER
        calls this as it relays the Invite; a replica calls it as it replays
        the relay's ledger entry (EP-09-007), so both stores apply one rule.

        Args:
            case_id: ID of the ``VulnerabilityCase`` that owns the participant.
            invitee_id: ID of the invited actor.
            rsvp_deadline: The Invite's RSVP deadline, when it carries one.

        Returns:
            :class:`EmbargoLifecycleResult` with ``em_before == em_after`` and
            ``case_changed == False``; ``participant_changes`` carries the
            invitee's PEC state change, empty when ``INVITE`` did not apply.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case, or
                *invitee_id* has no participant record on it.
        """
        case = self._read_case(case_id)
        em_state = case.current_status.em.state
        participant_id = case.actor_participant_index.get(invitee_id)
        participant = (
            self._persistence.read(participant_id) if participant_id else None
        )
        if not isinstance(participant, CaseParticipant):
            raise VultronNotFoundError(
                "CaseParticipant", f"{invitee_id} on case {case_id}"
            )

        pec_before = participant.embargo_consent_state
        changed = participant.apply_pec_transition_if_legal(PEC_Trigger.INVITE)
        if (
            rsvp_deadline is not None
            and participant.invite_rsvp_deadline != rsvp_deadline
        ):
            participant.invite_rsvp_deadline = rsvp_deadline
            changed = True
        if changed:
            self._persistence.save(participant)

        pec_after = participant.embargo_consent_state
        changes = (
            [
                ParticipantPECChange(
                    participant_id=participant.id_,
                    pec_before=pec_before.value,
                    pec_after=pec_after.value,
                )
            ]
            if pec_after != pec_before
            else []
        )
        logger.info(
            "Recorded embargo invite of '%s' on case '%s' (PEC %s → %s)",
            invitee_id,
            case_id,
            pec_before.name,
            pec_after.name,
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
        is_active = self._assert_rejectable(case, embargo_id)
        participant_changes = self._rejection_consent(
            case, actor_id, embargo_id, is_active=is_active
        )
        logger.info(
            "Recorded rejection of embargo '%s' by actor '%s' on case '%s'"
            " (%d PEC state change(s))",
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
            if participant.add_accepted_embargo(embargo_id):
                changed = True
        elif (
            pec_trigger == PEC_Trigger.DECLINE
            and embargo_id is not None
            and participant.remove_accepted_embargo(embargo_id)
        ):
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

    def assess_invite_expiry(
        self,
        *,
        case_id: str,
        actor_id: str,
        now: datetime,
    ) -> tuple[bool, bool]:
        """Read-only check: has the RSVP deadline passed and does EXPIRE need applying?

        Returns a ``(is_expired, needs_apply)`` pair where:

        * ``is_expired`` — ``True`` when the deadline has passed **and** the
          participant is not ``SIGNATORY``.  Used by :func:`EMB-17` routing.
        * ``needs_apply`` — ``True`` when the participant is still ``INVITED``
          **and** the deadline has passed.  When ``True``, the caller MUST
          call :meth:`record_invite_expiry` after committing the ledger entry
          (CLP-10-006).

        This method makes **no writes**.  The pair mirrors what
        :meth:`detect_and_apply_expiry` computes but without the side-effect,
        so a BT node can assess the situation, the commit node can persist the
        ledger entry, and only then the effect node calls
        :meth:`record_invite_expiry` (guard → commit → effect, CLP-10-006,
        BT-06-006).

        Args:
            case_id: ID of the ``VulnerabilityCase``.
            actor_id: ID of the actor whose participant record to check.
            now: Current UTC datetime used for deadline comparison.

        Returns:
            ``(is_expired, needs_apply)`` — both ``False`` when the actor has
            no participant record, the record has no deadline, or the deadline
            has not yet passed.
        """
        case = self._read_case(case_id)
        participant_id = case.actor_participant_index.get(actor_id)
        if not participant_id:
            return False, False
        participant = self._persistence.read(participant_id)
        if not isinstance(participant, CaseParticipant):
            return False, False
        deadline = participant.invite_rsvp_deadline
        if deadline is None or now < deadline:
            return False, False
        # Deadline passed.
        needs_apply = participant.embargo_consent_state == PEC.INVITED.value
        is_expired = participant.embargo_consent_state != PEC.SIGNATORY.value
        return is_expired, needs_apply

    def record_invite_expiry(
        self,
        *,
        case_id: str,
        actor_id: str,
    ) -> EmbargoLifecycleResult:
        """Apply PEC ``EXPIRE`` (``INVITED → EXPIRED``) after the commit.

        This is the **effect** half of the guard → commit → effect trio
        (CLP-10-006, BT-06-006).  The CASE_MANAGER calls it only after its
        expiry entry has been committed by
        :func:`~vultron.core.behaviors.sync.commit_tree.create_commit_log_entry_tree`.

        Idempotent: if the participant is no longer ``INVITED`` (already
        ``EXPIRED``, or any other state), the call is a no-op.  An actor with
        no participant record is logged and skipped.

        Args:
            case_id: ID of the ``VulnerabilityCase``.
            actor_id: ID of the actor whose invite expired.

        Returns:
            :class:`EmbargoLifecycleResult` with ``is_expired=True`` when
            ``EXPIRE`` was applied, ``is_expired=False`` when the invitee was
            already ``EXPIRED`` (idempotent call).
        """
        case = self._read_case(case_id)
        em_state = case.current_status.em.state
        participant_id = case.actor_participant_index.get(actor_id)
        if not participant_id:
            logger.debug(
                "record_invite_expiry: actor '%s' has no participant"
                " record in case '%s' — skipping",
                actor_id,
                case_id,
            )
            return _unchanged(em_state)
        participant = self._persistence.read(participant_id)
        if not isinstance(participant, CaseParticipant):
            return _unchanged(em_state)
        participant_changes: list[ParticipantPECChange] = []
        if participant.embargo_consent_state == PEC.INVITED.value:
            pec_before = participant.embargo_consent_state
            participant.apply_pec_transition(PEC_Trigger.EXPIRE)
            self._persistence.save(participant)
            participant_changes.append(
                ParticipantPECChange(
                    participant_id=participant_id,
                    pec_before=pec_before,
                    pec_after=participant.embargo_consent_state,
                )
            )
            logger.info(
                "Invite expired for actor '%s' on case '%s'"
                " (PEC INVITED → EXPIRED — recorded after commit)",
                actor_id,
                case_id,
            )
        is_expired = bool(participant_changes)
        return _unchanged(
            em_state,
            participant_changes=participant_changes,
            is_expired=is_expired,
        )

    def honour_late_accept(
        self,
        *,
        case_id: str,
        actor_id: str,
        embargo_id: str,
    ) -> EmbargoLifecycleResult:
        """Apply the honour decision: ``EXPIRED → SIGNATORY`` (or ``DECLINED → INVITED → SIGNATORY``).

        This is the **effect** of :data:`HONOUR_LATE_ACCEPT_EVENT_TYPE`
        (EMB-17-001, ADR-0118).  Called by the replica replay node
        :class:`~vultron.core.behaviors.embargo.nodes.expiry.ApplyHonourLateAcceptFromLedgerNode`
        **and** by the CASE_MANAGER's
        :class:`~vultron.core.behaviors.embargo.nodes.expiry.HonourLateAcceptNode`
        **after** the entry is committed (CLP-10-006).

        A ``DECLINED`` participant is first moved ``DECLINED → INVITED`` (since
        ``ACCEPT`` is not legal from ``DECLINED``, CM-18-003), then the shared
        :meth:`~vultron.core.services.embargo_lifecycle.pec._PecEffectsMixin._record_actor_pec_acceptance`
        applies ``ACCEPT`` and records *embargo_id* in ``accepted_embargo_ids``.

        Idempotent: a participant already ``SIGNATORY`` is not changed.

        Args:
            case_id: ID of the ``VulnerabilityCase``.
            actor_id: ID of the honouring actor.
            embargo_id: ID of the active ``EmbargoEvent`` to accept.

        Returns:
            :class:`EmbargoLifecycleResult` describing the PEC transitions.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case or
                *actor_id* has no participant record on it.
        """
        case = self._read_case(case_id)
        em_state = case.current_status.em.state
        participant_id = case.actor_participant_index.get(actor_id)
        participant = (
            self._persistence.read(participant_id) if participant_id else None
        )
        if not isinstance(participant, CaseParticipant) or not participant_id:
            raise VultronNotFoundError(
                "CaseParticipant", f"{actor_id} on case {case_id}"
            )

        participant_changes: list[ParticipantPECChange] = []

        # DECLINED is not a legal ACCEPT source (CM-18-003); re-invite first.
        if participant.embargo_consent_state == PEC.DECLINED.value:
            pec_before = participant.embargo_consent_state
            participant.apply_pec_transition(PEC_Trigger.INVITE)
            self._persistence.save(participant)
            participant_changes.append(
                ParticipantPECChange(
                    participant_id=participant_id,
                    pec_before=pec_before,
                    pec_after=participant.embargo_consent_state,
                )
            )
            logger.info(
                "honour_late_accept: re-invited DECLINED actor '%s'"
                " on case '%s' before ACCEPT (DECLINED → INVITED)",
                actor_id,
                case_id,
            )

        # Re-read case after the INVITE write so the fresh participant record
        # is used by _record_actor_pec_acceptance (participant may have changed).
        case = self._read_case(case_id)
        accept_changes = self._record_actor_pec_acceptance(
            case, actor_id, embargo_id, advance=True
        )
        all_changes = participant_changes + accept_changes
        logger.info(
            "honour_late_accept: honoured late Accept for actor '%s'"
            " on case '%s' (embargo '%s', EMB-17-001;"
            " %d PEC state change(s))",
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
        now: datetime,
    ) -> EmbargoLifecycleResult:
        """Lazily enforce the RSVP deadline: apply EXPIRE if the invite expired.

        Reads the participant record for *actor_id* in *case_id*.  If the
        participant is in ``INVITED`` state and ``invite_rsvp_deadline`` is
        set and ``now >= invite_rsvp_deadline``, applies ``PEC_Trigger.EXPIRE``
        (``INVITED → EXPIRED``) and returns a result with ``is_expired=True``.
        An expired invite is not a refusal, so ``DECLINE`` is never the timer
        path (ADR-0118, CM-18-002).

        Idempotent: if the participant is already ``EXPIRED`` (or any state
        other than ``INVITED``), no PEC transition is applied.  The result
        still carries ``is_expired=True`` when the deadline has passed and the
        participant is not ``SIGNATORY``, so the caller can branch on whether
        the invite window closed without re-deriving it.

        Args:
            case_id: ID of the VulnerabilityCase.
            actor_id: ID of the actor whose participant record to check.
            now: Current UTC datetime used for deadline comparison.

        Returns:
            :class:`EmbargoLifecycleResult` with ``is_expired`` reflecting
            whether the deadline has passed.
        """
        case = self._read_case(case_id)

        em_state = case.current_status.em.state

        participant_id = case.actor_participant_index.get(actor_id)
        if not participant_id:
            logger.debug(
                "detect_and_apply_expiry: actor '%s' has no participant"
                " record in case '%s' — skipping",
                actor_id,
                case_id,
            )
            return _unchanged(em_state)

        participant = self._persistence.read(participant_id)
        if not isinstance(participant, CaseParticipant):
            return _unchanged(em_state)

        deadline = participant.invite_rsvp_deadline
        is_expired = deadline is not None and now >= deadline

        if not is_expired:
            return _unchanged(em_state)

        # Deadline has passed — apply EXPIRE if still in INVITED state.
        # Idempotent: EXPIRED and every other state are left unchanged.
        participant_changes: list[ParticipantPECChange] = []
        if participant.embargo_consent_state == PEC.INVITED.value:
            pec_before = participant.embargo_consent_state
            participant.apply_pec_transition(PEC_Trigger.EXPIRE)
            self._persistence.save(participant)
            participant_changes.append(
                ParticipantPECChange(
                    participant_id=participant_id,
                    pec_before=pec_before,
                    pec_after=participant.embargo_consent_state,
                )
            )
            logger.info(
                "Invite expired for actor '%s' on case '%s'"
                " (deadline=%s, PEC INVITED → EXPIRED)",
                actor_id,
                case_id,
                deadline,
            )

        # A SIGNATORY participant has already accepted; a stale deadline is not
        # a real expiry.  Any other state past the deadline (just-expired,
        # already-expired, or declined) triggers the EMB-17 late-Accept routing
        # in the caller.
        is_expired = participant.embargo_consent_state != PEC.SIGNATORY.value

        return _unchanged(
            em_state,
            participant_changes=participant_changes,
            is_expired=is_expired,
        )

    def exit_participant_consent(
        self, case: VulnerabilityCase
    ) -> list[ParticipantPECChange]:
        """Move every participant of *case* to the terminal UNBOUND_EXITED.

        The termination cascade (MSM-07-006, ADR-0118) as a public operation
        for the teardown nodes, which apply it to a case whose EM state they
        have already moved; :meth:`terminate_active_embargo` runs the same
        :meth:`_cascade_pec_exit`, so the two paths share one loop
        (CS-22-001).  Idempotent: a participant already exited is skipped.
        """
        return self._cascade_pec_exit(case)

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
