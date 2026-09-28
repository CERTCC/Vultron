#!/usr/bin/env python
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
"""Use cases for the Case Owner / CASE_MANAGER Offer(CaseParticipant) round-trip.

Covers the three new semantics defined in ISSUE-1332:

- :class:`OfferCaseParticipantReceivedUseCase` — Case Owner received
  ``Offer(CaseParticipant)`` from the CASE_MANAGER (CM-16-003/CM-16-004).
- :class:`AcceptOfferCaseParticipantReceivedUseCase` — the CASE_MANAGER
  received ``Accept(Offer(CaseParticipant))`` from the Case Owner (CM-16-006).
- :class:`RejectOfferCaseParticipantReceivedUseCase` — the CASE_MANAGER
  received ``Reject(Offer(CaseParticipant))`` from the Case Owner (CM-16-007).

Who may act is decided in the tree (BT-17-001) and reported by the handler
(HP-01-005): the Accept and Reject effects are the CASE_MANAGER's, and an
``Offer(CaseParticipant)`` is for the addressee it names.  Any other receiver
of a copy refuses (#3752).
"""

import logging
from typing import TYPE_CHECKING

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.suggest_actor_tree import (
    create_accept_actor_recommendation_received_tree,
    create_receive_offer_case_participant_tree,
    create_reject_actor_recommendation_received_tree,
)
from vultron.core.models.events.actor import (
    AcceptOfferCaseParticipantReceivedEvent,
    OfferCaseParticipantReceivedEvent,
    RejectOfferCaseParticipantReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.use_cases._helpers import (
    is_recipient,
    resolve_receiving_actor_id,
)
from vultron.core.use_cases.received._bt_verdict import (
    not_case_manager,
    not_case_manager_refusal,
    verdict_from_bt,
)
from vultron.enums.roles import serialize_roles

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


class OfferCaseParticipantReceivedUseCase:
    """Case Owner received Offer(CaseParticipant) from the CASE_MANAGER.

    Commits a canonical ``CaseLedgerEntry`` for the received Offer
    (CM-16-003/CM-16-004, ADR-0026) via BTBridge.  That commit is the
    CASE_MANAGER's, and fires on its own loopback copy (OX-12-004).

    The Case Owner is the addressee: the Offer is now pending its decision,
    which it makes as a separate outbound Accept or Reject, so its receipt is
    ``APPLIED`` with nothing more to do here.  A receiver that is neither the
    CASE_MANAGER nor an addressee holds a misaddressed copy and refuses
    (HP-01-005, #3752).
    """

    def __init__(
        self,
        dl: CasePersistence,
        request: OfferCaseParticipantReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._trigger_activity = trigger_activity

    def execute(self) -> HandlerResult:
        request = self._request
        activity_id = request.activity_id
        case_id = request.target_id

        if not case_id:
            logger.warning(
                "OfferCaseParticipantReceived: missing case_id in event '%s'"
                " — refusing",
                activity_id,
            )
            return HandlerResult.refused(
                "Offer(CaseParticipant) names no case"
            )

        local_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )

        tree = create_receive_offer_case_participant_tree(
            case_id=case_id,
        )
        bridge = BTBridge(
            datalayer=self._dl, trigger_activity=self._trigger_activity
        )
        result = bridge.execute_with_setup(
            tree, actor_id=local_actor_id, activity=request
        )
        verdict = verdict_from_bt(
            tree, result, label="ReceiveOfferCaseParticipantBT"
        )
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "ReceiveOfferCaseParticipantBT refused '%s': %s",
                activity_id,
                verdict.reason,
            )
            return verdict
        if not_case_manager(tree):
            # The ledger commit is this tree's only work, and it is the
            # CASE_MANAGER's; a missing case also fails that gate (rule 3).
            if self._dl.read(case_id) is None:
                return HandlerResult.refused(f"unknown case '{case_id}'")
            if is_recipient(local_actor_id, request.activity):
                # The addressee (the Case Owner): the Offer is now theirs
                # to decide, by a separate outbound Accept or Reject.
                return HandlerResult.applied()
            verdict = HandlerResult.refused(
                f"'{local_actor_id}' is neither the CASE_MANAGER nor an"
                f" addressee of Offer(CaseParticipant) for case '{case_id}'"
            )
            logger.warning(
                "ReceiveOfferCaseParticipantBT refused '%s': %s",
                activity_id,
                verdict.reason,
            )
        return verdict


