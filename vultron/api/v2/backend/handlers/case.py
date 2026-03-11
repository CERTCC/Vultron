"""
Handler functions for vulnerability case activities.
"""

import logging

from vultron.api.v2.backend.handlers._base import verify_semantics
from vultron.core.models.events import MessageSemantics
from vultron.types import DispatchActivity

from vultron.api.v2.datalayer.abc import DataLayer

logger = logging.getLogger(__name__)


@verify_semantics(MessageSemantics.CREATE_CASE)
def create_case(dispatchable: DispatchActivity, dl: DataLayer) -> None:
    """
    Process a CreateCase activity (Create(VulnerabilityCase)).

    Persists the new VulnerabilityCase to the DataLayer, creates the
    associated CaseActor (CM-02-001), and emits a CreateCase activity to
    the actor outbox. Idempotent: re-processing an already-stored case
    succeeds without side effects (ID-04-004).

    Args:
        dispatchable: DispatchActivity containing the as_Create with
                      VulnerabilityCase object
    """
    from vultron.core.behaviors.bridge import BTBridge
    from vultron.core.behaviors.case.create_tree import create_create_case_tree

    payload = dispatchable.payload

    try:
        actor_id = payload.actor_id
        case = dispatchable.wire_object
        case_id = payload.object_id

        logger.info("Actor '%s' creates case '%s'", actor_id, case_id)

        bridge = BTBridge(datalayer=dl)
        tree = create_create_case_tree(case_obj=case, actor_id=actor_id)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=actor_id, activity=dispatchable.wire_activity
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
            payload.activity_id,
            str(e),
        )


@verify_semantics(MessageSemantics.ENGAGE_CASE)
def engage_case(dispatchable: DispatchActivity, dl: DataLayer) -> None:
    """
    Process an RmEngageCase activity (Join(VulnerabilityCase)).

    The sending actor has decided to engage the case (RM → ACCEPTED). Records
    their RM state transition in their CaseParticipant.participant_status.

    RM is participant-specific: each CaseParticipant tracks its own RM state
    independently of other participants in the same case.

    Args:
        dispatchable: DispatchActivity containing the as_Join with
                      VulnerabilityCase object
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.core.behaviors.bridge import BTBridge
    from vultron.core.behaviors.report.prioritize_tree import (
        create_engage_case_tree,
    )

    payload = dispatchable.payload

    try:
        actor_id = payload.actor_id
        case = rehydrate(payload.object_id)
        case_id = payload.object_id

        logger.info(
            "Actor '%s' engages case '%s' (RM → ACCEPTED)", actor_id, case_id
        )

        bridge = BTBridge(datalayer=dl)
        tree = create_engage_case_tree(case_id=case_id, actor_id=actor_id)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=actor_id, activity=dispatchable.wire_activity
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
            payload.activity_id,
            str(e),
        )

    return None


@verify_semantics(MessageSemantics.DEFER_CASE)
def defer_case(dispatchable: DispatchActivity, dl: DataLayer) -> None:
    """
    Process an RmDeferCase activity (Ignore(VulnerabilityCase)).

    The sending actor has decided to defer the case (RM → DEFERRED). Records
    their RM state transition in their CaseParticipant.participant_status.

    RM is participant-specific: each CaseParticipant tracks its own RM state
    independently of other participants in the same case.

    Args:
        dispatchable: DispatchActivity containing the as_Ignore with
                      VulnerabilityCase object
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.core.behaviors.bridge import BTBridge
    from vultron.core.behaviors.report.prioritize_tree import (
        create_defer_case_tree,
    )

    payload = dispatchable.payload

    try:
        actor_id = payload.actor_id
        case = rehydrate(payload.object_id)
        case_id = payload.object_id

        logger.info(
            "Actor '%s' defers case '%s' (RM → DEFERRED)", actor_id, case_id
        )

        bridge = BTBridge(datalayer=dl)
        tree = create_defer_case_tree(case_id=case_id, actor_id=actor_id)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=actor_id, activity=dispatchable.wire_activity
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
            payload.activity_id,
            str(e),
        )

    return None


