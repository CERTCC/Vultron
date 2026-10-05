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
the activation arm of the consent bookkeeping — carrying signatories over to
a shorter revision, lapsing non-acceptors of a longer one, and advancing every
participant that already accepted the activated terms (EP-05-001,
MSM-07-005).  The per-record helpers and the cascades it composes live in the
parent mixin.
"""

import logging

from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.services.embargo_lifecycle.pec import (
    _ACCEPTABLE_STATES,
    _PecEffectsMixin,
)
from vultron.core.services.embargo_lifecycle.results import (
    ParticipantPECChange,
)
from vultron.core.states.participant_embargo_consent import (
    PEC,
    PEC_Trigger,
)

logger = logging.getLogger(__name__)


class _PecActivationMixin(_PecEffectsMixin):
    """Consent bookkeeping run when an embargo becomes the one in force."""

    def _carry_signatories_over(
        self, case: VulnerabilityCase, *, revised_embargo_id: str
    ) -> None:
        """Record *revised_embargo_id* on every SIGNATORY's accepted list.

        The shorter arm of EP-05-001: a revision ending no later than the
        embargo it replaces asks nothing new of an existing signatory
        (agreeing to N days is agreeing to every shorter period), so its
        consent carries over by containment (CM-10-001) with no state change.
        Only a ``SIGNATORY`` is carried over, so the containment argument is
        always about consent the participant itself gave.
        """
        for _participant_id, participant in self._each_participant(case):
            if participant.embargo_consent_state != PEC.SIGNATORY.value:
                continue
            if participant.add_accepted_embargo(revised_embargo_id):
                self._persistence.save(participant)

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
          ``UNBOUND``, ``LAPSED``, ``EXPIRED``) whose list already holds B
          advances to ``SIGNATORY`` via ``ACCEPT`` — it accepted the
          embargo now in force.
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
        changes.extend(self._advance_holders_of(case, revised_embargo_id))
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

    def _advance_holders_of(
        self, case: VulnerabilityCase, embargo_id: str
    ) -> list[ParticipantPECChange]:
        """Advance every non-signatory whose list already holds *embargo_id*.

        Run whenever *embargo_id* becomes the embargo in force — a first
        activation as much as a replacement: a participant in ``UNBOUND``,
        ``INVITED``, ``LAPSED`` or ``EXPIRED`` that holds the id accepted
        these terms
        before they were active (a proposer, MSM-07-005; an early acceptor of
        a revision, MSM-07-003) and is a signatory to them now
        (EP-05-001).  ``DECLINED`` is never advanced (CM-18-003).
        """
        return self._cascade_pec(
            case,
            trigger=PEC_Trigger.ACCEPT,
            select=lambda p: (
                p.embargo_consent_state in _ACCEPTABLE_STATES
                and embargo_id in p.accepted_embargo_ids
            ),
        )

    def _consent_at_activation(
        self,
        case: VulnerabilityCase,
        *,
        embargo_id: str,
        ends_no_later: bool | None,
    ) -> list[ParticipantPECChange]:
        """Every participant's consent once *embargo_id* is the embargo in force.

        The one consent effect of an activation, shared by the owner path of
        ``accept_embargo_invite`` and by ``activate_embargo`` so the two
        cannot drift.  *ends_no_later* is ``None`` for a first activation
        (``PROPOSED → ACTIVE``, nothing replaced) and otherwise
        :meth:`_revision_ends_no_later`'s answer for the embargo replaced,
        taken before the case was mutated.

        - Replacing A with B is the owner's acceptance of B: the owner's record
          gains B first, so the owner is never lapsed by its own activation;
          then :meth:`_reevaluate_consent_at_activation` carries signatories
          over or lapses the non-acceptors (EP-05-001, MSM-07-005).
        - On every activation, first or replacement, every non-signatory that
          already holds B advances (:meth:`_advance_holders_of`) — without
          it a participant that proposed the first embargo would hold the
          active id while its state said otherwise, and the content gate
          (CM-10-004) and ``embargo_adherence`` would disagree.
        """
        if ends_no_later is None:
            return self._advance_holders_of(case, embargo_id)
        changes: list[ParticipantPECChange] = []
        owner_id = _as_id(case.attributed_to)
        if owner_id is not None and owner_id in case.actor_participant_index:
            changes.extend(
                self._record_actor_pec_acceptance(case, owner_id, embargo_id)
            )
        changes.extend(
            self._reevaluate_consent_at_activation(
                case,
                revised_embargo_id=embargo_id,
                ends_no_later=ends_no_later,
            )
        )
        return changes