class AcceptOfferCaseParticipantReceivedUseCase:
    """The CASE_MANAGER received Accept(Offer(CaseParticipant)) from the Case Owner.

    Delegates to :func:`create_accept_actor_recommendation_received_tree` via
    BTBridge to commit the ledger entry, notify the recommender, and invite the
    recommended actor (CM-16-006, ADR-0026).  Those effects are gated on the
    receiving actor holding ``CVDRole.CASE_MANAGER`` (BT-17-001); any other
    receiver refuses (HP-01-005, #3752).
    """

    def __init__(
        self,
        dl: CasePersistence,
        request: AcceptOfferCaseParticipantReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._trigger_activity = trigger_activity

    def execute(self) -> HandlerResult:
        request = self._request
        activity_id = request.activity_id
        case_id = request.target_id or request.inner_target_id
        inner_offer = getattr(request.activity, "object_", None)
        participant_obj = getattr(inner_offer, "object_", None)
        raw_invitee = getattr(participant_obj, "attributed_to", None)
        invitee_id = getattr(raw_invitee, "id_", raw_invitee)
        raw_recommendation_id = getattr(inner_offer, "origin", None)
        recommendation_id = getattr(
            raw_recommendation_id, "id_", raw_recommendation_id
        )
        recommender_id = None
        if recommendation_id and case_id:
            case = self._dl.read_case(case_id)
            if case is not None:
                recommender_id = case.recommendation_recommender_index.get(
                    recommendation_id
                )

        # Read the stored Offer (written by offer_actor_to_case()) to get the
        # trusted roles. Do NOT use the embedded CaseParticipant from the
        # received Accept — the accepting actor may have modified it or may
        # have sent only a bare ID reference (ISSUE-1745).
        offer_roles: list | None = None
        raw_offer_id = getattr(inner_offer, "id_", None)
        offer_id = raw_offer_id if isinstance(raw_offer_id, str) else None
        if offer_id:
            stored_offer = self._dl.read(offer_id)
            stored_participant = getattr(stored_offer, "object_", None)
            # AKM-03-001: dehydration stores object_ as a bare ID string;
            # follow the reference to retrieve the full as_CaseParticipant.
            if isinstance(stored_participant, str):
                stored_participant = self._dl.read(stored_participant)
            raw_roles = getattr(stored_participant, "roles", None)
            if isinstance(raw_roles, list) and raw_roles:
                offer_roles = serialize_roles(raw_roles)

        if not case_id or not invitee_id:
            logger.warning(
                "AcceptOfferCaseParticipantReceived: missing case_id or"
                " invitee_id in event '%s' — refusing",
                activity_id,
            )
            return HandlerResult.refused(
                "Accept(Offer(CaseParticipant)) is missing its case id or"
                " invitee id"
            )

        local_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )

        tree = create_accept_actor_recommendation_received_tree(
            recommendation_id=recommendation_id or "",
            recommender_id=recommender_id or "",
            invitee_id=invitee_id,
            case_id=case_id,
            roles=offer_roles,
        )
        bridge = BTBridge(
            datalayer=self._dl, trigger_activity=self._trigger_activity
        )
        result = bridge.execute_with_setup(
            tree, actor_id=local_actor_id, activity=request
        )
        verdict = verdict_from_bt(
            tree, result, label="AcceptActorRecommendationBT"
        )
        if verdict.disposition is not HandlerDisposition.REFUSED:
            refusal = not_case_manager_refusal(tree, self._dl, case_id)
            if refusal is not None:
                verdict = refusal
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "AcceptActorRecommendationBT refused '%s': %s",
                activity_id,
                verdict.reason,
            )
        return verdict


class RejectOfferCaseParticipantReceivedUseCase:
    """The CASE_MANAGER received Reject(Offer(CaseParticipant)) from the Case Owner.

    Delegates to :func:`create_reject_actor_recommendation_received_tree` via
    BTBridge to commit the ledger entry and notify the original recommender
    (CM-16-007, ADR-0026).  The notification is gated on the receiving actor
    holding ``CVDRole.CASE_MANAGER`` (BT-17-001); any other receiver refuses
    (HP-01-005, #3752).
    """

    def __init__(
        self,
        dl: CasePersistence,
        request: RejectOfferCaseParticipantReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._trigger_activity = trigger_activity

    def execute(self) -> HandlerResult:
        request = self._request
        activity_id = request.activity_id
        case_id = request.target_id
        inner_offer = getattr(request.activity, "object_", None)
        participant_obj = getattr(inner_offer, "object_", None)
        raw_invitee = getattr(participant_obj, "attributed_to", None)
        recommended_id = getattr(raw_invitee, "id_", None) or request.object_id
        raw_recommendation_id = getattr(inner_offer, "origin", None)
        recommendation_id = getattr(
            raw_recommendation_id, "id_", raw_recommendation_id
        )
        recommender_id = None
        if recommendation_id and case_id:
            case = self._dl.read_case(case_id)
            if case is not None:
                recommender_id = case.recommendation_recommender_index.get(
                    recommendation_id
                )

        if not case_id:
            logger.warning(
                "RejectOfferCaseParticipantReceived: missing case_id in"
                " event '%s' — refusing",
                activity_id,
            )
            return HandlerResult.refused(
                "Reject(Offer(CaseParticipant)) names no case"
            )

        local_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )

        tree = create_reject_actor_recommendation_received_tree(
            recommendation_id=recommendation_id or "",
            recommender_id=recommender_id or "",
            recommended_id=recommended_id or "",
            case_id=case_id,
        )
        bridge = BTBridge(
            datalayer=self._dl, trigger_activity=self._trigger_activity
        )
        result = bridge.execute_with_setup(
            tree, actor_id=local_actor_id, activity=request
        )
        verdict = verdict_from_bt(
            tree, result, label="RejectActorRecommendationBT"
        )
        if verdict.disposition is not HandlerDisposition.REFUSED:
            refusal = not_case_manager_refusal(tree, self._dl, case_id)
            if refusal is not None:
                verdict = refusal
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "RejectActorRecommendationBT refused '%s': %s",
                activity_id,
                verdict.reason,
            )
        return verdict
