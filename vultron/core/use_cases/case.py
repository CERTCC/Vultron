"""Use cases for vulnerability case activities."""

import logging
from typing import cast

from vultron.core.models.events.case import (
    AddReportToCaseReceivedEvent,
    CloseCaseReceivedEvent,
    CreateCaseReceivedEvent,
    DeferCaseReceivedEvent,
    EngageCaseReceivedEvent,
    UpdateCaseReceivedEvent,
)
from vultron.core.models.vultron_types import VultronActivity
from vultron.core.ports.datalayer import DataLayer
from vultron.core.use_cases._types import CaseModel

logger = logging.getLogger(__name__)


def create_case(event: CreateCaseReceivedEvent, dl: DataLayer) -> None:
    from vultron.core.behaviors.bridge import BTBridge
    from vultron.core.behaviors.case.create_tree import create_create_case_tree
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        VulnerabilityCase,
    )

    try:
        actor_id = event.actor_id
        case_id = event.object_id

        if event.case is None:
            logger.warning(
                "create_case: no case domain object in event for case '%s'",
                case_id,
            )
            return

        logger.info("Actor '%s' creates case '%s'", actor_id, case_id)

        case_wire = VulnerabilityCase(
            id=event.case.as_id,
            name=event.case.name,
            attributed_to=event.case.attributed_to,
        )

        bridge = BTBridge(datalayer=dl)
        tree = create_create_case_tree(case_obj=case_wire, actor_id=actor_id)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=actor_id, activity=event
        )

        if result.status.name != "SUCCESS":
            logger.warning(
                "CreateCaseBT did not succeed for actor '%s' / case '%s': %s",
                actor_id,
                case_id,
                result.feedback_message,
            )
    except Exception as e:
        logger.error(
            "Error in create_case for activity %s: %s",
            event.activity_id,
            str(e),
        )


def engage_case(event: EngageCaseReceivedEvent, dl: DataLayer) -> None:
    from vultron.core.behaviors.bridge import BTBridge
    from vultron.core.behaviors.report.prioritize_tree import (
        create_engage_case_tree,
    )

    try:
        actor_id = event.actor_id
        case_id = event.object_id

        logger.info(
            "Actor '%s' engages case '%s' (RM → ACCEPTED)", actor_id, case_id
        )

        bridge = BTBridge(datalayer=dl)
        tree = create_engage_case_tree(case_id=case_id, actor_id=actor_id)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=actor_id, activity=event
        )

        if result.status.name != "SUCCESS":
            logger.warning(
                "EngageCaseBT did not succeed for actor '%s' / case '%s': %s",
                actor_id,
                case_id,
                result.feedback_message,
            )
    except Exception as e:
        logger.error(
            "Error in engage_case for activity %s: %s",
            event.activity_id,
            str(e),
        )


def defer_case(event: DeferCaseReceivedEvent, dl: DataLayer) -> None:
    from vultron.core.behaviors.bridge import BTBridge
    from vultron.core.behaviors.report.prioritize_tree import (
        create_defer_case_tree,
    )

    try:
        actor_id = event.actor_id
        case_id = event.object_id

        logger.info(
            "Actor '%s' defers case '%s' (RM → DEFERRED)", actor_id, case_id
        )

        bridge = BTBridge(datalayer=dl)
        tree = create_defer_case_tree(case_id=case_id, actor_id=actor_id)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=actor_id, activity=event
        )

        if result.status.name != "SUCCESS":
            logger.warning(
                "DeferCaseBT did not succeed for actor '%s' / case '%s': %s",
                actor_id,
                case_id,
                result.feedback_message,
            )
    except Exception as e:
        logger.error(
            "Error in defer_case for activity %s: %s",
            event.activity_id,
            str(e),
        )


