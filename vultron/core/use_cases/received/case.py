"""Use cases for vulnerability case activities."""

import logging
from typing import Any, cast

from py_trees.common import Status

from vultron.core.models.events.case import (
    AddReportToCaseReceivedEvent,
    CloseCaseReceivedEvent,
    CreateCaseReceivedEvent,
    DeferCaseReceivedEvent,
    EngageCaseReceivedEvent,
    UpdateCaseReceivedEvent,
)
from vultron.core.models.participant import VultronParticipant
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.models.vultron_types import VultronActivity
from vultron.core.ports.case_persistence import (
    CasePersistence,
    CaseOutboxPersistence,
)
from vultron.core.models.protocols import (
    CaseModel,
    is_case_model,
    is_participant_model,
)
from vultron.core.states.rm import RM, is_rm_at_least
from vultron.core.states.roles import CVDRole
from vultron.core.use_cases._helpers import _as_id, update_participant_rm_state

logger = logging.getLogger(__name__)


def _find_case_actor_id_from_participants(
    case_obj: CaseModel, dl: CasePersistence
) -> str | None:
    """Find the CaseActor ID from the CASE_MANAGER participant in the case.

    Uses duck-typing on ``case_roles`` to avoid importing wire-layer types.
    Returns the ``attributed_to`` URI of the first participant holding
    ``CVDRole.CASE_MANAGER`` (CBT-01-003).

    Handles both inline objects and ID-only references stored in
    ``case_participants``.
    """
    for participant_ref in case_obj.case_participants:
        # Try inline object first (participant embedded in snapshot)
        if not isinstance(participant_ref, str):
            roles = getattr(participant_ref, "case_roles", [])
            if CVDRole.CASE_MANAGER in roles:
                attributed = getattr(participant_ref, "attributed_to", None)
                if attributed:
                    return str(attributed)
            continue

        # ID-only reference — look up from DataLayer
        participant = dl.read(participant_ref)
        if participant is None:
            continue
        roles = getattr(participant, "case_roles", [])
        if CVDRole.CASE_MANAGER in roles:
            attributed = getattr(participant, "attributed_to", None)
            if attributed:
                return str(attributed)
    return None


def _find_report_case_link(
    creator_id: str, dl: CasePersistence
) -> VultronReportCaseLink | None:
    """Return a pending ReportCaseLink expecting a bootstrap from *creator_id*.

    Scans all ``ReportCaseLink`` records and returns the first that has
    ``trusted_case_creator_id == creator_id`` and ``case_id is None``
    (i.e. awaiting bootstrap).  Using the sender identity rather than the
    case's vulnerability_reports list makes the lookup independent of whether
    the case snapshot embeds the report.
    """
    for obj in dl.list_objects("ReportCaseLink"):
        if isinstance(obj, VultronReportCaseLink):
            if (
                obj.trusted_case_creator_id == creator_id
                and obj.case_id is None
            ):
                return obj
    return None


def _check_participant_embargo_acceptance(
    case: CaseModel, dl: CasePersistence
) -> set[str]:
    """Check which participants have not accepted the active embargo.

    Returns a set of actor IDs whose case updates should be withheld per
    CM-10-004 (participants that have not accepted the active embargo).
    """
    excluded: set[str] = set()
    active_embargo = case.active_embargo
    if active_embargo is None:
        return excluded
    embargo_id = _as_id(active_embargo)
    for actor_id, participant_id in case.actor_participant_index.items():
        participant = dl.read(participant_id)
        if participant is None:
            logger.warning(
                "update_case: could not read participant '%s' for embargo acceptance check",
                participant_id,
            )
            continue
        if not is_participant_model(participant):
            continue
        if embargo_id not in participant.accepted_embargo_ids:
            logger.warning(
                "update_case: participant '%s' (actor '%s') has not accepted the active "
                "embargo '%s' — case update will not be broadcast to this participant "
                "(CM-10-004)",
                participant_id,
                actor_id,
                embargo_id,
            )
            excluded.add(actor_id)
    return excluded


