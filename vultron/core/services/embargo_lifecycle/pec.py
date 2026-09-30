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
these helpers apply the matching consent change to the participant records
— one actor's record on accept/reject, every participant's when the owner
activates a revision or terminates the embargo.  Consent is per embargo
(CM-10-001): ``accepted_embargo_ids`` records which terms a participant has
accepted, the scalar PEC state whether it is bound by the *active* embargo
(CM-18-001).  Every helper persists what it changes and reports each
*state* change as a :class:`ParticipantPECChange`; a write that only touches
``accepted_embargo_ids`` is persisted but not reported, because it moves no
consent state.
"""

import logging
from collections.abc import Callable, Iterator

from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.services.embargo_lifecycle.base import _LifecycleBase
from vultron.core.services.embargo_lifecycle.results import (
    ParticipantPECChange,
)
from vultron.core.services.embargo_ordering import (
    earliest_expiring_embargo_id,
)
from vultron.core.states.participant_embargo_consent import (
    PEC,
    PEC_Trigger,
)
from vultron.errors import VultronValidationError

logger = logging.getLogger(__name__)

#: PEC states from which an ``ACCEPT`` advances a participant to ``SIGNATORY``
#: (CM-18-003); ``DECLINED`` is deliberately absent.
_ACCEPTABLE_STATES = frozenset(
    {PEC.UNBOUND.value, PEC.INVITED.value, PEC.LAPSED.value}
)


def _pec_change(
    participant_id: str, pec_before: str, participant: CaseParticipant
) -> ParticipantPECChange:
    """Describe the PEC move *participant* just made from *pec_before*."""
    return ParticipantPECChange(
        participant_id=participant_id,
        pec_before=pec_before,
        pec_after=participant.embargo_consent_state,
    )


class _PecEffectsMixin(_LifecycleBase):
    """PEC bookkeeping shared by the EM transition operations."""

    def _participant_for_actor(
        self, case: VulnerabilityCase, actor_id: str, purpose: str
    ) -> tuple[str, CaseParticipant] | None:
        """Resolve *actor_id*'s participant record on *case*.

        Returns ``None`` (after a WARNING naming *purpose*) when the actor has
        no participant in the case, and silently when the record does not
        rehydrate as a :class:`CaseParticipant`.
        """
        participant_id = case.actor_participant_index.get(actor_id)
        if not participant_id:
            logger.warning(
                "Actor '%s' has no CaseParticipant in case '%s'"
                " — cannot record embargo %s",
                actor_id,
                _as_id(case),
                purpose,
            )
            return None

        participant = self._persistence.read(participant_id)
        if not isinstance(participant, CaseParticipant):
            return None
        return participant_id, participant

    def _each_participant(
        self, case: VulnerabilityCase
    ) -> Iterator[tuple[str, CaseParticipant]]:
        """Yield ``(participant_id, participant)`` for every record on *case*."""
        for entry in case.case_participants:
            participant_id = _as_id(entry)
            if participant_id is None:
                continue
            participant = self._persistence.read(participant_id)
            if isinstance(participant, CaseParticipant):
                yield participant_id, participant

    # -- one actor's record -------------------------------------------------

    def _record_actor_pec_acceptance(
        self,
        case: VulnerabilityCase,
        actor_id: str,
        embargo_id: str,
        *,
        advance: bool = True,
    ) -> list[ParticipantPECChange]:
        """Record *actor_id*'s acceptance of *embargo_id*.

        Adds the id to ``accepted_embargo_ids`` and, with *advance* set,
        applies ``ACCEPT`` unless the participant is already ``SIGNATORY`` or
        ``DECLINED``.  With *advance* false only the list changes: the
        participant accepted terms that are not (yet) the embargo in force —
        a proposed revision, or its own proposal (MSM-07-003, EP-05-002) —
        and its scalar state stays whatever the *active* embargo makes it.

        Idempotent (CM-13-005): a ``SIGNATORY`` re-accepting changes nothing
        and reports nothing.
        """
        resolved = self._participant_for_actor(case, actor_id, "acceptance")
        if resolved is None:
            return []
        participant_id, participant = resolved

        pec_before = participant.embargo_consent_state
        changed = False

        if advance and pec_before in _ACCEPTABLE_STATES:
            participant.apply_pec_transition(PEC_Trigger.ACCEPT)
            changed = True

        if participant.add_accepted_embargo(embargo_id):
            changed = True

        if not changed:
            return []
        self._persistence.save(participant)
        if participant.embargo_consent_state == pec_before:
            return []
        return [_pec_change(participant_id, pec_before, participant)]

    def _record_actor_pec_rejection(
        self,
        case: VulnerabilityCase,
        actor_id: str,
        embargo_id: str,
        *,
        withdrawal: bool,
    ) -> list[ParticipantPECChange]:
        """Record *actor_id*'s rejection of *embargo_id* (MSM-07-004).

        Drops the id from ``accepted_embargo_ids`` and applies ``DECLINE``
        to a participant not already ``DECLINED``.  With *withdrawal* set the
        Reject names the case's *active* embargo, so ``DECLINE`` applies from
        every state including ``SIGNATORY`` (consent withdrawal, ADR-0093).
        Without it the Reject names a *proposed* embargo: a ``SIGNATORY``
        keeps its state, because refusing proposed terms is not withdrawing
        from the embargo in force.

        Idempotent (CM-13-005): an already-``DECLINED`` participant changes
        nothing and reports nothing.
        """
        resolved = self._participant_for_actor(case, actor_id, "rejection")
        if resolved is None:
            return []
        participant_id, participant = resolved

        pec_before = participant.embargo_consent_state
        changed = False

        keeps_state = pec_before == PEC.DECLINED.value or (
            not withdrawal and pec_before == PEC.SIGNATORY.value
        )
        if not keeps_state:
            participant.apply_pec_transition(PEC_Trigger.DECLINE)
            changed = True

        if participant.remove_accepted_embargo(embargo_id):
            changed = True

        if not changed:
            return []
        self._persistence.save(participant)
        if participant.embargo_consent_state == pec_before:
            return []
        return [_pec_change(participant_id, pec_before, participant)]

    @staticmethod
    def _assert_rejectable(case: VulnerabilityCase, embargo_id: str) -> bool:
        """Classify the embargo a Reject names; True when it is the active one.

        A Reject names either the case's active embargo (consent withdrawal)
        or one of its open proposals (refusal of those terms).  Anything else
        is a protocol error, not a consent change (ADR-0093).  Call this
        *before* the owner's decision prunes the proposal, or an open
        proposal is misread as unknown.

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
        self, case: VulnerabilityCase, actor_id: str, embargo_id: str
    ) -> list[ParticipantPECChange]:
        """The whole MSM-07-004 consent effect of *actor_id* rejecting *embargo_id*.

        :meth:`_assert_rejectable` decides whether the Reject withdraws from
        the active embargo or refuses proposed terms.  The owner's EJ — the
        owner refusing a proposed revision while an embargo is in force —
        changes nobody's record, the owner's included: the owner is keeping
        the prior terms, not declining them.  Every other Reject is recorded
        by :meth:`_record_actor_pec_rejection`.  Shared by
        ``reject_embargo_invite`` and ``record_embargo_rejection`` so the two
        sides cannot drift; call it before the owner's decision prunes the
        proposal.

        Raises:
            VultronValidationError: If *embargo_id* is neither the active
                embargo nor an open proposal of the case.
        """
        is_active = self._assert_rejectable(case, embargo_id)
        is_owner = _as_id(case.attributed_to) == actor_id
        if is_owner and not is_active and case.active_embargo_id is not None:
            logger.info(
                "Owner '%s' rejected proposed revision '%s' on case '%s';"
                " no consent record changes (EJ)",
                actor_id,
                embargo_id,
                _as_id(case),
            )
            return []
        return self._record_actor_pec_rejection(
            case, actor_id, embargo_id, withdrawal=is_active
        )

    # -- every participant's record ----------------------------------------

    def _cascade_pec(
        self,
        case: VulnerabilityCase,
        *,
        trigger: PEC_Trigger,
        select: Callable[[CaseParticipant], bool],
    ) -> list[ParticipantPECChange]:
        """Apply *trigger* to every participant of *case* that *select* picks.

        Each moved participant is persisted and reported.
        """
        changes: list[ParticipantPECChange] = []
        for participant_id, participant in self._each_participant(case):
            if not select(participant):
                continue
            state = participant.embargo_consent_state
            participant.apply_pec_transition(trigger)
            self._persistence.save(participant)
            changes.append(_pec_change(participant_id, state, participant))
        return changes

    def _cascade_pec_reset(
        self, case: VulnerabilityCase
    ) -> list[ParticipantPECChange]:
        """Reset all participants' PEC state to UNBOUND.

        Called when an embargo is terminated.  Returns a list of
        :class:`ParticipantPECChange` for every participant that was updated.
        """
        return self._cascade_pec(
            case,
            trigger=PEC_Trigger.RESET,
            select=lambda p: p.embargo_consent_state != PEC.UNBOUND.value,
        )

    def _cascade_pec_revise(
        self, case: VulnerabilityCase, *, revised_embargo_id: str
    ) -> list[ParticipantPECChange]:
        """Lapse every SIGNATORY that has not accepted *revised_embargo_id*.

        Called when the case owner *activates* a revision ending later than
        the embargo it replaces (EP-05-001, MSM-07-005) — never when one is
        merely proposed (EP-05-002).  A signatory whose
        ``accepted_embargo_ids`` already holds the revised id stays
        ``SIGNATORY``; the rest move to ``LAPSED`` via the ``REVISE``
        trigger, so their consent to the longer terms is explicit.

        Returns a list of :class:`ParticipantPECChange` records for each
        participant whose PEC state was updated.
        """
        return self._cascade_pec(
            case,
            trigger=PEC_Trigger.REVISE,
            select=lambda p: (
                p.embargo_consent_state == PEC.SIGNATORY.value
                and revised_embargo_id not in p.accepted_embargo_ids
            ),
        )

    def _carry_signatories_over(
        self, case: VulnerabilityCase, *, revised_embargo_id: str
    ) -> None:
        """Record *revised_embargo_id* on every SIGNATORY's accepted list.

        The shorter arm of EP-05-001: a revision ending no later than the
        embargo it replaces asks nothing new of an existing signatory
        (agreeing to N days is agreeing to every shorter period), so its
        consent carries over by containment (CM-10-001) with no state change.
        """
        for _participant_id, participant in self._each_participant(case):
            if participant.embargo_consent_state != PEC.SIGNATORY.value:
                continue
            if participant.add_accepted_embargo(revised_embargo_id):
                self._persistence.save(participant)

    def _revision_ends_no_later(
        self, *, previous_embargo_id: str, revised_embargo_id: str
    ) -> bool:
        """True when revision B ends no later than the embargo A it replaces.

        The A-vs-B comparison shares :func:`earliest_expiring_embargo_id`'s
        read path (EP-08), so an unreadable record fails closed rather than
        silently deciding the arm; a tie keeps B, the first candidate, so
        equal terms carry everyone over.  Call it *before* the case is
        mutated, so a failure leaves EM and ``active_embargo`` untouched.

        Raises:
            VultronNotFoundError: If either embargo does not resolve.
            VultronValidationError: If either record is not an ``EmbargoEvent``.
        """
        return (
            earliest_expiring_embargo_id(
                self._persistence, [revised_embargo_id, previous_embargo_id]
            )
            == revised_embargo_id
        )

    def _reevaluate_consent_at_activation(
        self,
        case: VulnerabilityCase,
        *,
        revised_embargo_id: str,
        ends_no_later: bool,
    ) -> list[ParticipantPECChange]:
        """Re-evaluate every participant's consent when A is replaced by B.

        The EP-05-001 / MSM-07-005 cascade, run when the case owner activates
        revision *revised_embargo_id* in place of the previous active embargo
        (``REVISE → ACTIVE`` with ``active_embargo`` changing); *ends_no_later*
        is :meth:`_revision_ends_no_later`'s answer, taken before the case was
        mutated:

        - B ends no later than A: every signatory to A is carried over as a
          signatory to B (:meth:`_carry_signatories_over`); nobody lapses.
        - B ends later than A: every ``SIGNATORY`` whose list lacks B moves
          to ``LAPSED`` (:meth:`_cascade_pec_revise`); those with B stay.
        - Either arm: a participant in any other state (``INVITED``,
          ``UNBOUND``, ``LAPSED``) whose list already holds B advances to
          ``SIGNATORY`` via ``ACCEPT`` — it accepted the embargo now in force.
        """
        changes: list[ParticipantPECChange] = []
        if ends_no_later:
            self._carry_signatories_over(
                case, revised_embargo_id=revised_embargo_id
            )
        else:
            changes.extend(
                self._cascade_pec_revise(
                    case, revised_embargo_id=revised_embargo_id
                )
            )
        changes.extend(
            self._cascade_pec(
                case,
                trigger=PEC_Trigger.ACCEPT,
                select=lambda p: (
                    p.embargo_consent_state in _ACCEPTABLE_STATES
                    and revised_embargo_id in p.accepted_embargo_ids
                ),
            )
        )
        logger.info(
            "Re-evaluated consent on case '%s' against embargo '%s' (%s);"
            " %d participant state change(s)",
            _as_id(case),
            revised_embargo_id,
            (
                "shorter or equal — signatories carried over"
                if ends_no_later
                else "longer — non-accepting signatories lapsed"
            ),
            len(changes),
        )
        return changes
