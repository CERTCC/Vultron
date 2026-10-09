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

"""Answers to an embargo proposal.

``accept_embargo_invite`` records an ``Accept(Invite(EmbargoEvent))``: the
sender's own consent, whoever sends it, the case owner included (ADR-0122).
``reject_embargo_proposal`` applies the case owner's
``Reject(EmbargoEvent, target=Case)``: its decision for the case, which
rejects the proposal's register entry and writes no consent.  The owner's
``Accept(EmbargoEvent, target=Case)`` is ``activate_embargo``
(:mod:`.activation`).  Consent is per embargo (CM-10-001): a signatory's
answer to a *proposed* revision is about those terms only, and consent to
the active embargo is re-evaluated only when the owner activates a revision
(EP-05-001).  A ``Reject(Invite(EmbargoEvent))`` is recorded by
``record_embargo_rejection`` (:mod:`.consent`).
"""

import logging

from vultron.core.models.embargo_register import rejection_changes
from vultron.core.services.embargo_lifecycle.pec_activation import (
    _PecActivationMixin,
)
from vultron.core.services.embargo_lifecycle.results import (
    EmbargoLifecycleResult,
    TransitionMode,
)
from vultron.errors import VultronValidationError

logger = logging.getLogger(__name__)


class _AnswerOperationsMixin(_PecActivationMixin):
    """``accept_embargo_invite`` and ``reject_embargo_proposal``."""

    def accept_embargo_invite(
        self,
        *,
        case_id: str,
        embargo_id: str,
        actor_id: str,
    ) -> EmbargoLifecycleResult:
        """Record *actor_id*'s acceptance of an embargo Invite.

        ``Accept(Invite(EmbargoEvent))`` is always the sender's own consent,
        the case owner's included (MSM-07-003, ADR-0122): the PEC ``AGREE``
        trigger marks the sender's row for *embargo_id* ``AGREED``,
        whether *embargo_id* is the embargo in force, a proposed revision or
        a first proposal.  It moves no register entry, so EM is unchanged;
        being a signatory is the lookup of the active embargo's row.

        Args:
            case_id: ID of the ``VulnerabilityCase``.
            embargo_id: ID of the ``EmbargoEvent`` being accepted.
            actor_id: ID of the accepting actor.

        Returns:
            :class:`EmbargoLifecycleResult` with EM unchanged; its
            ``participant_changes`` carry the sender's row change, if any.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case.
        """
        case = self._read_case(case_id)
        em_state = case.em_state
        participant_changes = self._record_actor_acceptance(
            case, actor_id, embargo_id
        )
        logger.info(
            "Actor '%s' recorded consent for embargo '%s' on case '%s'"
            " (EM unchanged at %s)",
            actor_id,
            embargo_id,
            case_id,
            em_state,
        )
        return EmbargoLifecycleResult(
            em_before=em_state,
            em_after=em_state,
            case_changed=bool(participant_changes),
            case_embargo_changed=False,
            participant_changes=participant_changes,
        )

    def reject_embargo_proposal(
        self,
        *,
        case_id: str,
        embargo_id: str,
        actor_id: str | None = None,
        transition_mode: TransitionMode = TransitionMode.STRICT,
    ) -> EmbargoLifecycleResult:
        """Apply the case owner's rejection of an open proposal (ER / EJ).

        ``Reject(EmbargoEvent, target=Case)`` (ADR-0122): the proposal's
        register entry is rejected.  EM is derived from what is left:
        ``NONE`` or ``ACTIVE`` when no other proposal is open, and still
        ``PROPOSED``/``REVISE`` while one is (EP-08-001).  No participant's
        consent changes, the owner's included: the owner decides for the
        case and keeps any prior terms; refusing them as a participant is a
        ``Reject(Invite(EmbargoEvent))``.

        Per EMB-04-002, a rejection that would return the case to the prior
        terms is refused in ``STRICT`` mode when P/X/A is set — callers end
        the embargo with :meth:`terminate_active_embargo` (ET) instead.

        Args:
            case_id: ID of the ``VulnerabilityCase`` to update.
            embargo_id: ID of the proposed ``EmbargoEvent`` being rejected.
            actor_id: ID of the deciding actor (logging only).
            transition_mode: ``STRICT`` (default) or ``OBSERVED``.  In
                ``OBSERVED`` mode an embargo that is no longer an open
                proposal here is a no-op: the replica has already applied
                what followed.

        Returns:
            :class:`EmbargoLifecycleResult` describing what changed.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case.
            VultronValidationError: If *embargo_id* is not an open proposal
                of the case (``STRICT`` mode).
            VultronInvalidStateTransitionError: If the rejection would
                return the case to the prior terms with P/X/A set
                (``STRICT`` mode, EMB-04-002).
        """
        case = self._read_case(case_id)
        em_before = case.em_state
        if embargo_id not in case.proposed_embargo_ids:
            if transition_mode == TransitionMode.OBSERVED:
                return self._unchanged_result(em_before)
            raise VultronValidationError(
                f"Embargo '{embargo_id}' is not an open proposal of case"
                f" '{case_id}': nothing to reject."
            )

        # EP-08-001: another open proposal keeps the negotiation open.
        closes_negotiation = case.proposed_embargo_ids == [embargo_id]
        if (
            closes_negotiation
            and transition_mode == TransitionMode.STRICT
            and case.active_embargo_id is not None
        ):
            # EMB-04-002: with P/X/A set the case must be terminated (ET),
            # not returned to the prior terms.
            self._assert_pxa_embargo_eligible(
                case.current_status.pxa.state,
                case_id,
                "reject embargo revision (use terminate_active_embargo when"
                " P/X/A is set)",
            )
        if not self._apply_register_step(
            case,
            rejection_changes(embargo_id),
            transition_mode=transition_mode,
            actor_id=actor_id,
        ):
            return self._unchanged_result(em_before)
        self._persistence.save(case)

        em_after = case.em_state
        logger.info(
            "Case owner '%s' rejected embargo proposal '%s' on case '%s'"
            " (EM %s → %s)",
            actor_id,
            embargo_id,
            case_id,
            em_before,
            em_after,
        )
        return EmbargoLifecycleResult(
            em_before=em_before,
            em_after=em_after,
            case_changed=True,
            case_embargo_changed=False,
        )
