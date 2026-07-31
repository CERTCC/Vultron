"""Use case for the canonical role-delegation wire format (ADR-0039).

Handles ``Offer(CaseParticipantRole, target=Actor, context=VulnerabilityCase)``
introduced by ADR-0039 as the replacement for the deprecated
``Offer(VulnerabilityCase, target=CaseParticipant)`` format.
"""

import logging
from typing import TYPE_CHECKING

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.offer_case_manager_role_received_tree import (
    create_offer_case_manager_role_received_tree,
)
from vultron.core.models.events.actor import (
    OfferCaseParticipantRoleReceivedEvent,
)
from vultron.core.models._helpers import _as_id
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.ports.sync_activity import SyncActivityPort

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


class OfferCaseParticipantRoleReceivedUseCase:
    """Handle an incoming ``Offer(CaseParticipantRole, ...)`` (ADR-0039).

    Stores the offer idempotently, then delegates to the same BT that handles
    the deprecated ``OFFER_CASE_MANAGER_ROLE`` flow, since the response
    protocol (auto-accept, ledger commit) is identical.  The ``context`` field
    carries the VulnerabilityCase ID; ``target`` carries the Actor receiving the
    role.

    See SE-08-003, ADR-0039.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: OfferCaseParticipantRoleReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
        sync_port: SyncActivityPort | None = None,
    ) -> None:
        self._dl = dl
        self._request: OfferCaseParticipantRoleReceivedEvent = request
        self._trigger_activity = trigger_activity
        self._sync_port = sync_port

    def execute(self) -> None:
        request = self._request
        receiving_actor_id = request.receiving_actor_id
        if receiving_actor_id is None:
            logger.debug(
                "OfferCaseParticipantRoleReceivedUseCase: missing"
                " receiving_actor_id — skipping (CLP-10-005)"
            )
            return

        offer_id = request.activity_id
        vendor_id = request.actor_id
        # context carries the VulnerabilityCase; target carries the Actor
        case_id = _as_id(getattr(request.activity, "context", None))
        target_id = _as_id(getattr(request.activity, "target", None))

        # ADR-0039: target is an Actor URI; BT expects a CaseParticipant URI.
        # Resolve via actor_participant_index which maps actor_id → participant_id.
        case_obj = self._dl.read(case_id) if case_id else None
        participant_id = (
            getattr(case_obj, "actor_participant_index", {}).get(
                target_id or ""
            )
            or target_id
            or ""
        )

        tree = create_offer_case_manager_role_received_tree(
            offer_id=offer_id,
            offer_obj=request.activity,
            case_id=case_id or "",
            participant_id=participant_id,
            vendor_id=vendor_id or "",
        )
        result = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
        ).execute_with_setup(
            tree=tree,
            actor_id=receiving_actor_id,
            activity=request,
            sync_port=self._sync_port,
        )
        if result.status != Status.SUCCESS:
            logger.debug(
                "OfferCaseParticipantRoleReceivedUseCase: BT did not fully"
                " succeed for offer '%s': %s",
                offer_id,
                BTBridge.get_failure_reason(tree) or result.feedback_message,
            )
