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

"""PEC consent effects of an embargo becoming the one in force.

Split from :mod:`~vultron.core.services.embargo_lifecycle.pec` (CS-18-001):
the activation arm of the consent bookkeeping.  Consent is per embargo
(ADR-0122), so activation needs almost no bookkeeping: whoever holds an
``ACCEPTED`` row for the activated embargo is its signatory by lookup, and
whoever does not has lapsed by derivation (CM-18-001).  The one write left is
containment: a revision that ends no later than the embargo it replaces asks
nothing new of an existing signatory, so their acceptance is carried over to it
(EP-05-001, CM-10-001).
"""

import logging

from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.services.embargo_lifecycle.pec import (
    _consent_change,
    _PecEffectsMixin,
    owner_declined_embargo,
)
from vultron.core.services.embargo_lifecycle.results import (
    ParticipantConsentChange,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
    PEC_Trigger,
)
from vultron.errors import VultronInvalidStateTransitionError

logger = logging.getLogger(__name__)


class _PecActivationMixin(_PecEffectsMixin):
    """Consent bookkeeping run when an embargo becomes the one in force."""

    def _carry_signatories_over(
        self,
        case: VulnerabilityCase,
        *,
        previous_embargo_id: str,
        revised_embargo_id: str,
    ) -> list[ParticipantConsentChange]:
        """Mark *revised_embargo_id* ``ACCEPTED`` for every signatory to the old one.

        The shorter arm of EP-05-001: a revision ending no later than the
        embargo it replaces asks nothing new of an existing signatory
        (agreeing to N days is agreeing to every shorter period), so its
        consent carries over by containment (CM-10-001).  Only a participant
        whose row for *previous_embargo_id* is ``ACCEPTED`` is carried over,
        so the containment argument is always about consent the participant
        itself gave; one that declined the revision keeps that answer.  A
        *longer* revision needs no counterpart: a signatory that has not
        accepted it has lapsed by derivation (:meth:`CaseParticipant.has_lapsed`).
        """
        changes: list[ParticipantConsentChange] = []
        for participant_id, participant in self._each_participant(case):
            if (
                participant.consent_for(previous_embargo_id)
                != EmbargoConsentState.ACCEPTED
            ):
                continue
            before = participant.consent_for(revised_embargo_id)
            if participant.apply_pec_transition_if_legal(
                revised_embargo_id, PEC_Trigger.ACCEPT
            ):
                self._persistence.save(participant)
                changes.append(
                    _consent_change(
                        participant_id, revised_embargo_id, before, participant
                    )
                )
        return changes

    def _assert_owner_may_activate(
        self, case: VulnerabilityCase, embargo_id: str
    ) -> None:
        """Refuse an activation the case owner has declined (ADR-0122).

        Activation records the owner's ``AGREE``, which ``DECLINED`` refuses
        (CM-18-003): an owner that declined the proposal as a participant is
        invited again before it can activate it.  Called before anything is
        written, in either mode, so replay refuses what the CASE_MANAGER
        would have refused.

        Raises:
            VultronInvalidStateTransitionError: If the owner's row for
                *embargo_id* is ``DECLINED``.
        """
        if owner_declined_embargo(self._persistence, case, embargo_id):
            raise VultronInvalidStateTransitionError(
                f"Case owner '{_as_id(case.attributed_to)}' declined embargo"
                f" '{embargo_id}' on case '{_as_id(case)}': it is invited"
                " again before it can activate it (CM-18-003)."
            )

    def _consent_at_activation(
        self,
        case: VulnerabilityCase,
        *,
        embargo_id: str,
        previous_embargo_id: str | None,
        ends_no_later: bool | None,
    ) -> list[ParticipantConsentChange]:
        """The consent rows written once *embargo_id* is the embargo in force.

        The consent effect of the case owner's
        ``Accept(EmbargoEvent, target=Case)`` (ADR-0122).  *ends_no_later* is
        ``None`` for a first activation (``PROPOSED → ACTIVE``, nothing
        replaced) and otherwise :meth:`_revision_ends_no_later`'s answer for
        the embargo replaced, taken before the case was mutated;
        *previous_embargo_id* is that embargo.

        - The activation is the owner's agreement: the owner's row for the
          activated embargo becomes ``ACCEPTED`` unless it already is, so the
          owner is a signatory of what it activated and never lapsed by it.
        - Any other ``ACCEPTED`` row for it already makes its holder a
          signatory (its proposer, an early acceptor), with no advance step.
        - Replacing A with B: a B ending no later than A carries A's
          signatories over (:meth:`_carry_signatories_over`); a longer B
          carries nobody, and the signatories who have not accepted it are
          lapsed by derivation.
        """
        changes: list[ParticipantConsentChange] = []
        owner_id = _as_id(case.attributed_to)
        if owner_id is not None and owner_id in case.actor_participant_index:
            changes.extend(
                self._record_actor_acceptance(case, owner_id, embargo_id)
            )
        if ends_no_later is None or previous_embargo_id is None:
            return changes
        if ends_no_later:
            changes.extend(
                self._carry_signatories_over(
                    case,
                    previous_embargo_id=previous_embargo_id,
                    revised_embargo_id=embargo_id,
                )
            )
        logger.info(
            "Recorded consent on case '%s' for activated embargo '%s' (%s);"
            " %d row change(s)",
            _as_id(case),
            embargo_id,
            (
                "shorter or equal — signatories carried over"
                if ends_no_later
                else "longer — non-accepting signatories have lapsed"
            ),
            len(changes),
        )
        return changes
