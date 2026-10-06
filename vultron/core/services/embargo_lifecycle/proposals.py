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

"""Proposal-phase EM operations: ``propose_embargo`` and
``abandon_embargo_proposals``.

A proposal (first or revision) drives the shared EM machine and records the
proposer's own consent to the terms it proposed; it changes nobody else's
consent (EP-05-002).  Once the case is public, exploited or attacked while
EM is ``PROPOSED`` the proposals are abandoned rather than answered
(EMB-16-001).  The answers to a proposal — ``accept_embargo_invite`` and
``reject_embargo_invite`` — live in ``answers.py``.
"""

import logging

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.dimensions import EmDimension
from vultron.core.services.embargo_lifecycle.pec_activation import (
    _PecActivationMixin,
)
from vultron.core.services.embargo_lifecycle.results import (
    EmbargoLifecycleResult,
    ParticipantConsentChange,
    TransitionMode,
)
from vultron.core.states.em import EM, EM_Trigger
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronValidationError,
)

logger = logging.getLogger(__name__)


def _assert_abandonable(
    case: VulnerabilityCase, embargo_ids: list[str], em_before: EM
) -> None:
    """Raise unless the ``STRICT`` abandonment of *embargo_ids* is licensed.

    Every id must be an open proposal and EM must be ``PROPOSED``.  The P/X/A
    signal that licenses the abandonment is the caller's to detect
    (EMB-16-001): it may arrive in a participant's status before the case's
    own P/X/A moves, so the case's P/X/A is not checked here.
    """
    unknown = [i for i in embargo_ids if i not in case.proposed_embargo_ids]
    if not embargo_ids or unknown:
        raise VultronValidationError(
            f"Cannot abandon embargo proposals {unknown or embargo_ids}"
            f" on case '{case.id_}': not open proposals of the case."
        )
    if em_before != EM.PROPOSED:
        raise VultronInvalidStateTransitionError(
            f"Cannot abandon embargo proposals on case '{case.id_}':"
            f" EM state '{em_before}' is not PROPOSED."
        )