def _store_embedded_participants(
    case_obj: CaseModel, dl: CasePersistence, case_id: str
) -> None:
    """Persist embedded participant objects from a case snapshot.

    When a bootstrapped or announced ``VulnerabilityCase`` carries fully
    materialised participant objects (not just ID strings), each is stored
    as an independent DataLayer record.  This ensures BT nodes such as
    ``CheckParticipantExists`` (#561) and ``AppendParticipantStatusNode``
    (#562, #566) can retrieve them by their UUID.

    Called from:
    - ``CreateCaseReceivedUseCase._handle_bootstrap`` (Create path, CBT-05-005)
    - ``AnnounceVulnerabilityCaseReceivedUseCase.execute`` (Announce path, #566)

    Idempotent: ``dl.save()`` upserts so repeated calls are safe.

    Args:
        case_obj: The bootstrapped or announced case domain object.
        dl: DataLayer to persist participants into.
        case_id: ID of the case (for log context).
    """
    participants = getattr(case_obj, "case_participants", []) or []
    for participant_ref in participants:
        if isinstance(participant_ref, str):
            continue
        pid = getattr(participant_ref, "id_", None)
        if pid is None:
            continue
        dl.save(participant_ref)
        logger.info(
            "store_embedded_participants: stored participant '%s'"
            " for case '%s' (CBT-05-005, #566)",
            pid,
            case_id,
        )


def _ensure_reporter_participant(
    dl: CasePersistence,
    link: VultronReportCaseLink,
    case_obj: CaseModel,
    case_id: str,
) -> None:
    """Ensure the reporter's participant record is at RM.ACCEPTED (#589, #624).

    When ``Create(VulnerabilityCase)`` carries participant IDs as bare
    strings, ``_store_embedded_participants`` skips them.  Without an
    explicit participant record in the DataLayer,
    ``SvcAddParticipantStatusUseCase._resolve_current_participant_state``
    falls back to ``RM.START``, causing the Vendor's Case Actor to reject the
    subsequent ``Add(ParticipantStatus)`` as a backwards transition.

    The reporter submitted the original report, which implies they have
    already ``RM.ACCEPTED`` from their own perspective.  The reporter is
    identified as ``attributed_to`` of the ``Offer(Report)`` activity
    (``report.attributed_to``).  Their ``START→RECEIVED→VALID→ACCEPTED`` arc
    is hidden from the protocol — their first observable action already
    implies ``RM.ACCEPTED`` (#624).

    This function:

    * Creates the participant record at ``RM.ACCEPTED`` if it is absent.
    * Upgrades an existing participant from any state below ``RM.ACCEPTED``
      (e.g. ``RM.START`` seeded by the wire-layer default) to ``RM.ACCEPTED``.
    * No-ops if the participant is already at or beyond ``RM.ACCEPTED``.

    This invariant applies **only** to the reporter/finder.  All other
    participants enter through a visible protocol interaction and their RM
    lifecycle proceeds normally from ``RM.RECEIVED``.

    Args:
        dl: The reporter's local DataLayer.
        link: The ``VultronReportCaseLink`` associating the report to this
            case bootstrap.
        case_obj: The bootstrapped ``VulnerabilityCase`` snapshot.
        case_id: ID of the case (for log context and status context).
    """
    report = dl.read(link.report_id)
    if report is None:
        logger.warning(
            "ensure_reporter_participant: report '%s' not found "
            "— cannot seed reporter participant (#589)",
            link.report_id,
        )
        return

    reporter_actor_id = _as_id(getattr(report, "attributed_to", None))
    if not reporter_actor_id:
        logger.warning(
            "ensure_reporter_participant: report '%s' has no attributed_to "
            "— cannot seed reporter participant (#589)",
            link.report_id,
        )
        return

    index = getattr(case_obj, "actor_participant_index", {}) or {}
    participant_id = index.get(reporter_actor_id)
    if not participant_id:
        logger.warning(
            "ensure_reporter_participant: reporter '%s' not in "
            "actor_participant_index for case '%s' — skipping (#589)",
            reporter_actor_id,
            case_id,
        )
        return

    existing = dl.read(participant_id)
    if existing is not None:
        statuses = getattr(existing, "participant_statuses", []) or []
        latest_rm = statuses[-1].rm_state if statuses else RM.START
        if is_rm_at_least(latest_rm, RM.ACCEPTED):
            logger.debug(
                "ensure_reporter_participant: participant '%s' already "
                "≥ RM.ACCEPTED — skipping (#589, #624)",
                participant_id,
            )
            return
        _upgrade_participant_to_accepted(
            dl, existing, participant_id, case_id, reporter_actor_id, latest_rm
        )
        return

    status = ParticipantStatus(
        rm_state=RM.ACCEPTED,
        context=case_id,
        attributed_to=reporter_actor_id,
    )
    participant = VultronParticipant(
        id_=participant_id,
        attributed_to=reporter_actor_id,
        context=case_id,
        participant_statuses=[status],
    )
    try:
        dl.create(participant)
        logger.info(
            "ensure_reporter_participant: created participant '%s' for "
            "reporter '%s' at RM.ACCEPTED (#589)",
            participant_id,
            reporter_actor_id,
        )
    except ValueError:
        logger.debug(
            "ensure_reporter_participant: participant '%s' was concurrently "
            "created — idempotent (#589)",
            participant_id,
        )


