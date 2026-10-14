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

"""Participant Embargo Consent (PEC) side effects of EM transitions.

The EM operations in the sibling modules change one case's embargo state;
these helpers record the matching consent on the participant records — one
actor's record on accept/reject, every participant's when the owner activates
a shorter revision.  Consent is per (participant, embargo) (ADR-0122,
CM-10-001, CM-18-001): each participant holds one row per embargo register
entry, "signatory" is the row for the active embargo saying ``AGREED``, a row
whose entry is final is frozen, and a lapse or an exit is derived from the
rows and the register, never written.  Every
helper persists what it changes and reports each row it moved as a
:class:`ParticipantConsentChange`.
"""

import logging

from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.embargo_lifecycle.activation_arm import (
    _ActivationArmMixin,
)
from vultron.core.services.embargo_lifecycle.results import (
    ParticipantConsentChange,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
    PEC_Trigger,
)
from vultron.errors import VultronNotFoundError, VultronValidationError

logger = logging.getLogger(__name__)


def owner_declined_embargo(
    persistence: CasePersistence,
    case: VulnerabilityCase,
    embargo_id: str,
) -> bool:
    """True when the case owner's consent row for *embargo_id* is ``DECLINED``.

    Activation records the owner's ``AGREE``, which ``DECLINED`` refuses
    (CM-18-003), so an owner that declined the proposal as a participant is
    invited again before it can activate it (ADR-0122).  A case with no owner,
    or an owner with no participant record in *persistence*, has no declined
    row, so the activation is not refused on this ground; nor has an owner
    whose case does not hold the embargo yet (a replica that has not
    recorded the proposal), since it holds no row for it.  Shared by the
    received-side guard (``OwnerMayActivateEmbargoNode``) and the lifecycle's
    STRICT enforcement (``_assert_owner_may_activate``) so the two cannot drift.
    """
    owner_id = _as_id(case.attributed_to)
    if owner_id is None or case.embargo_register_entry(embargo_id) is None:
        return False
    participant_id = case.actor_participant_index.get(owner_id)
    if not participant_id:
        return False
    participant = persistence.read(participant_id)
    return (
        isinstance(participant, CaseParticipant)
        and participant.consent_for(embargo_id) == EmbargoConsentState.DECLINED
    )


def _consent_row(
    persistence: CasePersistence,
    case: VulnerabilityCase,
    actor_id: str,
    embargo_id: str,
) -> EmbargoConsentState | None:
    """*actor_id*'s consent row for *embargo_id*, or ``None`` with no record."""
    participant_id = case.actor_participant_index.get(actor_id)
    participant = persistence.read(participant_id) if participant_id else None
    if not isinstance(participant, CaseParticipant):
        return None
    return participant.consent_for(embargo_id)


def embargo_withdrawal_refusal(
    persistence: CasePersistence,
    case: VulnerabilityCase,
    actor_id: str,
    embargo_id: str | None,
) -> str | None:
    """Why *actor_id* cannot withdraw from *embargo_id*, or ``None`` if it can.

    Withdrawal is ``Leave(EmbargoEvent)`` (MSM-07-010, EP-09-013): only a
    participant whose row for the embargo *in force* is ``AGREED`` leaves
    it, and the case owner never does — it ends an embargo by terminating it
    (CM-02-005).  *embargo_id* ``None`` asks about the embargo in force, the
    trigger's question; the received side passes the embargo the Leave
    names.  Shared by the received-side guard, the trigger and the
    lifecycle's own check, so the three cannot drift.
    """
    case_id = _as_id(case)
    active_id = case.active_embargo_id
    if active_id is None:
        return (
            f"No embargo is in force on case '{case_id}', so there is"
            " nothing to withdraw from (MSM-07-010)"
        )
    if embargo_id is not None and embargo_id != active_id:
        return (
            f"Embargo '{embargo_id}' is not the embargo in force on case"
            f" '{case_id}': only the active embargo can be withdrawn from"
            " (MSM-07-010)"
        )
    if _as_id(case.attributed_to) == actor_id:
        return (
            f"'{actor_id}' is the case owner of '{case_id}': the case owner"
            " ends an embargo by terminating it, not by withdrawing"
            " (MSM-07-010, CM-02-005)"
        )
    row = _consent_row(persistence, case, actor_id, active_id)
    if row is None:
        return f"'{actor_id}' has no participant record on case '{case_id}'"
    if row != EmbargoConsentState.AGREED:
        return (
            f"'{actor_id}' is {row.value} on embargo '{active_id}' of case"
            f" '{case_id}', not AGREED: only a signatory withdraws"
            " (MSM-07-010, EP-09-013)"
        )
    return None


