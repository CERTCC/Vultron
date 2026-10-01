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
answer drives the shared EM machine and *decides* the proposal, while any
actor's answer records that actor's own consent on its participant record.
Consent is per embargo (CM-10-001): a signatory's answer to a *proposed*
revision is about those terms only, and consent to the active embargo is
re-evaluated only when the owner activates a revision (EP-05-001).
"""

import logging

from vultron.core.models._helpers import _as_id
from vultron.core.models.dimensions import EmDimension
from vultron.core.services.embargo_lifecycle.pec import (
    _PecEffectsMixin,
)
from vultron.core.services.embargo_lifecycle.results import (
    EmbargoLifecycleResult,
    ParticipantPECChange,
    TransitionMode,
)
from vultron.core.states.em import EM, EM_Trigger

logger = logging.getLogger(__name__)


class _AnswerOperationsMixin(_PecEffectsMixin):
    """``accept_embargo_invite`` and ``reject_embargo_invite``."""

    def accept_embargo_invite(
        self,
        *,
        case_id: str,
        embargo_id: str,
        actor_id: str,
        transition_mode: TransitionMode = TransitionMode.STRICT,
        em_before: EM | None = None,
    ) -> EmbargoLifecycleResult:
        """Accept an embargo invite on a case.

        If *actor_id* is the case owner (``attributed_to``), drives the EM
        state machine ``PROPOSED → ACTIVE`` (or ``REVISE → ACTIVE``) and
        activates the embargo via ``case.set_embargo(embargo_id)``.  When
        that replaces active embargo A with revision B, every participant's
        consent is re-evaluated against B (EP-05-001, MSM-07-005): a B that
        ends no later than A carries every signatory over, a B that ends
        later lapses the signatories whose ``accepted_embargo_ids`` lack it,
        and in either arm a non-signatory whose list already holds B becomes
        ``SIGNATORY``.  The cascade runs in ``STRICT`` and ``OBSERVED`` modes
        alike.

        For any actor (owner or not) *embargo_id* is added idempotently to the
        actor's ``accepted_embargo_ids``.  The PEC ``ACCEPT`` trigger is
        applied only when the accepted embargo is (or, for the owner, is now)
        the case's active embargo; accepting a *proposed* revision while
        another embargo is in force records the id with no state change
        (MSM-07-003) — a ``SIGNATORY`` was and remains a signatory to the
        embargo in force, and a non-signatory advances when B activates.

        Args:
            case_id: ID of the ``VulnerabilityCase`` to update.
            embargo_id: ID of the ``EmbargoEvent`` being accepted.
            actor_id: ID of the accepting actor.
            transition_mode: ``STRICT`` (default) or ``OBSERVED``.
            em_before: When provided, the service uses this value directly
                instead of reading it from the case.

        Returns:
            :class:`EmbargoLifecycleResult` describing what changed.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case, or
                (owner path) the embargo being replaced cannot be read for
                the EP-05-001 comparison.
            VultronInvalidStateTransitionError: If the EM state does not allow
                an ACCEPT transition (``STRICT`` mode, owner only), or if the
                owner would drive EM to ACTIVE but P/X/A is set (``STRICT``
                mode, owner only, per EMB-02-002).  Non-owner callers record
                PEC state only and are not blocked by P/X/A.
        """
        case = self._read_case(case_id)

        if em_before is None:
            em_before = case.current_status.em.state
        assert em_before is not None
        em_after = em_before
        case_mutated = False
        case_embargo_changed = False
        participant_changes: list[ParticipantPECChange] = []

        is_owner = _as_id(case.attributed_to) == actor_id
        active_embargo_id = case.active_embargo_id
        already_active = (
            em_before == EM.ACTIVE and active_embargo_id == embargo_id
        )
        # B is a proposed revision of an embargo A still in force.
        is_revision_of_active = (
            active_embargo_id is not None and active_embargo_id != embargo_id
        )

        # Does this accept replace an embargo already in force?  Decide the
        # EP-05-001 arm *before* anything is written, so an unreadable record
        # fails closed with EM and active_embargo untouched.
        ends_no_later = (
            self._revision_ends_no_later(
                previous_embargo_id=active_embargo_id,
                revised_embargo_id=embargo_id,
            )
            if is_owner
            and active_embargo_id is not None
            and is_revision_of_active
            else None
        )

        if is_owner and not already_active:
            # Guard only applies when owner would drive the EM machine (EMB-02-002).
            if transition_mode == TransitionMode.STRICT:
                self._assert_pxa_embargo_eligible(
                    case.current_status.pxa.state,
                    case_id,
                    "accept embargo invite",
                )
            em_after = self._drive_em_transition(
                case_id=case_id,
                em_before=em_before,
                trigger=EM_Trigger.ACCEPT,
                transition_mode=transition_mode,
                fallback_dest=EM.ACTIVE,
                actor_id=actor_id,
            )
            if em_after != em_before:
                case.current_status.em = EmDimension(state=em_after)
                case_mutated = True
            # Sync active_embargo independently: handle OBSERVED mode where
            # em_after == em_before == ACTIVE but active_embargo points elsewhere
            if active_embargo_id != embargo_id:
                case.set_embargo(embargo_id)
                case_mutated = True
                case_embargo_changed = True

        if is_owner and case.discard_proposed_embargo(embargo_id):
            # The owner's accept decides the proposal: it is no longer open
            # (EP-08-003).  A participant's accept is consent, not a decision.
            case_mutated = True

        if case_mutated:
            self._persistence.save(case)

        # The actor's own consent.  The owner has just made B the active
        # embargo, so its ACCEPT advances; a non-owner accepting a proposed
        # revision records the id only (MSM-07-003).
        participant_changes.extend(
            self._record_actor_pec_acceptance(
                case,
                actor_id,
                embargo_id,
                advance=is_owner or not is_revision_of_active,
            )
        )

        if is_owner and not already_active:
            # B is now the embargo in force: re-evaluate everyone's consent
            # (EP-05-001) and advance the non-signatories that already hold
            # B.  The owner's record already holds B, so it is never lapsed.
            participant_changes.extend(
                self._consent_at_activation(
                    case, embargo_id=embargo_id, ends_no_later=ends_no_later
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
            case_embargo_changed=case_embargo_changed,
            pec_reset=False,
            participant_changes=participant_changes,
        )

    def reject_embargo_invite(
        self,
        *,
        case_id: str,
        embargo_id: str,
        actor_id: str,
        transition_mode: TransitionMode = TransitionMode.STRICT,
        em_before: EM | None = None,
    ) -> EmbargoLifecycleResult:
        """Reject an embargo proposal or revision on a case.

        If *actor_id* is the case owner, drives the EM state machine:
            - ``PROPOSED → NONE``  (initial proposal rejected, ER)
            - ``REVISE → ACTIVE``        (revision rejected, EJ; returns to
              the prior terms)

        Per EMB-04-002, a REVISE rejection that would return the case to ACTIVE
        is blocked in STRICT mode when P/X/A is set — callers must invoke
        :meth:`terminate_active_embargo` (ET) instead.

        The consent effect depends on which embargo the Reject names
        (MSM-07-004, ADR-0093):

        - the case's *active* embargo: ``DECLINE`` from any state including
          ``SIGNATORY`` — consent withdrawal — and the id leaves the actor's
          ``accepted_embargo_ids``;
        - a *proposed* embargo that is not active: the id leaves the list and
          ``DECLINE`` applies only to an actor not yet ``SIGNATORY``; a
          signatory's refusal of proposed terms is not withdrawal from the
          embargo in force;
        - the owner's EJ (``REVISE → ACTIVE``) changes no participant record,
          the owner's included — the owner is keeping the prior terms, not
          declining them.

        Args:
            case_id: ID of the ``VulnerabilityCase`` to update.
            embargo_id: ID of the ``EmbargoEvent`` being rejected.
            actor_id: ID of the rejecting actor.
            transition_mode: ``STRICT`` (default) or ``OBSERVED``.
            em_before: When provided, the service uses this value directly
                instead of reading it from the case.

        Returns:
            :class:`EmbargoLifecycleResult` describing what changed.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case.
            VultronValidationError: If *embargo_id* is neither the active
                embargo nor an open proposal of the case.
            VultronInvalidStateTransitionError: If the EM state does not allow
                a REJECT transition (``STRICT`` mode, owner only), or if the
                case is in REVISE state with P/X/A set (``STRICT`` mode only,
                per EMB-04-002 — use terminate_active_embargo instead).
        """
        case = self._read_case(case_id)

        if em_before is None:
            em_before = case.current_status.em.state
        assert em_before is not None
        em_after = em_before
        case_mutated = False

        is_owner = _as_id(case.attributed_to) == actor_id
        # Classify before anything is written (and before the owner's prune):
        # an unknown embargo is a protocol error (ADR-0093), not a consent
        # change.
        is_active = self._assert_rejectable(case, embargo_id)

        if is_owner:
            # In STRICT mode, block REVISE→ACTIVE when P/X/A is set (EMB-04-002):
            # the case must be terminated (ET), not returned to ACTIVE.
            if (
                transition_mode == TransitionMode.STRICT
                and em_before == EM.REVISE
            ):
                self._assert_pxa_embargo_eligible(
                    case.current_status.pxa.state,
                    case_id,
                    "reject embargo revision (use terminate_active_embargo when P/X/A is set)",
                )
            # OBSERVED fallback: REVISE reject → ACTIVE; otherwise → NONE
            fallback = EM.ACTIVE if em_before == EM.REVISE else EM.NONE
            em_after = self._drive_em_transition(
                case_id=case_id,
                em_before=em_before,
                trigger=EM_Trigger.REJECT,
                transition_mode=transition_mode,
                fallback_dest=fallback,
                actor_id=actor_id,
            )
            if em_after != em_before:
                case.current_status.em = EmDimension(state=em_after)
                case_mutated = True

        # Consent after the EM guards (a refused transition writes nothing).
        # The owner's EJ changes no record (MSM-07-004).
        participant_changes = self._rejection_consent(
            case, actor_id, embargo_id, is_active=is_active
        )

        if is_owner and case.discard_proposed_embargo(embargo_id):
            # The owner's reject decides the proposal (EP-08-003).
            case_mutated = True

        if case_mutated:
            self._persistence.save(case)

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
            pec_reset=False,
            participant_changes=participant_changes,
        )
