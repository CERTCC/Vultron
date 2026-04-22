"""Use cases for case actor/participant invitation and suggestion activities."""

import logging

from vultron.core.models.events.actor import (
    AcceptCaseOwnershipTransferReceivedEvent,
    AcceptInviteActorToCaseReceivedEvent,
    AcceptSuggestActorToCaseReceivedEvent,
    AnnounceVulnerabilityCaseReceivedEvent,
    InviteActorToCaseReceivedEvent,
    OfferCaseOwnershipTransferReceivedEvent,
    RejectCaseOwnershipTransferReceivedEvent,
    RejectInviteActorToCaseReceivedEvent,
    RejectSuggestActorToCaseReceivedEvent,
    SuggestActorToCaseReceivedEvent,
)
from vultron.core.models.vultron_types import VultronParticipant
from vultron.core.models.protocols import is_case_model
from vultron.core.ports.datalayer import DataLayer
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    PEC,
    PEC_Trigger,
    apply_pec_trigger,
)
from vultron.core.states.rm import RM
from vultron.core.use_cases._helpers import _as_id, _idempotent_create

logger = logging.getLogger(__name__)


class SuggestActorToCaseReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: SuggestActorToCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: SuggestActorToCaseReceivedEvent = request

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
        bridge = BTBridge(datalayer=self._dl)
        bridge.execute_with_setup(tree, actor_id=local_actor_id)


class AcceptSuggestActorToCaseReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: AcceptSuggestActorToCaseReceivedEvent
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
        self, dl: DataLayer, request: RejectSuggestActorToCaseReceivedEvent
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


class OfferCaseOwnershipTransferReceivedUseCase:
    def __init__(
        self, dl: DataLayer, request: OfferCaseOwnershipTransferReceivedEvent
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
        self, dl: DataLayer, request: AcceptCaseOwnershipTransferReceivedEvent
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
        self, dl: DataLayer, request: RejectCaseOwnershipTransferReceivedEvent
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
        self, dl: DataLayer, request: InviteActorToCaseReceivedEvent
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
        self, dl: DataLayer, request: AcceptInviteActorToCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: AcceptInviteActorToCaseReceivedEvent = request

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

        bridge = BTBridge(datalayer=self._dl)
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
        """Emit Announce(VulnerabilityCase) to the invitee from the case owner.

        Per MV-10-003, the case owner sends the full case object after the
        invitee's embargo consent has been verified.
        """
        from vultron.core.use_cases.received.sync import _find_local_actor_id
        from vultron.core.use_cases.triggers._helpers import (
            add_activity_to_outbox,
        )
        from vultron.wire.as2.vocab.activities.case import (
            AnnounceVulnerabilityCaseActivity,
        )

        case_owner_id = _find_local_actor_id(self._dl)
        if case_owner_id is None:
            logger.warning(
                "AcceptInviteActorToCase: no local actor found;"
                " cannot emit AnnounceVulnerabilityCase for case '%s'",
                case_id,
            )
            return

        try:
            announce = AnnounceVulnerabilityCaseActivity(
                actor=case_owner_id,
                object_=case,
                to=[invitee_id],
            )
            self._dl.create(announce)
            add_activity_to_outbox(case_owner_id, announce.id_, self._dl)
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
        self, dl: DataLayer, request: RejectInviteActorToCaseReceivedEvent
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
        dl: DataLayer,
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

        existing = self._dl.read(case_id)
        if existing is not None:
            logger.info(
                "AnnounceVulnerabilityCase: case '%s' already exists locally"
                " — skipping (idempotent, MV-10-004)",
                case_id,
            )
            return

        try:
            self._dl.create(case_obj)
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
