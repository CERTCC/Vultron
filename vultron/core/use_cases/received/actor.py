"""Use cases for case actor/participant invitation and suggestion activities."""

import logging
from typing import TYPE_CHECKING

from vultron.core.models.events.actor import (
    AcceptCaseManagerRoleReceivedEvent,
    AcceptCaseOwnershipTransferReceivedEvent,
    AcceptInviteActorToCaseReceivedEvent,
    AcceptSuggestActorToCaseReceivedEvent,
    AnnounceVulnerabilityCaseReceivedEvent,
    InviteActorToCaseReceivedEvent,
    OfferCaseManagerRoleReceivedEvent,
    OfferCaseOwnershipTransferReceivedEvent,
    RejectCaseManagerRoleReceivedEvent,
    RejectCaseOwnershipTransferReceivedEvent,
    RejectInviteActorToCaseReceivedEvent,
    RejectSuggestActorToCaseReceivedEvent,
    SuggestActorToCaseReceivedEvent,
)
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.models.vultron_types import VultronParticipant
from vultron.core.models.protocols import is_case_model
from vultron.core.ports.case_persistence import (
    CasePersistence,
    CaseOutboxPersistence,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    PEC,
    PEC_Trigger,
    apply_pec_trigger,
)
from vultron.core.states.rm import RM
from vultron.core.states.roles import CVDRole
from vultron.core.use_cases._helpers import _as_id, _idempotent_create

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


def _find_case_actor_id(dl: CasePersistence, case_id: str) -> str | None:
    """Return the CaseActor ID for *case_id*, if present in the DataLayer.

    First checks for a ``VultronReportCaseLink`` whose ``trusted_case_actor_id``
    was established during bootstrap (CBT-01-006).  Falls back to the legacy
    Service-object scan for backward compatibility.
    """
    # Bootstrap-trust path: check ReportCaseLink first
    for link in dl.list_objects("ReportCaseLink"):
        if isinstance(link, VultronReportCaseLink):
            if link.case_id == case_id and link.trusted_case_actor_id:
                return str(link.trusted_case_actor_id)

    # Legacy path: scan for a VultronCaseActor Service with context=case_id
    for service in dl.list_objects("Service"):
        if getattr(service, "context", None) == case_id:
            return service.id_
    return None


def _link_report_case_links(dl: CasePersistence, case) -> None:
    """Attach any matching ``ReportCaseLink`` records to the announced case."""
    for report_ref in case.vulnerability_reports:
        report_id = _as_id(report_ref)
        if report_id is None:
            continue

        link = dl.read(VultronReportCaseLink.build_id(report_id))
        if not isinstance(link, VultronReportCaseLink):
            continue
        if link.case_id == case.id_:
            continue

        dl.save(link.model_copy(update={"case_id": case.id_}))
        logger.info(
            "AnnounceVulnerabilityCase: linked report '%s' to case '%s'",
            report_id,
            case.id_,
        )


class SuggestActorToCaseReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: SuggestActorToCaseReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: SuggestActorToCaseReceivedEvent = request
        self._trigger_activity = trigger_activity

    def execute(self) -> None:
        request = self._request
        activity_id = request.activity_id
        recommender_id = request.actor_id
        invitee_id = request.object_id
        case_id = request.target_id

        if not invitee_id or not case_id:
            logger.warning(
                "SuggestActorToCaseReceived: missing invitee_id or case_id"
                " in event '%s' — skipping",
                activity_id,
            )
            return

        # Persist the incoming recommendation for record-keeping.
        _idempotent_create(
            self._dl,
            request.activity_type,
            activity_id,
            request.activity,
            "RecommendActor",
            activity_id,
        )

        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.case.suggest_actor_tree import (
            create_suggest_actor_tree,
        )
        from vultron.core.use_cases.received.sync import _find_local_actor_id

        local_actor_id = _find_local_actor_id(self._dl)
        if local_actor_id is None:
            logger.warning(
                "SuggestActorToCaseReceived: no local actor found in DataLayer"
                " — skipping event '%s'",
                activity_id,
            )
            return

        tree = create_suggest_actor_tree(
            recommendation_id=activity_id,
            recommender_id=recommender_id,
            invitee_id=invitee_id,
            case_id=case_id,
        )
        bridge = BTBridge(
            datalayer=self._dl, trigger_activity=self._trigger_activity
        )
        bridge.execute_with_setup(tree, actor_id=local_actor_id)


class AcceptSuggestActorToCaseReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: AcceptSuggestActorToCaseReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: AcceptSuggestActorToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        _idempotent_create(
            self._dl,
            request.activity_type,
            request.activity_id,
            request.activity,
            "AcceptSuggestActorToCase",
            request.activity_id,
        )


class RejectSuggestActorToCaseReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: RejectSuggestActorToCaseReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: RejectSuggestActorToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        logger.info(
            "Actor '%s' rejected recommendation to add actor '%s' to case",
            request.actor_id,
            request.suggested_actor_id,
        )


class OfferCaseManagerRoleReceivedUseCase:
    """Handle an incoming CASE_MANAGER role delegation offer.

    Idempotently stores the incoming Offer activity, then auto-accepts it
    on behalf of the local actor (the Case Actor entity that received the
    Offer).  The Accept is queued to the Case Actor's outbox so the offering
    Vendor receives confirmation.

    See DEMOMA-08-002, DEMOMA-08-003; Issue #469.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: OfferCaseManagerRoleReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: OfferCaseManagerRoleReceivedEvent = request
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
            "OfferCaseManagerRole",
            request.activity_id,
        )
        logger.info(
            "OfferCaseManagerRoleReceived: actor '%s' offered CASE_MANAGER"
            " role delegation for activity '%s'",
            request.actor_id,
            request.activity_id,
        )

        if self._trigger_activity is None:
            logger.warning(
                "OfferCaseManagerRoleReceived: trigger_activity not available"
                " — skipping auto-accept for offer '%s'",
                request.activity_id,
            )
            return

        case_id = _as_id(request.activity.object_)
        participant_id = _as_id(request.activity.target)
        offer_id = request.activity_id
        vendor_id = request.actor_id

        if not case_id or not participant_id:
            logger.warning(
                "OfferCaseManagerRoleReceived: missing case_id or"
                " participant_id in offer '%s' — skipping auto-accept",
                offer_id,
            )
            return

        local_actor_id = _find_local_actor_id(self._dl)
        if local_actor_id is None:
            logger.warning(
                "OfferCaseManagerRoleReceived: no local actor found"
                " — skipping auto-accept for offer '%s'",
                offer_id,
            )
            return

        try:
            accept_id = self._trigger_activity.accept_case_manager_role(
                offer_id=offer_id,
                case_id=case_id,
                participant_id=participant_id,
                vendor_id=vendor_id,
                actor=local_actor_id,
                to=[vendor_id],
            )
            add_activity_to_outbox(local_actor_id, accept_id, self._dl)
            logger.info(
                "OfferCaseManagerRoleReceived: auto-accepted offer '%s'"
                " as actor '%s'; queued Accept '%s' to outbox",
                offer_id,
                local_actor_id,
                accept_id,
            )
        except Exception as exc:
            logger.error(
                "OfferCaseManagerRoleReceived: error auto-accepting offer"
                " '%s': %s",
                offer_id,
                exc,
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

        local_actor_id = _find_local_actor_id(self._dl)
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


class OfferCaseOwnershipTransferReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: OfferCaseOwnershipTransferReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: OfferCaseOwnershipTransferReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        _idempotent_create(
            self._dl,
            request.activity_type,
            request.activity_id,
            request.activity,
            "OfferCaseOwnershipTransfer",
            request.activity_id,
        )


class AcceptCaseOwnershipTransferReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: AcceptCaseOwnershipTransferReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: AcceptCaseOwnershipTransferReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        case_id = request.case_id
        new_owner_id = request.actor_id
        if case_id is None:
            logger.warning(
                "accept_case_ownership_transfer: missing case_id on request"
            )
            return
        case = self._dl.read(case_id)

        if not is_case_model(case):
            logger.warning(
                "accept_case_ownership_transfer: case '%s' not found",
                case_id,
            )
            return

        current_owner_id = _as_id(case.attributed_to)
        if current_owner_id == new_owner_id:
            logger.info(
                "Case '%s' already owned by '%s' — skipping (idempotent)",
                case_id,
                new_owner_id,
            )
            return

        case.attributed_to = new_owner_id  # type: ignore[assignment]
        self._dl.save(case)
        logger.info(
            "Transferred ownership of case '%s' from '%s' to '%s'",
            case_id,
            current_owner_id,
            new_owner_id,
        )


class RejectCaseOwnershipTransferReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: RejectCaseOwnershipTransferReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: RejectCaseOwnershipTransferReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        logger.info(
            "Actor '%s' rejected ownership transfer offer '%s' — ownership unchanged",
            request.actor_id,
            request.offer_id,
        )


class InviteActorToCaseReceivedUseCase:
    def __init__(
        self, dl: CasePersistence, request: InviteActorToCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: InviteActorToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        _idempotent_create(
            self._dl,
            request.activity_type,
            request.activity_id,
            request.activity,
            "InviteActorToCase",
            request.activity_id,
        )
        # MV-10-004: do NOT create a case from the stub target.  The stub
        # carries only {id, type} for identification; the full case details
        # arrive later in an AnnounceVulnerabilityCase activity (MV-10-003).
        case_stub_id = request.target_id
        if case_stub_id:
            logger.info(
                "InviteActorToCase: received invite with case stub '%s'."
                " Awaiting AnnounceVulnerabilityCase before creating case.",
                case_stub_id,
            )


class AcceptInviteActorToCaseReceivedUseCase:
    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AcceptInviteActorToCaseReceivedEvent,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request: AcceptInviteActorToCaseReceivedEvent = request
        self._trigger_activity = trigger_activity

    def execute(self) -> None:
        request = self._request
        case_id = request.case_id
        invitee_id = request.invitee_id
        if case_id is None or invitee_id is None:
            logger.warning(
                "accept_invite_actor_to_case: missing case_id or invitee_id"
            )
            return
        case = self._dl.read(case_id)

        if not is_case_model(case):
            logger.warning(
                "accept_invite_actor_to_case: case '%s' not found", case_id
            )
            return

        existing_ids = [_as_id(p) for p in case.case_participants]
        if (
            invitee_id in case.actor_participant_index
            or invitee_id in existing_ids
        ):
            logger.info(
                "Actor '%s' already participant in case '%s' — skipping (idempotent)",
                invitee_id,
                case_id,
            )
            return

        active_embargo_id = _as_id(case.active_embargo)
        em_state = case.current_status.em_state

        participant = VultronParticipant(
            id_=f"{case_id}/participants/{invitee_id.split('/')[-1]}",
            attributed_to=invitee_id,
            context=case_id,
        )
        # An accepted invite implies the invitee has received and validated the
        # case. Pre-seeding RECEIVED→VALID ensures the engage-case trigger
        # (VALID→ACCEPTED) is a valid RM transition.
        participant.append_rm_state(
            RM.RECEIVED, actor=invitee_id, context=case_id
        )
        participant.append_rm_state(
            RM.VALID, actor=invitee_id, context=case_id
        )
        # Only auto-sign embargo consent when the embargo is fully ACTIVE.
        # In REVISE state the terms are under negotiation; auto-signing would
        # commit the new participant to unresolved terms.
        if active_embargo_id and em_state == EM.ACTIVE:
            participant.accepted_embargo_ids.append(active_embargo_id)
            participant.embargo_consent_state = apply_pec_trigger(
                PEC.NO_EMBARGO, PEC_Trigger.ACCEPT
            )
        self._dl.create(participant)

        # Use string IDs to avoid wire-type serialization incompatibility
        case.case_participants.append(participant.id_)
        case.actor_participant_index[invitee_id] = participant.id_
        case.record_event(invitee_id, "participant_joined")
        if active_embargo_id and em_state == EM.ACTIVE:
            case.record_event(active_embargo_id, "embargo_accepted")
        self._dl.save(case)

        # MV-10-003/MV-10-005: emit full case details to the invitee now that
        # embargo consent has been resolved (auto-signed above when ACTIVE).
        # The case owner (receiving_actor_id) sends Announce(VulnerabilityCase)
        # so the invitee can seed their local DataLayer.
        self._emit_announce_case(case_id, invitee_id, case)

        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.report.prioritize_tree import (
            create_prioritize_subtree,
        )

        bridge = BTBridge(
            datalayer=self._dl, trigger_activity=self._trigger_activity
        )
        prioritize_tree = create_prioritize_subtree(
            case_id=case_id, actor_id=invitee_id
        )
        bridge.execute_with_setup(prioritize_tree, actor_id=invitee_id)

        logger.info(
            "Added participant '%s' to case '%s' via accepted invite and auto-engaged via BT",
            invitee_id,
            case_id,
        )

    def _emit_announce_case(self, case_id: str, invitee_id: str, case) -> None:
        """Emit Announce(VulnerabilityCase) to the invitee from the CaseActor.

        Per MV-10-003, the case owner sends the full case object after the
        invitee's embargo consent has been verified.
        """
        from vultron.core.use_cases.triggers._helpers import (
            add_activity_to_outbox,
        )
        from vultron.wire.as2.factories import (
            announce_vulnerability_case_activity,
        )

        case_actor_id = _find_case_actor_id(self._dl, case_id)
        if case_actor_id is None:
            logger.warning(
                "AcceptInviteActorToCase: no CaseActor found;"
                " cannot emit AnnounceVulnerabilityCase for case '%s'",
                case_id,
            )
            return

        try:
            announce = announce_vulnerability_case_activity(
                case=case,
                actor=case_actor_id,
                context=case_id,
                to=[invitee_id],
            )
            self._dl.create(announce)
            add_activity_to_outbox(case_actor_id, announce.id_, self._dl)
            logger.info(
                "Emitted AnnounceVulnerabilityCase '%s' to '%s' for case '%s'",
                announce.id_,
                invitee_id,
                case_id,
            )
        except Exception as exc:
            logger.error(
                "Failed to emit AnnounceVulnerabilityCase for case '%s'"
                " to '%s': %s",
                case_id,
                invitee_id,
                exc,
            )


class RejectInviteActorToCaseReceivedUseCase:
    def __init__(
        self,
        dl: CasePersistence,
        request: RejectInviteActorToCaseReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request: RejectInviteActorToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        logger.info(
            "Actor '%s' rejected invitation '%s'",
            request.actor_id,
            request.invite_id,
        )


class AnnounceVulnerabilityCaseReceivedUseCase:
    """Seed the local DataLayer with a full VulnerabilityCase from the case owner.

    Per MV-10-003, the invitee creates the case if it does not already exist.
    Per MV-10-004, if the case already exists locally, the announcement is
    accepted without overwriting the existing record (idempotent).
    """

    def __init__(
        self,
        dl: CasePersistence,
        request: AnnounceVulnerabilityCaseReceivedEvent,
    ) -> None:
        self._dl = dl
        self._request = request

    def execute(self) -> None:
        request = self._request
        activity = request.activity
        if activity is None:
            logger.warning(
                "AnnounceVulnerabilityCase: no activity on event '%s' — skipping",
                request.activity_id,
            )
            return

        # The case object is the object_ field of the announce activity.
        case_obj = getattr(activity, "object_", None)
        if case_obj is None:
            logger.warning(
                "AnnounceVulnerabilityCase: no case object in activity '%s'"
                " — skipping",
                request.activity_id,
            )
            return

        if not is_case_model(case_obj):
            logger.warning(
                "AnnounceVulnerabilityCase: object in activity '%s' is not a"
                " VulnerabilityCase (%s) — skipping",
                request.activity_id,
                type(case_obj).__name__,
            )
            return

        case_id = _as_id(case_obj)
        if case_id is None:
            logger.warning(
                "AnnounceVulnerabilityCase: case object has no id in"
                " activity '%s' — skipping",
                request.activity_id,
            )
            return

        case_actor_id = _find_case_actor_id(self._dl, case_id)
        if case_actor_id is not None and case_actor_id != request.actor_id:
            logger.warning(
                "AnnounceVulnerabilityCase: actor '%s' is not the CaseActor"
                " for case '%s' — update rejected (PCR-03-001)",
                request.actor_id,
                case_id,
            )
            return

        existing = self._dl.read(case_id)
        if existing is not None:
            logger.info(
                "AnnounceVulnerabilityCase: case '%s' already exists locally"
                " — skipping (idempotent, MV-10-004)",
                case_id,
            )
            _link_report_case_links(self._dl, case_obj)
            return

        try:
            self._dl.save(case_obj)
            _link_report_case_links(self._dl, case_obj)
            logger.info(
                "AnnounceVulnerabilityCase: seeded case '%s' from actor '%s'",
                case_id,
                request.actor_id,
            )
        except Exception as exc:
            logger.error(
                "AnnounceVulnerabilityCase: failed to create case '%s': %s",
                case_id,
                exc,
            )
