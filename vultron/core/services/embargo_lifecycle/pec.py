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
a shorter revision.  Consent is per (participant, embargo) (ADR-0120,
CM-10-001, CM-18-001): each participant holds one row per embargo it was asked
about, "signatory" is the row for the active embargo saying ``ACCEPTED``, and a
lapse or an exit is derived from the rows and the case, never written.  Every
helper persists what it changes and reports each row it moved as a
:class:`ParticipantConsentChange`.
"""

import logging
from collections.abc import Iterator

from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.services.embargo_lifecycle.activation_arm import (
    _ActivationArmMixin,
)
from vultron.core.services.embargo_lifecycle.results import (
    ParticipantConsentChange,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
    PEC_Trigger,
)
from vultron.errors import VultronValidationError

logger = logging.getLogger(__name__)


def _consent_change(
    participant_id: str,
    embargo_id: str,
    before: EmbargoConsentState | None,
    participant: CaseParticipant,
) -> ParticipantConsentChange:
    """Describe the row move *participant* just made from *before*."""
    after = participant.consent_for(embargo_id)
    assert after is not None
    return ParticipantConsentChange(
        participant_id=participant_id,
        embargo_id=embargo_id,
        consent_before=before.value if before is not None else None,
        consent_after=after.value,
    )


def _embargo_exited(case: VulnerabilityCase) -> bool:
    """True once the case's embargo was terminated (EM ``EXITED``, terminal).

    Nothing can be consented to after that, so an Accept or Reject that
    arrives late records nothing (ADR-0118, MSM-07-006).
    """
    return case.current_status.em.state == EM.EXITED


class _PecEffectsMixin(_ActivationArmMixin):
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

    def _record_actor_acceptance(
        self,
        case: VulnerabilityCase,
        actor_id: str,
        embargo_id: str,
    ) -> list[ParticipantConsentChange]:
        """Record *actor_id*'s acceptance of *embargo_id*.

        Marks the row for *embargo_id* ``ACCEPTED`` (CM-18-003): always this
        embargo's row, whether it is the embargo in force, a proposed
        revision, or the actor's own proposal (MSM-07-003).  Whether that
        makes the actor a signatory is a lookup of the active embargo, never
        a second write (ADR-0120).

        Idempotent (CM-13-005): an ``ACCEPTED`` row changes nothing and
        reports nothing.  A ``DECLINED`` row records nothing: ``ACCEPT`` is
        not legal from it (CM-18-003), and accepting here would let the
        content gate (CM-10-004) admit an actor that has declined; it is
        re-invited first (``DECLINED → INVITED``).  Once the embargo has
        terminated nothing is recorded either, and nobody can be invited back
        into it (ADR-0118).
        """
        resolved = self._participant_for_actor(case, actor_id, "acceptance")
        if resolved is None:
            return []
        participant_id, participant = resolved

        if _embargo_exited(case):
            logger.info(
                "Embargo on case '%s' has terminated; actor '%s' acceptance"
                " of embargo '%s' binds nothing (ADR-0118)",
                _as_id(case),
                actor_id,
                embargo_id,
            )
            return []
        before = participant.consent_for(embargo_id)
        if before == EmbargoConsentState.ACCEPTED:
            return []
        if not participant.accepts_pec_trigger(embargo_id, PEC_Trigger.ACCEPT):
            logger.info(
                "Actor '%s' is %s on embargo '%s' of case '%s'; its"
                " acceptance binds nothing (CM-18-003)",
                actor_id,
                before,
                embargo_id,
                _as_id(case),
            )
            return []
        participant.apply_pec_transition(embargo_id, PEC_Trigger.ACCEPT)
        self._persistence.save(participant)
        return [
            _consent_change(participant_id, embargo_id, before, participant)
        ]

    def _record_actor_rejection(
        self,
        case: VulnerabilityCase,
        actor_id: str,
        embargo_id: str,
        *,
        withdrawal: bool,
    ) -> list[ParticipantConsentChange]:
        """Record *actor_id*'s rejection of *embargo_id* (MSM-07-004).

        Marks the row for *embargo_id* ``DECLINED`` — an ``EXPIRED`` one
        included, since a late explicit Reject is an answer (ADR-0118).  The
        same write serves both kinds of Reject: refusing a *proposed* embargo
        leaves the actor's row for the embargo in force untouched, so a
        signatory stays a signatory to it (refusing proposed terms is not
        withdrawing from the embargo in force), while a Reject of the *active*
        embargo is a withdrawal from it (ADR-0093) and the active row is the
        one that becomes ``DECLINED``.

        With *withdrawal* set, every open proposal the actor had accepted is
        declined too: a case has one active embargo, so every open proposal is
        a revision of it (ADR-0113), and an actor that has left the embargo
        has left its revisions — otherwise a ``DECLINED`` actor could still
        hold an ``ACCEPTED`` row for a revision that later activates and be
        admitted by the content gate (CM-10-004) while having withdrawn.  Only
        rows it had *accepted* are declined: a revision it was merely invited
        to stays answerable.

        Idempotent (CM-13-005): an already-``DECLINED`` row changes nothing
        and reports nothing.  Nothing is recorded once the embargo has
        terminated (ADR-0118).
        """
        resolved = self._participant_for_actor(case, actor_id, "rejection")
        if resolved is None or _embargo_exited(case):
            return []
        participant_id, participant = resolved

        targets = [embargo_id]
        if withdrawal:
            targets.extend(
                open_id
                for open_id in case.proposed_embargo_ids
                if open_id != embargo_id
                and participant.consent_for(open_id)
                == EmbargoConsentState.ACCEPTED
            )
        changes: list[ParticipantConsentChange] = []
        for target in targets:
            before = participant.consent_for(target)
            if participant.apply_pec_transition_if_legal(
                target, PEC_Trigger.DECLINE
            ):
                changes.append(
                    _consent_change(
                        participant_id, target, before, participant
                    )
                )
        if changes:
            self._persistence.save(participant)
        return changes

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
        self,
        case: VulnerabilityCase,
        actor_id: str,
        embargo_id: str,
        *,
        is_active: bool,
    ) -> list[ParticipantConsentChange]:
        """The whole MSM-07-004 consent effect of *actor_id* rejecting *embargo_id*.

        *is_active* is :meth:`_assert_rejectable`'s classification, taken by
        the caller before any write (and before the owner's decision prunes
        the proposal): the Reject withdraws from the active embargo or refuses
        proposed terms.  The owner's EJ — the owner refusing a proposed
        revision while an embargo is in force — changes nobody's record, the
        owner's included: the owner is keeping the prior terms, not declining
        them.  Every other Reject is recorded by
        :meth:`_record_actor_rejection`; with *no* embargo in force a Reject of
        one proposal declines that proposal's row only, since it is not a
        withdrawal from anything (CM-18-001).  Shared by ``reject_embargo_invite``
        and ``record_embargo_rejection`` so the two sides cannot drift.
        """
        nothing_in_force = case.active_embargo_id is None
        is_owner = _as_id(case.attributed_to) == actor_id
        if is_owner and not is_active and not nothing_in_force:
            logger.info(
                "Owner '%s' rejected proposed revision '%s' on case '%s';"
                " no consent record changes (EJ)",
                actor_id,
                embargo_id,
                _as_id(case),
            )
            return []
        return self._record_actor_rejection(
            case,
            actor_id,
            embargo_id,
            withdrawal=is_active,
        )
