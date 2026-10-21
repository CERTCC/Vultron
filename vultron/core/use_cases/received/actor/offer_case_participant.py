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
of a copy refuses at the tree's addressee door guard (#3752).
"""

import logging
from typing import TYPE_CHECKING, ClassVar

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
    resolve_receiving_actor_id,
)
from vultron.core.use_cases.received._bt_verdict import (
    case_manager_verdict,
    not_case_manager,
    verdict_from_bt,
)

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)

logger = logging.getLogger(__name__)


class OfferCaseParticipantReceivedUseCase:
    """Case Owner received Offer(CaseParticipant) from the CASE_MANAGER.

    Commits a canonical ``CaseLedgerEntry`` for the received Offer
    (CM-16-003/CM-16-004, ADR-0026) via BTBridge.  That commit is the
    CASE_MANAGER's and runs only where the receiving actor holds the role —
    a Case Owner that also manages its case receives the Offer in ``to``
    over the ordinary delivery path (ADR-0109; the former self-``cc:``
    copy is retired).

    The Case Owner is the addressee: the Offer is now pending its decision,
    which it makes as a separate outbound Accept or Reject, so its receipt is
    ``APPLIED`` with nothing more to do here.  A receiver the Offer is not
    addressed to holds a misaddressed copy, which the tree's addressee door
    guard refuses (HP-01-005, #3752).
    """

    sender_entitlement: ClassVar[SenderRule] = SenderRule.in_case(
        SenderEntitlementKind.CASE_MANAGER
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: OfferCaseParticipantReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
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
            sender_id=request.actor_id,
            sender_rule=self.sender_entitlement,
        )
        bridge = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
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
            # Past the tree's door and sender guards, the Offer is addressed
            # to this store, by name or as an active participant of a
            # participants collection its `to` names (HP-01-012).  Only the
            # CASE_MANAGER sends an Offer(CaseParticipant), and it addresses
            # the Case Owner, so a non-CASE_MANAGER store never holds its own
            # copy (HP-01-005).  The Offer is now the addressee's to decide,
            # by a separate outbound Accept or Reject.
            return HandlerResult.applied()
        return verdict


class AcceptOfferCaseParticipantReceivedUseCase:
    """The CASE_MANAGER received Accept(Offer(CaseParticipant)) from the Case Owner.

    Delegates to :func:`create_accept_actor_recommendation_received_tree` via
    BTBridge to commit the ledger entry, notify the recommender, and invite the
    recommended actor (CM-16-006, ADR-0026).  Those effects are gated on the
    receiving actor holding ``CVDRole.CASE_MANAGER`` (BT-17-001); any other
    receiver refuses (HP-01-005, #3752).  The tree looks up the recorded Offer
    the Accept names, so an Accept naming one this CASE_MANAGER never recorded
    is archived and refused in the tree (CLP-10-005, CLP-10-018).
    """

    sender_entitlement: ClassVar[SenderRule] = SenderRule.in_case(
        SenderEntitlementKind.CASE_OWNER
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: AcceptOfferCaseParticipantReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request = request
        self._trigger_activity = trigger_activity

    def execute(self) -> HandlerResult:
        request = self._request
        activity_id = request.activity_id
        case_id = request.target_id or request.inner_target_id

        if not case_id:
            logger.warning(
                "AcceptOfferCaseParticipantReceived: missing case_id in"
                " event '%s' — refusing",
                activity_id,
            )
            return HandlerResult.refused(
                "Accept(Offer(CaseParticipant)) is missing its case id"
            )

        local_actor_id = resolve_receiving_actor_id(
            self._dl, request.receiving_actor_id
        )

        # The tree looks up the Offer the Accept names: the invitee, its
        # roles and the recommender are the recorded Offer's, not the
        # Accept's (CM-16-019, ISSUE-1745).
        tree = create_accept_actor_recommendation_received_tree(
            answer_id=activity_id,
            case_id=case_id,
            sender_id=request.actor_id,
            sender_rule=self.sender_entitlement,
        )
        bridge = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        )
        result = bridge.execute_with_setup(
            tree, actor_id=local_actor_id, activity=request
        )
        verdict = verdict_from_bt(
            tree, result, label="AcceptActorRecommendationBT"
        )
        verdict = case_manager_verdict(tree, verdict, self._dl, case_id)
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
    (HP-01-005, #3752).  The tree looks up the recorded Offer the Reject
    names, so a Reject naming one this CASE_MANAGER never recorded is
    archived and refused in the tree (CLP-10-005, CLP-10-018).
    """

    sender_entitlement: ClassVar[SenderRule] = SenderRule.in_case(
        SenderEntitlementKind.CASE_OWNER
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: RejectOfferCaseParticipantReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
        sync_port: "SyncActivityPort | None" = None,
        wire_render_port: "WireRenderPort | None" = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._request = request
        self._trigger_activity = trigger_activity

    def execute(self) -> HandlerResult:
        request = self._request
        activity_id = request.activity_id
        case_id = request.target_id
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

        # The tree looks up the Offer the Reject names: the recommender and
        # the recommended actor are the recorded Offer's (CM-16-019).
        tree = create_reject_actor_recommendation_received_tree(
            answer_id=activity_id,
            case_id=case_id,
            sender_id=request.actor_id,
            sender_rule=self.sender_entitlement,
        )
        bridge = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        )
        result = bridge.execute_with_setup(
            tree, actor_id=local_actor_id, activity=request
        )
        verdict = verdict_from_bt(
            tree, result, label="RejectActorRecommendationBT"
        )
        verdict = case_manager_verdict(tree, verdict, self._dl, case_id)
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "RejectActorRecommendationBT refused '%s': %s",
                activity_id,
                verdict.reason,
            )
        return verdict