class _ProposalOperationsMixin(_PecActivationMixin):
    """``propose_embargo`` and ``abandon_embargo_proposals``."""

    def propose_embargo(
        self,
        *,
        case_id: str,
        embargo_id: str,
        actor_id: str | None = None,
        transition_mode: TransitionMode = TransitionMode.STRICT,
        em_before: EM | None = None,
    ) -> EmbargoLifecycleResult:
        """Propose or counter-propose an embargo on a case.

        Valid EM transitions (STRICT mode):
            - ``NONE → PROPOSED``  (initial proposal)
            - ``PROPOSED → PROPOSED``    (counter-proposal / idempotent)
            - ``ACTIVE → REVISE``        (revision proposal)
            - ``REVISE → REVISE``        (counter-revision / idempotent)

        A proposal changes **no one's consent to the embargo in force**
        (EP-05-002, ADR-0093): while a revision is merely proposed the prior
        embargo is still in force and every signatory to it stays one.
        Carry-over to a shorter revision happens only when the owner activates
        it (``accept_embargo_invite`` / ``activate_embargo``, EP-05-001).
        Proposing terms is consenting to them, so when *actor_id* is a
        participant of the case its row for the proposed embargo is marked
        ``ACCEPTED`` (MSM-07-005).

        The ``EmbargoEvent`` identified by *embargo_id* MUST already exist in
        the DataLayer before this method is called; the caller is responsible
        for creating it.

        Args:
            case_id: ID of the :class:`~...VulnerabilityCase` to update.
            embargo_id: ID of the pre-existing ``EmbargoEvent`` being proposed.
            actor_id: Optional ID of the proposing actor.  Used for logging and,
                when it names a case participant, to record the proposer's
                consent to the proposed terms; there is no ownership gate.
            transition_mode: ``STRICT`` (default) enforces valid transitions.
                ``OBSERVED`` syncs local state even when the transition would
                not normally be valid, forcing ``PROPOSED`` (or ``REVISE``
                when the local state is ``ACTIVE``/``REVISE``).
            em_before: When provided, the service uses this value directly
                instead of reading it from the case.

        Returns:
            :class:`EmbargoLifecycleResult` describing what changed;
            ``participant_changes`` is always empty.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case.
            VultronInvalidStateTransitionError: If the current EM state does
                not allow a PROPOSE transition (``STRICT`` mode only), or if
                any of P/X/A is set on the case (``STRICT`` mode only,
                per EMB-01-002).
        """
        case = self._read_case(case_id)

        if em_before is None:
            em_before = case.current_status.em.state
        assert em_before is not None

        if transition_mode == TransitionMode.STRICT:
            self._assert_pxa_embargo_eligible(
                case.current_status.pxa.state,
                case_id,
                "propose embargo",
            )

        # OBSERVED fallback: ACTIVE/REVISE stays in REVISE; otherwise PROPOSED
        fallback = (
            EM.REVISE if em_before in (EM.ACTIVE, EM.REVISE) else EM.PROPOSED
        )
        em_after = self._drive_em_transition(
            case_id=case_id,
            em_before=em_before,
            trigger=EM_Trigger.PROPOSE,
            transition_mode=transition_mode,
            fallback_dest=fallback,
            actor_id=actor_id,
        )

        case_mutated = False

        if em_after != em_before:
            case.current_status.em = EmDimension(state=em_after)
            case_mutated = True

        # Idempotent append, by validated assignment (the pruner
        # ``discard_proposed_embargo`` writes the same record the same way).
        if embargo_id not in case.proposed_embargo_ids:
            case.proposed_embargoes = [*case.proposed_embargoes, embargo_id]
            case_mutated = True

        if case_mutated:
            self._persistence.save(case)

        # Proposing B is consent to B (ADR-0093).
        self._record_proposer_consent(case, actor_id, embargo_id)

        if em_after != em_before:
            logger.info(
                "Actor '%s' proposed embargo '%s' on case '%s' (EM %s → %s)",
                actor_id,
                embargo_id,
                case_id,
                em_before,
                em_after,
            )
        else:
            logger.info(
                "Actor '%s' counter-proposed embargo '%s' on case '%s'"
                " (EM %s, no state change)",
                actor_id,
                embargo_id,
                case_id,
                em_before,
            )

        return EmbargoLifecycleResult(
            em_before=em_before,
            em_after=em_after,
            case_changed=case_mutated,
            case_embargo_changed=False,
            participant_changes=[],
        )

    def abandon_embargo_proposals(
        self,
        *,
        case_id: str,
        embargo_ids: list[str],
        actor_id: str | None = None,
        transition_mode: TransitionMode = TransitionMode.STRICT,
        em_before: EM | None = None,
    ) -> EmbargoLifecycleResult:
        """Abandon open embargo proposals once P/X/A is set (EMB-16-001).

        Nobody answers an abandoned proposal: no embargo can be accepted once
        the vulnerability is public, an exploit is public or attacks are
        observed (EMB-02-002), so every open proposal is decided at once, as
        termination decides every open revision (EP-08-004, ADR-0113).  Each
        named proposal leaves the record of open proposals (EP-08-003); when
        none is left open and EM is ``PROPOSED`` the ``REJECT`` trigger
        drives ``PROPOSED → NONE``.  While another proposal stays open EM
        keeps its state, so a ledger replay that applies one abandonment
        entry per proposal reaches ``NONE`` with the last one.

        The abandonment is no actor's answer, so it changes no participant's
        consent record — exactly as the owner's own ER in ``PROPOSED``
        changes nobody else's (MSM-07-004).

        Args:
            case_id: ID of the ``VulnerabilityCase`` to update.
            embargo_ids: IDs of the proposals to abandon.
            actor_id: The deciding actor, used for logging only.
            transition_mode: ``STRICT`` (the CASE_MANAGER's own decision)
                requires EM ``PROPOSED`` and every id to be an open
                proposal.  ``OBSERVED`` (the ledger replay) skips ids
                that are no longer open and moves EM only from ``PROPOSED``.
            em_before: When provided, the service uses this value directly
                instead of reading it from the case.

        Returns:
            :class:`EmbargoLifecycleResult` describing what changed;
            ``participant_changes`` is always empty.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case.
            VultronValidationError: ``STRICT`` only — an id is not an open
                proposal of the case, or *embargo_ids* is empty.
            VultronInvalidStateTransitionError: ``STRICT`` only — EM is not
                ``PROPOSED``.
        """
        case = self._read_case(case_id)

        if em_before is None:
            em_before = case.current_status.em.state
        assert em_before is not None
        em_after = em_before

        if transition_mode == TransitionMode.STRICT:
            # Every check runs before any write, so a refused abandonment
            # leaves the case untouched (EMB-18-003).
            _assert_abandonable(case, embargo_ids, em_before)

        case_mutated = False
        for embargo_id in embargo_ids:
            if case.discard_proposed_embargo(embargo_id):
                case_mutated = True

        if em_before == EM.PROPOSED and not case.proposed_embargo_ids:
            em_after = self._drive_em_transition(
                case_id=case_id,
                em_before=em_before,
                trigger=EM_Trigger.REJECT,
                transition_mode=transition_mode,
                fallback_dest=EM.NONE,
                actor_id=actor_id,
            )
            if em_after != em_before:
                case.current_status.em = EmDimension(state=em_after)
                case_mutated = True

        if case_mutated:
            self._persistence.save(case)

        logger.info(
            "Actor '%s' abandoned embargo proposal(s) %s on case '%s'"
            " (EM %s → %s, EMB-16-001)",
            actor_id,
            embargo_ids,
            case_id,
            em_before,
            em_after,
        )

        return EmbargoLifecycleResult(
            em_before=em_before,
            em_after=em_after,
            case_changed=case_mutated,
            case_embargo_changed=False,
            participant_changes=[],
        )

    def _record_proposer_consent(
        self,
        case: VulnerabilityCase,
        actor_id: str | None,
        embargo_id: str,
    ) -> list[ParticipantConsentChange]:
        """Record that proposing *embargo_id* is *actor_id*'s consent to it.

        The proposer's row for *embargo_id* is marked ``ACCEPTED`` — only that
        row, so its consent to the embargo in force is untouched (ADR-0093).
        A proposer with no participant record (the case-creation default, for
        one) has no consent to record.
        """
        if actor_id is None or actor_id not in case.actor_participant_index:
            return []
        return self._record_actor_acceptance(case, actor_id, embargo_id)