def _upgrade_participant_to_accepted(
    dl: CasePersistence,
    existing: Any,
    participant_id: str,
    case_id: str,
    reporter_actor_id: str,
    latest_rm: "RM",
) -> None:
    """Upgrade an existing participant record from below RM.ACCEPTED to RM.ACCEPTED.

    Saves the new status as an independent DataLayer record, then reads it back
    via the vocabulary registry so the serialised type matches what the
    participant container expects.  This avoids wire/domain type mismatches when
    appending to ``CaseParticipant.participant_statuses``.
    """
    upgrade_status = ParticipantStatus(
        rm_state=RM.ACCEPTED,
        context=case_id,
        attributed_to=reporter_actor_id,
    )
    try:
        dl.create(upgrade_status)
    except ValueError:
        dl.save(upgrade_status)
    wire_status = dl.read(upgrade_status.id_)
    participant_statuses = getattr(existing, "participant_statuses", None)
    if participant_statuses is not None:
        participant_statuses.append(
            wire_status if wire_status is not None else upgrade_status
        )
    dl.save(existing)
    logger.info(
        "ensure_reporter_participant: upgraded participant '%s' from "
        "%s to RM.ACCEPTED (#589, #624)",
        participant_id,
        latest_rm,
    )


class CreateCaseReceivedUseCase:
    """Process a bootstrap ``Create(VulnerabilityCase)`` from a remote actor.

    Receiving this message means *someone else* created the case and is
    notifying us.  We do NOT create our own case infrastructure here.

    Bootstrap trust path (CBT-01-005 / CBT-01-006):
    1. Locate the ``VultronReportCaseLink`` for any report listed in the case.
    2. Validate that the sender matches ``link.trusted_case_creator_id``.
    3. Extract the ``CaseActor`` ID from the ``CASE_MANAGER`` participant.
    4. Seed a local replica of the case via the case-replica BT.
    5. Update the link with ``case_id`` and ``trusted_case_actor_id``.
    """

    def __init__(
        self, dl: CasePersistence, request: CreateCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: CreateCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        actor_id = request.actor_id
        case_id = request.case_id

        if request.case is None:
            logger.warning(
                "create_case_received: no case domain object in event for "
                "case '%s'",
                case_id,
            )
            return

        if case_id is None:
            logger.warning(
                "create_case_received: case_id missing in event — skipping"
            )
            return

        case_obj_raw = request.case
        if not is_case_model(case_obj_raw):
            logger.warning(
                "create_case_received: case object for case '%s' does not "
                "satisfy CaseModel protocol — skipping",
                case_id,
            )
            return
        case_obj: CaseModel = case_obj_raw
        link = _find_report_case_link(actor_id, self._dl)

        if link is not None:
            # Bootstrap trust path — CBT-01-005 / CBT-01-006
            self._handle_bootstrap(actor_id, case_id, case_obj, link)
        else:
            logger.info(
                "create_case_received: no ReportCaseLink for case '%s' — "
                "no bootstrap trust to record (not a known reporter)",
                case_id,
            )

    def _handle_bootstrap(
        self,
        actor_id: str,
        case_id: str,
        case_obj: CaseModel,
        link: VultronReportCaseLink,
    ) -> None:
        """Validate trust and seed the case replica."""
        # CBT-01-005: sender must match the actor we sent the report to
        if link.trusted_case_creator_id is not None:
            if actor_id != link.trusted_case_creator_id:
                logger.warning(
                    "create_case_received: bootstrap rejected for case '%s' — "
                    "sender does not match trusted case creator "
                    "(CBT-01-005)",
                    case_id,
                )
                return
        else:
            logger.warning(
                "create_case_received: no trusted_case_creator_id in link "
                "for case '%s'; accepting bootstrap unchecked",
                case_id,
            )

        # CBT-01-003: extract CaseActor from CASE_MANAGER participant
        case_actor_id = _find_case_actor_id_from_participants(
            case_obj, self._dl
        )
        if case_actor_id is None:
            logger.warning(
                "create_case_received: no CASE_MANAGER participant found in "
                "bootstrap snapshot for case '%s'; Announce validation will "
                "be bypassed",
                case_id,
            )

        logger.info(
            "create_case_received: bootstrap accepted for case '%s' from "
            "'%s'; seeding replica (CBT-01-006)",
            case_id,
            actor_id,
        )

        # Seed the local case replica
        from vultron.core.models.protocols import is_case_model

        # Idempotency guard (CBT-01-006, ID-04-004)
        existing = self._dl.read(case_id)
        if is_case_model(existing):
            logger.info(
                "create_case_received: case '%s' already exists as replica "
                "— skipping re-seed",
                case_id,
            )
        else:
            try:
                self._dl.create(case_obj)
                logger.info(
                    "create_case_received: replica case '%s' persisted",
                    case_id,
                )
            except ValueError:
                logger.info(
                    "create_case_received: case '%s' persisted concurrently "
                    "— idempotent",
                    case_id,
                )

        # CBT-01-006: persist trust anchors in the link
        link.case_id = case_id
        link.trusted_case_actor_id = case_actor_id
        self._dl.save(link)
        logger.info(
            "create_case_received: ReportCaseLink updated with case_id='%s' "
            "and trusted_case_actor_id='%s' (CBT-01-006)",
            case_id,
            case_actor_id,
        )

        # CBT-05-005: store any embedded participant objects so that BT nodes
        # (``CheckParticipantExists``, ``AppendParticipantStatusNode``) can
        # find them by UUID via ``datalayer.read(participant_id)``.
        # This must happen regardless of the idempotency guard above because
        # the inbox router may have already seeded the case before dispatch.
        _store_embedded_participants(case_obj, self._dl, case_id)

        # #589: when participants arrive as bare string IDs (the common case),
        # _store_embedded_participants cannot create records for them.  Ensure
        # the reporter's own participant is seeded at RM.ACCEPTED — inferred
        # from the fact that they submitted a report.
        _ensure_reporter_participant(self._dl, link, case_obj, case_id)


class UpdateCaseReceivedUseCase:
    def __init__(
        self, dl: CaseOutboxPersistence, request: UpdateCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: UpdateCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        actor_id = request.actor_id
        case_id = request.case_id
        if case_id is None:
            logger.warning("update_case: missing case_id on request")
            return

        stored_case = self._dl.read(case_id)
        if not is_case_model(stored_case):
            logger.warning(
                "update_case: case '%s' not found in DataLayer — skipping",
                case_id,
            )
            return

        owner_id = _as_id(stored_case.attributed_to)
        if owner_id != actor_id:
            logger.warning(
                "update_case: actor '%s' is not the owner of case '%s' — skipping update",
                actor_id,
                case_id,
            )
            return

        excluded_actor_ids = _check_participant_embargo_acceptance(
            stored_case, self._dl
        )

        if (
            request.object_type == "VulnerabilityCase"
            and request.case is not None
        ):
            for field in ("name", "summary", "content"):
                value = getattr(request.case, field, None)
                if value is not None:
                    setattr(stored_case, field, value)
            self._dl.save(stored_case)
            logger.info("Actor '%s' updated case '%s'", actor_id, case_id)
        else:
            logger.info(
                "update_case: object for case '%s' is a reference only — no fields to apply",
                case_id,
            )

        self._broadcast_case_update(case_id, stored_case, excluded_actor_ids)

    def _broadcast_case_update(
        self,
        case_id: str,
        case: CaseModel,
        excluded_actor_ids: set[str] | None = None,
    ) -> None:
        """Broadcast an Announce activity for the updated case to participants.

        Implements CM-06-001/CM-06-002: after a case update, the CaseActor MUST
        send an ActivityStreams Announce to each active case participant's inbox.
        Per CM-10-004, participants who have not accepted the active embargo are
        excluded from the broadcast.
        """
        excluded = excluded_actor_ids or set()
        # Locate the CaseActor (type_="Service") associated with this case
        case_actor_id: str | None = None
        for service in self._dl.list_objects("Service"):
            if getattr(service, "context", None) == case_id:
                case_actor_id = service.id_
                break

        if case_actor_id is None:
            logger.debug(
                "update_case: no CaseActor found for case '%s' — skipping broadcast",
                case_id,
            )
            return

        participant_ids = [
            actor_id
            for actor_id in case.actor_participant_index.keys()
            if actor_id not in excluded
        ]
        if not participant_ids:
            logger.debug(
                "update_case: no eligible participants in case '%s' — skipping broadcast",
                case_id,
            )
            return

        broadcast = VultronActivity(
            type_="Announce",
            actor=case_actor_id,
            object_=case_id,
            to=participant_ids,
        )
        try:
            self._dl.create(broadcast)
        except ValueError:
            logger.debug(
                "update_case: broadcast activity %s already exists — skipping",
                broadcast.id_,
            )
            return

        case_actor_obj = self._dl.read(case_actor_id)
        if case_actor_obj is not None and hasattr(case_actor_obj, "outbox"):
            cast(Any, case_actor_obj).outbox.items.append(broadcast.id_)
            self._dl.save(case_actor_obj)

        # Enqueue for delivery via outbox_handler
        self._dl.record_outbox_item(case_actor_id, broadcast.id_)

        logger.info(
            "update_case: CaseActor '%s' broadcast Announce for case '%s' to %d participants (CM-06-001)",
            case_actor_id,
            case_id,
            len(participant_ids),
        )


class EngageCaseReceivedUseCase:
    def __init__(
        self, dl: CasePersistence, request: EngageCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: EngageCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.report.prioritize_tree import (
            create_engage_case_tree,
        )

        actor_id = request.actor_id
        case_id = request.case_id
        if case_id is None:
            logger.warning("engage_case: missing case_id on request")
            return

        # Persist any inline participant objects carried in the case snapshot
        # so BT nodes (CheckParticipantExists, AppendParticipantStatusNode) can
        # locate them by UUID.  Mirrors the Create (#564) and Announce (#566)
        # paths (CBT-05-005, fixes #573).
        case_obj = request.case
        if is_case_model(case_obj):
            _store_embedded_participants(case_obj, self._dl, case_id)

        logger.info(
            "Actor '%s' engages case '%s' (RM → ACCEPTED)",
            actor_id,
            case_id,
        )

        bridge = BTBridge(datalayer=self._dl)
        tree = create_engage_case_tree(case_id=case_id, actor_id=actor_id)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=actor_id, activity=request
        )

        if result.status != Status.SUCCESS:
            logger.warning(
                "EngageCaseBT did not succeed for actor '%s' / case '%s': %s",
                actor_id,
                case_id,
                BTBridge.get_failure_reason(tree),
            )


class DeferCaseReceivedUseCase:
    def __init__(
        self, dl: CasePersistence, request: DeferCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: DeferCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.report.prioritize_tree import (
            create_defer_case_tree,
        )

        actor_id = request.actor_id
        case_id = request.case_id
        if case_id is None:
            logger.warning("defer_case: missing case_id on request")
            return

        logger.info(
            "Actor '%s' defers case '%s' (RM → DEFERRED)",
            actor_id,
            case_id,
        )

        bridge = BTBridge(datalayer=self._dl)
        tree = create_defer_case_tree(case_id=case_id, actor_id=actor_id)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=actor_id, activity=request
        )

        if result.status != Status.SUCCESS:
            logger.warning(
                "DeferCaseBT did not succeed for actor '%s' / case '%s': %s",
                actor_id,
                case_id,
                BTBridge.get_failure_reason(tree),
            )


class AddReportToCaseReceivedUseCase:
    def __init__(
        self, dl: CasePersistence, request: AddReportToCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: AddReportToCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        report_id = request.report_id
        case_id = request.case_id
        if report_id is None or case_id is None:
            logger.warning("add_report_to_case: missing report_id or case_id")
            return
        case = self._dl.read(case_id)

        if not is_case_model(case):
            logger.warning("add_report_to_case: case '%s' not found", case_id)
            return

        existing_report_ids = [_as_id(r) for r in case.vulnerability_reports]
        if report_id in existing_report_ids:
            logger.info(
                "Report '%s' already in case '%s' — skipping (idempotent)",
                report_id,
                case_id,
            )
            return

        case.vulnerability_reports.append(report_id)
        self._dl.save(case)
        logger.info("Added report '%s' to case '%s'", report_id, case_id)


class CloseCaseReceivedUseCase:
    def __init__(
        self, dl: CaseOutboxPersistence, request: CloseCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: CloseCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        actor_id = request.actor_id
        case_id = request.case_id

        logger.info("Actor '%s' is closing case '%s'", actor_id, case_id)

        close_activity = VultronActivity(
            type_="Leave",
            actor=actor_id,
            object_=case_id,
        )
        try:
            self._dl.create(close_activity)
            logger.info("Created Leave activity %s", close_activity.id_)
        except ValueError:
            logger.info(
                "Leave activity for case '%s' already exists — skipping (idempotent)",
                case_id,
            )
            return

        actor_obj = self._dl.read(actor_id)
        if actor_obj is not None and hasattr(actor_obj, "outbox"):
            cast(Any, actor_obj).outbox.items.append(close_activity.id_)
            self._dl.save(actor_obj)
            logger.info(
                "Added Leave activity %s to actor %s outbox",
                close_activity.id_,
                actor_id,
            )
        # Queue for delivery via outbox_handler regardless of outbox field
        self._dl.record_outbox_item(actor_id, close_activity.id_)


class InvalidateCaseUseCase:
    """Transition the actor's RM state to INVALID within the given case.

    Called by ``InvalidateReportReceivedUseCase`` after dereferencing
    report_id to case_id (CM-12-005).
    """

    def __init__(
        self, dl: CasePersistence, case_id: str, actor_id: str
    ) -> None:
        self._dl = dl
        self._case_id = case_id
        self._actor_id = actor_id

    def execute(self) -> None:
        success = update_participant_rm_state(
            self._case_id, self._actor_id, RM.INVALID, self._dl
        )
        if success:
            logger.info(
                "RM → INVALID for actor '%s' in case '%s'",
                self._actor_id,
                self._case_id,
            )
        else:
            logger.warning(
                "Failed to set RM.INVALID for actor '%s' in case '%s'",
                self._actor_id,
                self._case_id,
            )


class CloseCaseUseCase:
    """Transition the actor's RM state to CLOSED within the given case.

    Called by ``CloseReportReceivedUseCase`` after dereferencing
    report_id to case_id (CM-12-005).
    """

    def __init__(
        self, dl: CasePersistence, case_id: str, actor_id: str
    ) -> None:
        self._dl = dl
        self._case_id = case_id
        self._actor_id = actor_id

    def execute(self) -> None:
        success = update_participant_rm_state(
            self._case_id, self._actor_id, RM.CLOSED, self._dl
        )
        if success:
            logger.info(
                "RM → CLOSED for actor '%s' in case '%s'",
                self._actor_id,
                self._case_id,
            )
        else:
            logger.warning(
                "Failed to set RM.CLOSED for actor '%s' in case '%s'",
                self._actor_id,
                self._case_id,
            )


class ValidateCaseUseCase:
    """Run the validate-report behavior tree for the given case.

    Called by ``ValidateReportReceivedUseCase`` after dereferencing
    report_id to case_id (CM-12-005).

    After successful BT validation (RM → VALID), auto-cascades to engage the
    case (RM → ACCEPTED) using the default policy of immediate engagement.
    This eliminates the need for a separate manual ``engage-case`` trigger call
    (D5-7-AUTOENG-2).
    """

    def __init__(
        self,
        dl: CasePersistence,
        actor_id: str,
        report_id: str,
        offer_id: str,
        case_id: str | None = None,
    ) -> None:
        self._dl = dl
        self._actor_id = actor_id
        self._report_id = report_id
        self._offer_id = offer_id
        self._case_id = case_id

    def execute(self) -> None:
        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.report.validate_tree import (
            create_validate_report_tree,
        )

        logger.info(
            "Actor '%s' validates VulnerabilityReport '%s'%s via BT",
            self._actor_id,
            self._report_id,
            f" (case '{self._case_id}')" if self._case_id else "",
        )

        bridge = BTBridge(datalayer=self._dl)
        tree = create_validate_report_tree(
            report_id=self._report_id,
            offer_id=self._offer_id,
            case_id=self._case_id,
            actor_id=self._actor_id,
        )
        result = bridge.execute_with_setup(tree, actor_id=self._actor_id)

        if result.status == Status.SUCCESS:
            logger.info(
                "✓ BT validation succeeded for report: %s", self._report_id
            )
        elif result.status == Status.FAILURE:
            logger.error(
                "✗ BT validation failed for report: %s — %s",
                self._report_id,
                result.feedback_message,
            )
            for err in result.errors or []:
                logger.error("  - %s", err)
        else:
            logger.warning(
                "⚠ BT validation incomplete for report: %s (status=%s)",
                self._report_id,
                result.status,
            )
