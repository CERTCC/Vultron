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
"""Use cases for Case Owner and CaseActor Offer(CaseParticipant) round-trip.

Covers the three new semantics defined in ISSUE-1332:

- :class:`OfferCaseParticipantReceivedUseCase` — Case Owner received
  ``Offer(CaseParticipant)`` from the CaseActor (CM-16-003/CM-16-004).
- :class:`AcceptOfferCaseParticipantReceivedUseCase` — CaseActor received
  ``Accept(Offer(CaseParticipant))`` from the Case Owner (CM-16-006).
- :class:`RejectOfferCaseParticipantReceivedUseCase` — CaseActor received
  ``Reject(Offer(CaseParticipant))`` from the Case Owner (CM-16-007).
"""

import logging
from typing import TYPE_CHECKING

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.suggest_actor_tree import (
    create_accept_actor_recommendation_received_tree,
    create_receive_offer_case_participant_tree,
    create_reject_actor_recommendation_received_tree,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.events.actor import (
    AcceptOfferCaseParticipantReceivedEvent,
    OfferCaseParticipantReceivedEvent,
    RejectOfferCaseParticipantReceivedEvent,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.use_cases.received.sync import _find_local_actor_id

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


class OfferCaseParticipantReceivedUseCase:
    """Case Owner received Offer(CaseParticipant) from the CaseActor.

    Commits a canonical ``CaseLedgerEntry`` for the received Offer
    (CM-16-003/CM-16-004, ADR-0026) via BTBridge.
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

    def execute(self) -> None:
        request = self._request
        activity_id = request.activity_id
        case_id = request.target_id

        if not case_id:
            logger.warning(
                "OfferCaseParticipantReceived: missing case_id in event '%s'"
                " — skipping",
                activity_id,
            )
            return

        local_actor_id = _find_local_actor_id(self._dl)
        if local_actor_id is None:
            logger.warning(
                "OfferCaseParticipantReceived: no local actor found"
                " — skipping event '%s'",
                activity_id,
            )
            return

        tree = create_receive_offer_case_participant_tree(
            case_id=case_id,
        )
        bridge = BTBridge(
            datalayer=self._dl, trigger_activity=self._trigger_activity
        )
        bridge.execute_with_setup(
            tree, actor_id=local_actor_id, activity=request
        )


class AcceptOfferCaseParticipantReceivedUseCase:
    """CaseActor received Accept(Offer(CaseParticipant)) from the Case Owner.

    Delegates to :func:`create_accept_actor_recommendation_received_tree` via
    BTBridge to commit the ledger entry, notify the recommender, and invite the
    recommended actor (CM-16-006, ADR-0026).
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

    def execute(self) -> None:
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
            case = self._dl.read(case_id)
            if isinstance(case, VulnerabilityCase):
                recommender_id = case.recommendation_recommender_index.get(
                    recommendation_id
                )

        if not case_id or not invitee_id:
            logger.warning(
                "AcceptOfferCaseParticipantReceived: missing case_id or"
                " invitee_id in event '%s' — skipping",
                activity_id,
            )
            return

        local_actor_id = _find_local_actor_id(self._dl)
        if local_actor_id is None:
            logger.warning(
                "AcceptOfferCaseParticipantReceived: no local actor found"
                " — skipping event '%s'",
                activity_id,
            )
            return

        tree = create_accept_actor_recommendation_received_tree(
            recommendation_id=recommendation_id or "",
            recommender_id=recommender_id or "",
            invitee_id=invitee_id,
            case_id=case_id,
        )
        bridge = BTBridge(
            datalayer=self._dl, trigger_activity=self._trigger_activity
        )
        bridge.execute_with_setup(
            tree, actor_id=local_actor_id, activity=request
        )


class RejectOfferCaseParticipantReceivedUseCase:
    """CaseActor received Reject(Offer(CaseParticipant)) from the Case Owner.

    Delegates to :func:`create_reject_actor_recommendation_received_tree` via
    BTBridge to commit the ledger entry and notify the original recommender
    (CM-16-007, ADR-0026).
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

    def execute(self) -> None:
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
            case = self._dl.read(case_id)
            if isinstance(case, VulnerabilityCase):
                recommender_id = case.recommendation_recommender_index.get(
                    recommendation_id
                )

        if not case_id:
            logger.warning(
                "RejectOfferCaseParticipantReceived: missing case_id in"
                " event '%s' — skipping",
                activity_id,
            )
            return

        local_actor_id = _find_local_actor_id(self._dl)
        if local_actor_id is None:
            logger.warning(
                "RejectOfferCaseParticipantReceived: no local actor found"
                " — skipping event '%s'",
                activity_id,
            )
            return

        tree = create_reject_actor_recommendation_received_tree(
            recommendation_id=recommendation_id or "",
            recommender_id=recommender_id or "",
            recommended_id=recommended_id or "",
            case_id=case_id,
        )
        bridge = BTBridge(
            datalayer=self._dl, trigger_activity=self._trigger_activity
        )
        bridge.execute_with_setup(
            tree, actor_id=local_actor_id, activity=request
        )
