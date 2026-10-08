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

"""Answers to an embargo proposal: ``accept_embargo_invite`` and
``reject_embargo_invite``.

Both have two-audience semantics (MSM-07-003, MSM-07-004): the case owner's
answer *decides* the proposal — ``ACTIVATE`` or ``REJECT`` on its embargo
register entry, from which EM is derived (ADR-0122) — while any actor's
answer records that actor's own consent on its participant record.
Consent is per embargo (CM-10-001): a signatory's answer to a *proposed*
revision is about those terms only, and consent to the active embargo is
re-evaluated only when the owner activates a revision (EP-05-001).
"""

import logging

from vultron.core.models._helpers import _as_id
from vultron.core.models.embargo_register import rejection_changes
from vultron.core.services.embargo_lifecycle.pec_activation import (
    _PecActivationMixin,
)
from vultron.core.services.embargo_lifecycle.results import (
    EmbargoLifecycleResult,
    ParticipantConsentChange,
    TransitionMode,
)

logger = logging.getLogger(__name__)


class _AnswerOperationsMixin(_PecActivationMixin):
    """``accept_embargo_invite`` and ``reject_embargo_invite``."""

    def accept_embargo_invite(
        self,
        *,
        case_id: str,
        embargo_id: str,
        actor_id: str,
        transition_mode: TransitionMode = TransitionMode.STRICT,
    ) -> EmbargoLifecycleResult:
        """Accept an embargo invite on a case.

        If *actor_id* is the case owner (``attributed_to``), activates
        the embargo's register entry, superseding any embargo in force, so EM
        derives ``ACTIVE``.  When that replaces active embargo A with
        revision B, the consent rows are
        settled against B (EP-05-001, MSM-07-005): a B that ends no later than
        A carries every signatory over, and under a longer B the signatories
        who have not accepted it have lapsed by derivation (CM-18-001).  The
        carry-over runs in ``STRICT`` and ``OBSERVED`` modes alike.

        For any actor (owner or not) the PEC ``ACCEPT`` trigger marks the row
        for *embargo_id* ``ACCEPTED`` (MSM-07-003).  There is one rule whether
        *embargo_id* is the embargo in force, a proposed revision, or the
        actor's own proposal: the row is written, and being a signatory is the
        lookup of the active embargo's row (ADR-0122).

        Args:
            case_id: ID of the ``VulnerabilityCase`` to update.
            embargo_id: ID of the ``EmbargoEvent`` being accepted.
            actor_id: ID of the accepting actor.
            transition_mode: ``STRICT`` (default) or ``OBSERVED``.

        Returns:
            :class:`EmbargoLifecycleResult` describing what changed.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case,
                or (owner path, when the accept activates *embargo_id*) the
                embargo being activated or the one it replaces cannot be read
                (EMB-18-003, EP-05-001) — in either mode, before any write.
            VultronValidationError: If (owner path) either embargo record is
                not an ``EmbargoEvent``.
            VultronInvalidStateTransitionError: If the embargo is not an
                open proposal the register can activate (``STRICT`` mode,
                owner only), or if the owner would activate it but P/X/A is
                set (``STRICT`` mode, owner only, per EMB-02-002).  Non-owner callers record
                PEC state only and are not blocked by P/X/A.
        """
        case = self._read_case(case_id)
        em_before = case.em_state
        participant_changes: list[ParticipantConsentChange] = []

        is_owner = _as_id(case.attributed_to) == actor_id
        active_embargo_id = case.active_embargo_id
        activates = is_owner and active_embargo_id != embargo_id

        # The owner's accept activates B: read B (and any embargo A it
        # replaces) and decide the EP-05-001 arm *before* anything is
        # written, so an unreadable record fails closed with the register and
        # consent untouched (EMB-18-003).
        ends_no_later = (
            self._activation_arm(
                previous_embargo_id=active_embargo_id,
                activated_embargo_id=embargo_id,
            )
            if activates
            else None
        )

        case_mutated = False
        if activates:
            # Guard only applies when the owner activates (EMB-02-002).
            if transition_mode == TransitionMode.STRICT:
                self._assert_pxa_embargo_eligible(
                    case.current_status.pxa.state,
                    case_id,
                    "accept embargo invite",
                )
            # The owner's accept decides the proposal: activation takes it
            # out of the open proposals (EP-08-003).
            case_mutated = self._activate_entry(
                case,
                embargo_id,
                transition_mode=transition_mode,
                actor_id=actor_id,
            )
        em_after = case.em_state

        if case_mutated:
            self._persistence.save(case)

        # The actor's own consent: this embargo's row, whichever embargo it
        # is (MSM-07-003).
        participant_changes.extend(
            self._record_actor_acceptance(case, actor_id, embargo_id)
        )

        if case_mutated:
            # B is now the embargo in force: carry A's signatories over to it
            # when it ends no later (EP-05-001).  The owner's row already
            # holds B, so it is never lapsed.
            participant_changes.extend(
                self._consent_at_activation(
                    case,
                    embargo_id=embargo_id,
                    previous_embargo_id=active_embargo_id,
                    ends_no_later=ends_no_later,
                )
            )

        if is_owner and em_after != em_before:
            logger.info(
                "Actor '%s' accepted embargo '%s' on case '%s'"
                " (EM %s → %s; embargo activated)",
                actor_id,
                embargo_id,
                case_id,
                em_before,
                em_after,
            )
        else:
            logger.info(
                "Actor '%s' recorded consent for embargo '%s' on case '%s'"
                " (EM unchanged at %s)",
                actor_id,
                embargo_id,
                case_id,
                em_after,
            )

        return EmbargoLifecycleResult(
            em_before=em_before,
            em_after=em_after,
            case_changed=case_mutated or bool(participant_changes),
            case_embargo_changed=case_mutated,
            participant_changes=participant_changes,
        )

    def reject_embargo_invite(
        self,
        *,
        case_id: str,
        embargo_id: str,
        actor_id: str,
        transition_mode: TransitionMode = TransitionMode.STRICT,
        record_consent: bool = True,
    ) -> EmbargoLifecycleResult:
        """Reject an embargo proposal or revision on a case.

        If *actor_id* is the case owner and the embargo is an open proposal,
        its register entry is rejected (ER, or EJ for a revision).
        EM is derived from what is left: ``NONE`` or ``ACTIVE`` when no other
        proposal is open, and still ``PROPOSED``/``REVISE`` while one is
        (EP-08-001), so the case never leaves negotiation with a proposal
        still awaiting an answer (ADR-0122).

        Per EMB-04-002, a REVISE rejection that would return the case to ACTIVE
        is blocked in STRICT mode when P/X/A is set — callers must invoke
        :meth:`terminate_active_embargo` (ET) instead.

        The consent effect depends on which embargo the Reject names
        (MSM-07-004, ADR-0093):

        - the case's *active* embargo: ``DECLINE`` marks the actor's row for
          it ``DECLINED`` — consent withdrawal, a signatory's included — and
          every open proposal the actor had accepted is declined with it;
        - a *proposed* embargo that is not active: ``DECLINE`` marks that
          embargo's row only; the actor's row for the embargo in force is
          untouched, so a signatory's refusal of proposed terms is not
          withdrawal from it;
        - the owner's EJ (``REVISE → ACTIVE``) changes no participant record,
          the owner's included — the owner is keeping the prior terms, not
          declining them.

        Args:
            case_id: ID of the ``VulnerabilityCase`` to update.
            embargo_id: ID of the ``EmbargoEvent`` being rejected.
            actor_id: ID of the rejecting actor.
            transition_mode: ``STRICT`` (default) or ``OBSERVED``.
            record_consent: ``False`` when the caller has already recorded
                the rejecting actor's consent effect through
                :meth:`record_embargo_rejection` (the received Reject tree
                and its ledger replay), so it is applied once.

        Returns:
            :class:`EmbargoLifecycleResult` describing what changed.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case.
            VultronValidationError: If *embargo_id* is neither the active
                embargo nor an open proposal of the case.
            VultronInvalidStateTransitionError: If the case's owner rejects
                a revision of the embargo in force with P/X/A set
                (``STRICT`` mode only, per EMB-04-002 — use
                terminate_active_embargo instead).
        """
        case = self._read_case(case_id)
        em_before = case.em_state

        is_owner = _as_id(case.attributed_to) == actor_id
        # Classify before anything is written (and before the owner's
        # decision): an unknown embargo is a protocol error (ADR-0093), not a
        # consent change.
        is_active = self._assert_rejectable(case, embargo_id)
        decides = is_owner and not is_active
        # EP-08-001: another open proposal keeps the negotiation open, so the
        # owner's Reject of this one leaves EM at REVISE.
        closes_negotiation = all(
            open_id == embargo_id for open_id in case.proposed_embargo_ids
        )

        if (
            decides
            and closes_negotiation
            and transition_mode == TransitionMode.STRICT
            and case.active_embargo_id is not None
        ):
            # EMB-04-002: with P/X/A set the case must be terminated (ET),
            # not returned to the prior terms.
            self._assert_pxa_embargo_eligible(
                case.current_status.pxa.state,
                case_id,
                "reject embargo revision (use terminate_active_embargo when P/X/A is set)",
            )
        case_mutated = decides and self._apply_register_step(
            case,
            rejection_changes(embargo_id),
            transition_mode=transition_mode,
            actor_id=actor_id,
        )

        # Consent after the register guards (a refused step writes nothing).
        # The owner's EJ changes no record (MSM-07-004).
        participant_changes = (
            self._rejection_consent(
                case, actor_id, embargo_id, is_active=is_active
            )
            if record_consent
            else []
        )

        if case_mutated:
            self._persistence.save(case)

        em_after = case.em_state
        logger.info(
            "Actor '%s' rejected embargo '%s' on case '%s' (EM %s → %s)",
            actor_id,
            embargo_id,
            case_id,
            em_before,
            em_after,
        )

        return EmbargoLifecycleResult(
            em_before=em_before,
            em_after=em_after,
            case_changed=case_mutated or bool(participant_changes),
            case_embargo_changed=False,
            participant_changes=participant_changes,
        )
