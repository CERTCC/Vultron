"""Use cases for case actor/participant invitation and suggestion activities."""

import logging
from typing import TYPE_CHECKING

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.offer_case_manager_role_received_tree import (
    create_offer_case_manager_role_received_tree,
)
from vultron.core.models.events.actor import (
    AcceptCaseManagerRoleReceivedEvent,
    OfferCaseManagerRoleReceivedEvent,
    RejectCaseManagerRoleReceivedEvent,
)
from vultron.core.models.protocols import is_case_model
from vultron.core.ports.case_persistence import (
    CaseOutboxPersistence,
    CasePersistence,
)
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.states.roles import CVDRole
from vultron.core.use_cases._helpers import (
    _as_id,
    _idempotent_create,
)

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


class OfferCaseManagerRoleReceivedUseCase:
    """Handle an incoming CASE_MANAGER role delegation offer.

    Idempotently stores the incoming Offer activity, then auto-accepts it
    on behalf of the local actor (the Case Actor entity that received the
    Offer).  The Accept is queued to the Case Actor's outbox so the offering
    Vendor receives confirmation.

    After auto-accepting, the CaseActor commits its initialization entry to
    the canonical case ledger (backfill).  This is the correct place for the
    initial ``offer_case_manager_role`` ledger entry: the vendor MUST NOT
    commit canonical entries, and the CaseActor's first protocol-significant
    event is accepting its CASE_MANAGER role delegation.

    See DEMOMA-08-002, DEMOMA-08-003; Issue #469, Issue #1021.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: OfferCaseManagerRoleReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
        sync_port: SyncActivityPort | None = None,
    ) -> None:
        self._dl = dl
        self._request: OfferCaseManagerRoleReceivedEvent = request
        self._trigger_activity = trigger_activity
        self._sync_port = sync_port

    def execute(self) -> None:
        request = self._request
        receiving_actor_id = request.receiving_actor_id
        if receiving_actor_id is None:
            logger.debug(
                "OfferCaseManagerRoleReceivedUseCase: missing"
                " receiving_actor_id — skipping (CLP-10-005)"
            )
            return

        offer_id = request.activity_id
        vendor_id = request.actor_id
        case_id = _as_id(request.activity.object_)
        participant_id = _as_id(request.activity.target)

        tree = create_offer_case_manager_role_received_tree(
            offer_id=offer_id,
            offer_obj=request.activity,
            case_id=case_id or "",
            participant_id=participant_id or "",
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
                "OfferCaseManagerRoleReceivedUseCase: BT did not fully"
                " succeed for offer '%s': %s",
                offer_id,
                BTBridge.get_failure_reason(tree) or result.feedback_message,
            )


class AcceptCaseManagerRoleReceivedUseCase:
    """Handle an incoming acceptance of the CASE_MANAGER role delegation offer.

    The offering actor (Vendor) receives this Accept from the Case Actor.
    After persisting the activity the Vendor bootstraps trust with the
    Reporter by sending ``Create(VulnerabilityCase)`` to the Reporter's inbox.

    See notes/case-bootstrap-trust.md CBT-01; Issue #469.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AcceptCaseManagerRoleReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: AcceptCaseManagerRoleReceivedEvent = request
        self._trigger_activity = trigger_activity

    def execute(self) -> None:
        from vultron.core.use_cases.received.sync import _find_local_actor_id
        from vultron.core.use_cases.triggers._helpers import (
            add_activity_to_outbox,
        )

        request = self._request
        _idempotent_create(
            self._dl,
            request.activity_type,
            request.activity_id,
            request.activity,
            "AcceptCaseManagerRole",
            request.activity_id,
        )
        logger.info(
            "AcceptCaseManagerRoleReceived: actor '%s' accepted CASE_MANAGER"
            " role delegation (inner case: '%s')",
            request.actor_id,
            request.inner_object_id,
        )

        if self._trigger_activity is None:
            logger.warning(
                "AcceptCaseManagerRoleReceived: trigger_activity not available"
                " — skipping trust bootstrap for case '%s'",
                request.inner_object_id,
            )
            return

        case_id = request.case_id
        if not case_id:
            logger.warning(
                "AcceptCaseManagerRoleReceived: missing case_id on request"
                " '%s' — skipping trust bootstrap",
                request.activity_id,
            )
            return

        case = self._dl.read(case_id)
        if not is_case_model(case):
            logger.warning(
                "AcceptCaseManagerRoleReceived: case '%s' not found"
                " — skipping trust bootstrap",
                case_id,
            )
            return

        local_actor_id = request.receiving_actor_id or _find_local_actor_id(
            self._dl
        )
        if local_actor_id is None:
            logger.warning(
                "AcceptCaseManagerRoleReceived: no local actor found"
                " — skipping trust bootstrap for case '%s'",
                case_id,
            )
            return

        # Find the Reporter participant to address the Create(Case) to.
        reporter_id: str | None = None
        for p_id in case.actor_participant_index.values():
            p = self._dl.read(p_id)
            roles = getattr(p, "case_roles", [])
            if CVDRole.REPORTER in roles or CVDRole.FINDER in roles:
                reporter_id = _as_id(getattr(p, "attributed_to", None))
                break

        if not reporter_id:
            logger.warning(
                "AcceptCaseManagerRoleReceived: no Reporter participant found"
                " in case '%s' — skipping trust bootstrap",
                case_id,
            )
            return

        try:
            create_id, _ = self._trigger_activity.create_case(
                case_id=case_id,
                actor=local_actor_id,
                to=[reporter_id],
            )
            add_activity_to_outbox(local_actor_id, create_id, self._dl)
            logger.info(
                "AcceptCaseManagerRoleReceived: sent Create(VulnerabilityCase)"
                " '%s' to Reporter '%s' for case '%s'",
                create_id,
                reporter_id,
                case_id,
            )
        except Exception as exc:
            logger.error(
                "AcceptCaseManagerRoleReceived: error sending trust bootstrap"
                " for case '%s': %s",
                case_id,
                exc,
            )


class RejectCaseManagerRoleReceivedUseCase:
    """Process a Reject(Offer(VulnerabilityCase)) for CASE_MANAGER delegation.

    The offering actor (Vendor) receives this rejection from the Case Actor.
    Logs a warning so the operator can investigate.
    """

    def __init__(
        self,
        dl: CasePersistence,
        request: RejectCaseManagerRoleReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: RejectCaseManagerRoleReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        logger.warning(
            "RejectCaseManagerRoleReceived: actor '%s' rejected CASE_MANAGER"
            " role delegation offer '%s'",
            request.actor_id,
            request.object_id,
        )