def add_report_to_case(
    event: AddReportToCaseReceivedEvent, dl: DataLayer
) -> None:
    try:
        report_id = event.object_id
        case_id = event.target_id
        case = cast(CaseModel, dl.read(case_id))

        if case is None:
            logger.warning("add_report_to_case: case '%s' not found", case_id)
            return

        existing_report_ids = [
            (r.as_id if hasattr(r, "as_id") else r)
            for r in case.vulnerability_reports
        ]
        if report_id in existing_report_ids:
            logger.info(
                "Report '%s' already in case '%s' — skipping (idempotent)",
                report_id,
                case_id,
            )
            return

        case.vulnerability_reports.append(report_id)
        dl.save(case)
        logger.info("Added report '%s' to case '%s'", report_id, case_id)

    except Exception as e:
        logger.error(
            "Error in add_report_to_case for activity %s: %s",
            event.activity_id,
            str(e),
        )


def close_case(event: CloseCaseReceivedEvent, dl: DataLayer) -> None:
    try:
        actor_id = event.actor_id
        case_id = event.object_id

        logger.info("Actor '%s' is closing case '%s'", actor_id, case_id)

        close_activity = VultronActivity(
            as_type="Leave",
            actor=actor_id,
            as_object=case_id,
        )
        try:
            dl.create(close_activity)
            logger.info("Created Leave activity %s", close_activity.as_id)
        except ValueError:
            logger.info(
                "Leave activity for case '%s' already exists — skipping (idempotent)",
                case_id,
            )
            return

        actor_obj = dl.read(actor_id)
        if actor_obj is not None and hasattr(actor_obj, "outbox"):
            actor_obj.outbox.items.append(close_activity.as_id)
            dl.save(actor_obj)
            logger.info(
                "Added Leave activity %s to actor %s outbox",
                close_activity.as_id,
                actor_id,
            )

    except Exception as e:
        logger.error(
            "Error in close_case for activity %s: %s",
            event.activity_id,
            str(e),
        )


def _check_participant_embargo_acceptance(
    case: CaseModel, dl: DataLayer
) -> None:
    active_embargo = case.active_embargo
    if active_embargo is None:
        return
    embargo_id = (
        active_embargo.as_id
        if hasattr(active_embargo, "as_id")
        else str(active_embargo)
    )
    for actor_id, participant_id in case.actor_participant_index.items():
        participant = dl.read(participant_id)
        if participant is None:
            logger.warning(
                "update_case: could not read participant '%s' for embargo acceptance check",
                participant_id,
            )
            continue
        if not hasattr(participant, "accepted_embargo_ids"):
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


def update_case(event: UpdateCaseReceivedEvent, dl: DataLayer) -> None:
    try:
        actor_id = event.actor_id
        case_id = event.object_id

        stored_case = cast(CaseModel, dl.read(case_id))
        if stored_case is None:
            logger.warning(
                "update_case: case '%s' not found in DataLayer — skipping",
                case_id,
            )
            return

        owner_id = (
            stored_case.attributed_to.as_id
            if hasattr(stored_case.attributed_to, "as_id")
            else (
                str(stored_case.attributed_to)
                if stored_case.attributed_to
                else None
            )
        )
        if owner_id != actor_id:
            logger.warning(
                "update_case: actor '%s' is not the owner of case '%s' — skipping update",
                actor_id,
                case_id,
            )
            return

        _check_participant_embargo_acceptance(stored_case, dl)

        if event.object_type == "VulnerabilityCase" and event.case is not None:
            for field in ("name", "summary", "content"):
                value = getattr(event.case, field, None)
                if value is not None:
                    setattr(stored_case, field, value)
            dl.save(stored_case)
            logger.info("Actor '%s' updated case '%s'", actor_id, case_id)
        else:
            logger.info(
                "update_case: object for case '%s' is a reference only — no fields to apply",
                case_id,
            )

    except Exception as e:
        logger.error(
            "Error in update_case for activity %s: %s",
            event.activity_id,
            str(e),
        )
