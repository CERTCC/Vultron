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
— one actor's record on accept/reject, every participant's on a REVISE
cascade or a termination reset.  Every helper persists what it changes and
reports each change as a :class:`ParticipantPECChange`.
"""

import logging

from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.services.embargo_lifecycle.base import _LifecycleBase
from vultron.core.services.embargo_lifecycle.results import (
    ParticipantPECChange,
)
from vultron.core.states.participant_embargo_consent import (
    PEC,
    PEC_Trigger,
)

logger = logging.getLogger(__name__)


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

    def _record_actor_pec_acceptance(
        self, case: VulnerabilityCase, actor_id: str, embargo_id: str
    ) -> list[ParticipantPECChange]:
        """Update a participant's PEC to SIGNATORY and track the embargo ID.

        Idempotent: if the participant is already ``SIGNATORY``, only
        ``accepted_embargo_ids`` is updated (if needed).
        """
        resolved = self._participant_for_actor(case, actor_id, "acceptance")
        if resolved is None:
            return []
        participant_id, participant = resolved

        pec_before = participant.embargo_consent_state
        changed = False

        if participant.embargo_consent_state not in (
            PEC.SIGNATORY.value,
            PEC.DECLINED.value,
        ):
            participant.apply_pec_transition(PEC_Trigger.ACCEPT)
            changed = True

        if embargo_id not in participant.accepted_embargo_ids:
            participant.accepted_embargo_ids = list(
                dict.fromkeys(participant.accepted_embargo_ids + [embargo_id])
            )
            changed = True

        if not changed:
            return []
        self._persistence.save(participant)
        return [_pec_change(participant_id, pec_before, participant)]

    def _record_actor_pec_rejection(
        self, case: VulnerabilityCase, actor_id: str, embargo_id: str
    ) -> list[ParticipantPECChange]:
        """Update a participant's PEC to DECLINED and remove the embargo ID.

        Idempotent: if the participant is already ``DECLINED``, only
        ``accepted_embargo_ids`` is updated (if needed).
        """
        resolved = self._participant_for_actor(case, actor_id, "rejection")
        if resolved is None:
            return []
        participant_id, participant = resolved

        pec_before = participant.embargo_consent_state
        changed = False

        if participant.embargo_consent_state != PEC.DECLINED.value:
            participant.apply_pec_transition(PEC_Trigger.DECLINE)
            changed = True

        if embargo_id in participant.accepted_embargo_ids:
            participant.accepted_embargo_ids.remove(embargo_id)
            changed = True

        if not changed:
            return []
        self._persistence.save(participant)
        return [_pec_change(participant_id, pec_before, participant)]

    def _cascade_pec(
        self,
        case: VulnerabilityCase,
        *,
        from_state: PEC | None,
        trigger: PEC_Trigger,
    ) -> list[ParticipantPECChange]:
        """Apply *trigger* to every participant of *case* the cascade selects.

        With *from_state* set, only participants currently in that PEC state
        are moved; with ``None``, every participant not already ``UNBOUND``
        is.  Each moved participant is persisted and reported.
        """
        changes: list[ParticipantPECChange] = []
        for entry in case.case_participants:
            participant_id = _as_id(entry)
            if participant_id is None:
                continue
            participant = self._persistence.read(participant_id)
            if not isinstance(participant, CaseParticipant):
                continue
            state = participant.embargo_consent_state
            if from_state is None:
                if state == PEC.UNBOUND.value:
                    continue
            elif state != from_state.value:
                continue
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
            case, from_state=None, trigger=PEC_Trigger.RESET
        )

    def _cascade_pec_revise(
        self, case: VulnerabilityCase
    ) -> list[ParticipantPECChange]:
        """Transition all SIGNATORY participants to LAPSED.

        Called when an embargo transitions to REVISE state, meaning the
        embargo terms are being renegotiated.  Existing signatories temporarily
        lapse until they accept the revised terms.

        Returns a list of :class:`ParticipantPECChange` records for each
        participant whose PEC state was updated.
        """
        return self._cascade_pec(
            case, from_state=PEC.SIGNATORY, trigger=PEC_Trigger.REVISE
        )