def reject_is_withdrawal_refusal(
    persistence: CasePersistence,
    case: VulnerabilityCase,
    actor_id: str,
    embargo_id: str,
) -> str | None:
    """Why a Reject of *embargo_id* by *actor_id* is refused, or ``None``.

    A ``Reject(Invite(EmbargoEvent))`` of the embargo *in force* from an
    ``AGREED`` row would be a withdrawal, and withdrawal is
    ``Leave(EmbargoEvent)`` (MSM-07-004, MSM-07-010), so it is refused.  A
    Reject of the embargo in force from any other row, or of a proposal,
    is an answer and is not refused here.
    """
    if embargo_id != case.active_embargo_id:
        return None
    row = _consent_row(persistence, case, actor_id, embargo_id)
    if row != EmbargoConsentState.AGREED:
        return None
    return (
        f"'{actor_id}' is AGREED on the embargo in force '{embargo_id}' of"
        f" case '{_as_id(case)}': a Reject does not withdraw from it;"
        " withdrawal is Leave(EmbargoEvent) (MSM-07-004, MSM-07-010)"
    )


def _consent_change(
    participant_id: str,
    embargo_id: str,
    before: EmbargoConsentState,
    participant: CaseParticipant,
) -> ParticipantConsentChange:
    """Describe the row move *participant* just made from *before*."""
    return ParticipantConsentChange(
        participant_id=participant_id,
        embargo_id=embargo_id,
        consent_before=before.value,
        consent_after=participant.consent_for(embargo_id).value,
    )