@verify_semantics(MessageSemantics.ADD_REPORT_TO_CASE)
def add_report_to_case(dispatchable: DispatchActivity, dl: DataLayer) -> None:
    """
    Process an AddReportToCase activity
    (Add(VulnerabilityReport, target=VulnerabilityCase)).

    Appends the report reference to the case's vulnerability_reports list
    and persists the updated case to the DataLayer. Idempotent: re-adding a
    report already in the case succeeds without side effects (ID-04-004).

    Args:
        dispatchable: DispatchActivity containing the as_Add with
                      VulnerabilityReport object and VulnerabilityCase target
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.api.v2.datalayer.db_record import object_to_record

    payload = dispatchable.payload

    try:
        report = rehydrate(payload.object_id)
        case = rehydrate(payload.target_id)
        report_id = payload.object_id
        case_id = payload.target_id

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
            return None

        case.vulnerability_reports.append(report_id)
        dl.update(case_id, object_to_record(case))

        logger.info("Added report '%s' to case '%s'", report_id, case_id)

    except Exception as e:
        logger.error(
            "Error in add_report_to_case for activity %s: %s",
            payload.activity_id,
            str(e),
        )


@verify_semantics(MessageSemantics.CLOSE_CASE)
def close_case(dispatchable: DispatchActivity, dl: DataLayer) -> None:
    """
    Process a CloseCase activity (Leave(VulnerabilityCase)).

    Records that the sending actor is leaving/closing their participation
    in the case. Emits an RmCloseCase activity to the actor outbox.

    Args:
        dispatchable: DispatchActivity containing the as_Leave with
                      VulnerabilityCase object
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.api.v2.datalayer.db_record import object_to_record
    from vultron.wire.as2.vocab.activities.case import RmCloseCase

    payload = dispatchable.payload

    try:
        actor_id = payload.actor_id
        case = rehydrate(payload.object_id)
        case_id = payload.object_id

        logger.info("Actor '%s' is closing case '%s'", actor_id, case_id)

        close_activity = RmCloseCase(
            actor=actor_id,
            object=case_id,
        )
        try:
            dl.create(close_activity)
            logger.info(
                "Created RmCloseCase activity %s", close_activity.as_id
            )
        except ValueError:
            logger.info(
                "RmCloseCase activity for case '%s' already exists"
                " — skipping (idempotent)",
                case_id,
            )
            return None

        actor_obj = dl.read(actor_id)
        if actor_obj is not None and hasattr(actor_obj, "outbox"):
            actor_obj.outbox.items.append(close_activity.as_id)
            dl.update(actor_id, object_to_record(actor_obj))
            logger.info(
                "Added RmCloseCase activity %s to actor %s outbox",
                close_activity.as_id,
                actor_id,
            )

    except Exception as e:
        logger.error(
            "Error in close_case for activity %s: %s",
            payload.activity_id,
            str(e),
        )


def _check_participant_embargo_acceptance(stored_case, dl, rehydrate) -> None:
    """Log a WARNING for each active participant who has not accepted the current embargo.

    Per CM-10-004: before sharing case updates with a participant, verify they
    have accepted the current active embargo.  Full enforcement (withholding the
    update) is deferred to PRIORITY-200; this prototype guard only logs.

    Args:
        stored_case: the VulnerabilityCase read from the DataLayer.
        dl: the DataLayer instance (unused directly; rehydrate uses it via DI).
        rehydrate: callable that expands URI references to full objects.
    """
    active_embargo = stored_case.active_embargo
    if active_embargo is None:
        return

    embargo_id = (
        active_embargo.as_id
        if hasattr(active_embargo, "as_id")
        else str(active_embargo)
    )

    for (
        actor_id,
        participant_id,
    ) in stored_case.actor_participant_index.items():
        try:
            participant = rehydrate(obj=participant_id)
        except Exception:
            logger.warning(
                "update_case: could not rehydrate participant '%s' for"
                " embargo acceptance check",
                participant_id,
            )
            continue

        if not hasattr(participant, "accepted_embargo_ids"):
            continue

        if embargo_id not in participant.accepted_embargo_ids:
            logger.warning(
                "update_case: participant '%s' (actor '%s') has not accepted"
                " the active embargo '%s' — case update will not be"
                " broadcast to this participant (CM-10-004)",
                participant_id,
                actor_id,
                embargo_id,
            )


@verify_semantics(MessageSemantics.UPDATE_CASE)
def update_case(dispatchable: DispatchActivity, dl: DataLayer) -> None:
    """
    Process an UpdateCase activity (Update(VulnerabilityCase)).

    Applies scalar field updates from the activity's object to the stored
    VulnerabilityCase in the DataLayer. Restricted to the case owner: if
    the sending actor is not the case owner, logs a WARNING and skips.
    Idempotent: last-write-wins on scalar fields.

    Also checks (CM-10-004) that each participant has accepted the active
    embargo before broadcasting; logs a WARNING for any who have not.
    Full enforcement is deferred to PRIORITY-200.

    Args:
        dispatchable: DispatchActivity containing the as_Update with
                      VulnerabilityCase object
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.api.v2.datalayer.db_record import object_to_record

    payload = dispatchable.payload

    try:
        actor_id = payload.actor_id
        incoming = rehydrate(payload.object_id)
        case_id = payload.object_id

        stored_case = dl.read(case_id)
        if stored_case is None:
            logger.warning(
                "update_case: case '%s' not found in DataLayer — skipping",
                case_id,
            )
            return None

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
                "update_case: actor '%s' is not the owner of case '%s'"
                " — skipping update",
                actor_id,
                case_id,
            )
            return None

        _check_participant_embargo_acceptance(stored_case, dl, rehydrate)

        if payload.object_type == "VulnerabilityCase":
            for field in ("name", "summary", "content"):
                value = getattr(incoming, field, None)
                if value is not None:
                    setattr(stored_case, field, value)
            dl.update(case_id, object_to_record(stored_case))
            logger.info("Actor '%s' updated case '%s'", actor_id, case_id)
        else:
            logger.info(
                "update_case: object for case '%s' is a reference only"
                " — no fields to apply",
                case_id,
            )

    except Exception as e:
        logger.error(
            "Error in update_case for activity %s: %s",
            payload.activity_id,
            str(e),
        )