class _PecEffectsMixin(_ActivationArmMixin):
    """PEC bookkeeping shared by the EM transition operations."""

    def _find_participant(
        self, case: VulnerabilityCase, actor_id: str
    ) -> tuple[str, CaseParticipant] | None:
        """*actor_id*'s ``(participant_id, record)`` on *case*, or ``None``.

        The one participant lookup the lifecycle operations share; callers
        decide whether an absent record is skipped, warned about or refused.
        """
        participant_id = case.actor_participant_index.get(actor_id)
        participant = (
            self._persistence.read(participant_id) if participant_id else None
        )
        if not participant_id or not isinstance(participant, CaseParticipant):
            return None
        return participant_id, participant

    def _participant_for_actor(
        self, case: VulnerabilityCase, actor_id: str, purpose: str
    ) -> tuple[str, CaseParticipant] | None:
        """Resolve *actor_id*'s participant record on *case*, warning when absent.

        Returns ``None`` (after a WARNING naming *purpose*) when the actor has
        no participant record in the case.
        """
        resolved = self._find_participant(case, actor_id)
        if resolved is None:
            logger.warning(
                "Actor '%s' has no CaseParticipant in case '%s'"
                " — cannot record embargo %s",
                actor_id,
                _as_id(case),
                purpose,
            )
        return resolved

    def _require_participant(
        self, case: VulnerabilityCase, actor_id: str
    ) -> tuple[str, CaseParticipant]:
        """*actor_id*'s participant record on *case*, or raise.

        Raises:
            VultronNotFoundError: the actor has no participant record on it.
        """
        resolved = self._find_participant(case, actor_id)
        if resolved is None:
            raise VultronNotFoundError(
                "CaseParticipant", f"{actor_id} on case {case.id_}"
            )
        return resolved

    def _apply_where_legal(
        self,
        case: VulnerabilityCase,
        participant_id: str,
        participant: CaseParticipant,
        embargo_id: str,
        trigger: PEC_Trigger,
    ) -> list[ParticipantConsentChange]:
        """Apply *trigger* to one row where it is legal; persist and report it.

        The row's register entry decides whether it can move at all: a row
        for a final entry is frozen (ADR-0122).  Returns the one change, or
        nothing when the trigger did not apply.
        """
        before = participant.consent_for(embargo_id)
        if not participant.apply_pec_transition_if_legal(
            embargo_id,
            trigger,
            entry_status=case.embargo_register_status(embargo_id),
        ):
            return []
        self._persistence.save(participant)
        return [
            _consent_change(participant_id, embargo_id, before, participant)
        ]

    # -- one actor's record -------------------------------------------------

    def _record_actor_acceptance(
        self,
        case: VulnerabilityCase,
        actor_id: str,
        embargo_id: str,
    ) -> list[ParticipantConsentChange]:
        """Record *actor_id*'s agreement to *embargo_id*.

        Marks the row for *embargo_id* ``AGREED`` (CM-18-003): always this
        embargo's row, whether it is the embargo in force, a proposed
        revision, or the actor's own proposal.  Whether that makes the actor
        a signatory is a lookup of the active embargo, never a second write
        (ADR-0122).

        Idempotent (CM-13-005): an ``AGREED`` row changes nothing and reports
        nothing.  A ``DECLINED`` row records nothing: ``AGREE`` is not legal
        from it (CM-18-003), and agreeing here would let the content gate
        (CM-10-004) admit an actor that has declined; it is invited again
        first.  A row whose embargo is in a final register status —
        superseded, rejected, cancelled or terminated — is frozen and records
        nothing either, and nothing is recorded for an embargo the register
        does not hold: a row for an embargo the case never saw would be a row
        with no entry (ADR-0122).
        """
        resolved = self._participant_for_actor(case, actor_id, "acceptance")
        if resolved is None:
            return []
        participant_id, participant = resolved
        if case.embargo_register_entry(embargo_id) is None:
            logger.info(
                "Embargo '%s' is not in the register of case '%s'; actor"
                " '%s' agreement records nothing (ADR-0122)",
                embargo_id,
                _as_id(case),
                actor_id,
            )
            return []
        changes = self._apply_where_legal(
            case, participant_id, participant, embargo_id, PEC_Trigger.AGREE
        )
        if not changes:
            logger.info(
                "Actor '%s' is %s on embargo '%s' (%s) of case '%s'; its"
                " agreement records nothing (CM-18-003, ADR-0122)",
                actor_id,
                participant.consent_for(embargo_id),
                embargo_id,
                case.embargo_register_status(embargo_id),
                _as_id(case),
            )
        return changes

    def _record_actor_rejection(
        self,
        case: VulnerabilityCase,
        actor_id: str,
        embargo_id: str,
        *,
        withdrawal: bool,
    ) -> list[ParticipantConsentChange]:
        """Decline *actor_id*'s row for *embargo_id*, and with *withdrawal* more.

        Marks the row for *embargo_id* ``DECLINED`` — a ``TIMED_OUT`` one
        included, since a late explicit Reject is an answer (ADR-0118).  A
        Reject (*withdrawal* unset) declines that row only: refusing a
        *proposed* embargo leaves the actor's row for the embargo in force
        untouched, so a signatory stays a signatory to it, and a Reject of the
        embargo in force answers it from a row that never agreed
        (MSM-07-004).

        With *withdrawal* set — ``Leave(EmbargoEvent)`` from an ``AGREED``
        row for the embargo in force (MSM-07-010) — every open proposal the
        actor had agreed to is declined too: a case has one active embargo,
        so every open proposal is a revision of it (EP-08-004), and an actor
        that has left the embargo has left its revisions — otherwise a
        ``DECLINED`` actor could still hold an ``AGREED`` row for a revision
        that later activates and be admitted by the content gate (CM-10-004)
        while having withdrawn.  Only rows it had *agreed* to are declined: a
        revision it was merely invited to stays answerable.

        Idempotent (CM-13-005): an already-``DECLINED`` row changes nothing
        and reports nothing.  A row whose entry is final is frozen, so nothing
        is recorded once the embargo has terminated (ADR-0118, ADR-0122).
        """
        resolved = self._participant_for_actor(case, actor_id, "rejection")
        if resolved is None:
            return []
        participant_id, participant = resolved

        targets = [embargo_id]
        if withdrawal:
            targets.extend(
                open_id
                for open_id in case.proposed_embargo_ids
                if open_id != embargo_id
                and participant.consent_for(open_id)
                == EmbargoConsentState.AGREED
            )
        changes: list[ParticipantConsentChange] = []
        for target in targets:
            changes.extend(
                self._apply_where_legal(
                    case,
                    participant_id,
                    participant,
                    target,
                    PEC_Trigger.DECLINE,
                )
            )
        return changes

    @staticmethod
    def _assert_rejectable(case: VulnerabilityCase, embargo_id: str) -> bool:
        """Classify the embargo a Reject names; True when it is the active one.

        A Reject names either the case's active embargo (an answer from a
        row that has not agreed to it) or one of its open proposals (refusal
        of those terms).  Anything else is a protocol error, not a consent
        change (ADR-0093).  Call this *before* the owner's decision prunes
        the proposal, or an open proposal is misread as unknown.

        Raises:
            VultronValidationError: If *embargo_id* is neither the active
                embargo nor an open proposal of *case*.
        """
        if embargo_id == case.active_embargo_id:
            return True
        if embargo_id in case.proposed_embargo_ids:
            return False
        raise VultronValidationError(
            f"Embargo '{embargo_id}' is neither the active embargo nor an"
            f" open proposal of case '{_as_id(case)}': nothing to reject."
        )

    def _rejection_consent(
        self,
        case: VulnerabilityCase,
        actor_id: str,
        embargo_id: str,
    ) -> list[ParticipantConsentChange]:
        """The whole MSM-07-004 consent effect of *actor_id* rejecting *embargo_id*.

        A ``Reject(Invite(EmbargoEvent))`` is always the sender's own consent,
        the case owner's included (ADR-0122): the owner's decision for the
        case is a separate ``Reject(EmbargoEvent, target=Case)`` that writes
        no consent.  It declines the named embargo's row only, whether that
        embargo is in force or proposed, and with *no* embargo in force a
        Reject of one proposal declines that proposal's row only (CM-18-001).
        It never withdraws: a Reject of the embargo in force from an
        ``AGREED`` row is refused (:func:`reject_is_withdrawal_refusal`);
        withdrawal is ``Leave(EmbargoEvent)`` (MSM-07-010).

        Raises:
            VultronValidationError: The Reject would withdraw *actor_id*
                from the embargo in force.
        """
        refusal = reject_is_withdrawal_refusal(
            self._persistence, case, actor_id, embargo_id
        )
        if refusal is not None:
            raise VultronValidationError(refusal)
        return self._record_actor_rejection(
            case, actor_id, embargo_id, withdrawal=False
        )

    def _withdrawal_consent(
        self,
        case: VulnerabilityCase,
        actor_id: str,
        embargo_id: str,
    ) -> list[ParticipantConsentChange]:
        """The whole MSM-07-010 consent effect of *actor_id* leaving *embargo_id*.

        Declines the actor's ``AGREED`` row for the embargo in force and every
        open proposal's row it had agreed to; no register entry moves.

        Raises:
            VultronValidationError: *embargo_id* is not the embargo in force,
                the actor's row for it is not ``AGREED``, or the actor is the
                case owner (:func:`embargo_withdrawal_refusal`).
        """
        refusal = embargo_withdrawal_refusal(
            self._persistence, case, actor_id, embargo_id
        )
        if refusal is not None:
            raise VultronValidationError(refusal)
        return self._record_actor_rejection(
            case, actor_id, embargo_id, withdrawal=True
        )
