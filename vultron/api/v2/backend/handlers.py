"""
Provides handler functions for specific activities in the Vultron API v2 backend.
"""

import logging
from functools import wraps

from vultron.api.v2.errors import (
    VultronApiHandlerMissingSemanticError,
    VultronApiHandlerSemanticMismatchError,
)
from vultron.enums import MessageSemantics
from vultron.semantic_map import find_matching_semantics
from vultron.types import DispatchActivity

logger = logging.getLogger(__name__)


def verify_semantics(expected_semantic_type: MessageSemantics):
    def decorator(func):
        @wraps(func)
        def wrapper(dispatchable: DispatchActivity):
            if not dispatchable.semantic_type:
                logger.error(
                    "Dispatchable activity %s is missing semantic_type",
                    dispatchable,
                )
                raise VultronApiHandlerMissingSemanticError()

            computed = find_matching_semantics(dispatchable.payload)

            if computed != expected_semantic_type:
                logger.error(
                    "Dispatchable activity %s claims semantic_type %s that does not match its payload (%s)",
                    dispatchable,
                    expected_semantic_type,
                    computed,
                )
                raise VultronApiHandlerSemanticMismatchError(
                    expected=expected_semantic_type, actual=computed
                )

            return func(dispatchable)

        return wrapper

    return decorator


@verify_semantics(MessageSemantics.CREATE_REPORT)
def create_report(dispatchable: DispatchActivity) -> None:
    """
    Process a CreateReport activity (Create(VulnerabilityReport)).

    Stores the VulnerabilityReport object in the data layer and the Create activity.

    Args:
        dispatchable: DispatchActivity containing the as_Create with VulnerabilityReport object
    """
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
    from vultron.as_vocab.objects.vulnerability_report import (
        VulnerabilityReport,
    )

    activity = dispatchable.payload

    # Extract the created report
    created_obj = activity.as_object
    if not isinstance(created_obj, VulnerabilityReport):
        logger.error(
            "Expected VulnerabilityReport in create_report, got %s",
            type(created_obj).__name__,
        )
        return None

    actor_id = activity.actor
    logger.info(
        "Actor '%s' creates VulnerabilityReport '%s' (ID: %s)",
        actor_id,
        created_obj.name,
        created_obj.as_id,
    )

    # Get data layer
    dl = get_datalayer()

    # Store the report object
    try:
        dl.create(created_obj)
        logger.info(
            "Stored VulnerabilityReport with ID: %s", created_obj.as_id
        )
    except ValueError as e:
        logger.warning(
            "VulnerabilityReport %s already exists: %s", created_obj.as_id, e
        )

    # Store the create activity
    try:
        dl.create(activity)
        logger.info("Stored CreateReport activity with ID: %s", activity.as_id)
    except ValueError as e:
        logger.warning(
            "CreateReport activity %s already exists: %s", activity.as_id, e
        )

    return None


@verify_semantics(MessageSemantics.SUBMIT_REPORT)
def submit_report(dispatchable: DispatchActivity) -> None:
    """
    Process a SubmitReport activity (Offer(VulnerabilityReport)).

    Stores both the VulnerabilityReport object and the Offer activity in the data layer.

    Args:
        dispatchable: DispatchActivity containing the as_Offer with VulnerabilityReport object
    """
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
    from vultron.as_vocab.objects.vulnerability_report import (
        VulnerabilityReport,
    )

    activity = dispatchable.payload

    # Extract the offered report
    offered_obj = activity.as_object
    if not isinstance(offered_obj, VulnerabilityReport):
        logger.error(
            "Expected VulnerabilityReport in submit_report, got %s",
            type(offered_obj).__name__,
        )
        return None

    actor_id = activity.actor
    logger.info(
        "Actor '%s' submits VulnerabilityReport '%s' (ID: %s)",
        actor_id,
        offered_obj.name,
        offered_obj.as_id,
    )

    # Get data layer
    dl = get_datalayer()

    # Store the report object
    try:
        dl.create(offered_obj)
        logger.info(
            "Stored VulnerabilityReport with ID: %s", offered_obj.as_id
        )
    except ValueError as e:
        logger.warning(
            "VulnerabilityReport %s already exists: %s", offered_obj.as_id, e
        )

    # Store the offer activity
    try:
        dl.create(activity)
        logger.info("Stored SubmitReport activity with ID: %s", activity.as_id)
    except ValueError as e:
        logger.warning(
            "SubmitReport activity %s already exists: %s", activity.as_id, e
        )

    return None


@verify_semantics(MessageSemantics.VALIDATE_REPORT)
def validate_report(dispatchable: DispatchActivity) -> None:
    """
    Process a ValidateReport activity (Accept(Offer(VulnerabilityReport))).

    Uses behavior tree execution to orchestrate report validation workflow,
    including status updates, case creation, and activity generation.

    Args:
        dispatchable: DispatchActivity containing the as_Accept with Offer object
    """
    from py_trees.common import Status

    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
    from vultron.as_vocab.objects.vulnerability_report import (
        VulnerabilityReport,
    )
    from vultron.behaviors.bridge import BTBridge
    from vultron.behaviors.report.validate_tree import (
        create_validate_report_tree,
    )

    activity = dispatchable.payload

    # Rehydrate the accepted offer and report (validation phase)
    try:
        accepted_offer = rehydrate(activity.as_object)
        accepted_report = rehydrate(accepted_offer.as_object)
    except (ValueError, KeyError) as e:
        logger.error(
            "Failed to rehydrate offer or report in validate_report: %s", e
        )
        return None

    # Verify we have a VulnerabilityReport
    if not isinstance(accepted_report, VulnerabilityReport):
        logger.error(
            "Expected VulnerabilityReport in validate_report, got %s",
            type(accepted_report).__name__,
        )
        return None

    # Rehydrate actor
    try:
        actor = rehydrate(activity.actor)
        actor_id = actor.as_id
    except (ValueError, KeyError) as e:
        logger.error("Failed to rehydrate actor in validate_report: %s", e)
        return None

    logger.info(
        "Actor '%s' validates VulnerabilityReport '%s' via BT execution",
        actor_id,
        accepted_report.as_id,
    )

    # Delegate to behavior tree for workflow orchestration
    report_id = accepted_report.as_id
    offer_id = accepted_offer.as_id

    dl = get_datalayer()
    bridge = BTBridge(datalayer=dl)

    # Create and execute validation tree
    tree = create_validate_report_tree(report_id=report_id, offer_id=offer_id)

    # Log tree structure for visibility (DEBUG level logs structure, can be enabled if needed)
    tree_viz = BTBridge.get_tree_visualization(tree, show_status=False)
    logger.debug("Validation BT structure:\n%s", tree_viz)

    result = bridge.execute_with_setup(
        tree, actor_id=actor_id, activity=activity
    )

    # Handle BT execution results with detailed feedback
    if result.status == Status.SUCCESS:
        logger.info(
            "✓ BT execution succeeded for report validation: %s (feedback: %s)",
            report_id,
            result.feedback_message or "none",
        )
    elif result.status == Status.FAILURE:
        logger.error(
            "✗ BT execution failed for report validation: %s - %s",
            report_id,
            result.feedback_message,
        )
        if result.errors:
            for error in result.errors:
                logger.error("  - %s", error)
    else:
        logger.warning(
            "⚠ BT execution incomplete for report validation: %s (status=%s)",
            report_id,
            result.status,
        )

    return None


@verify_semantics(MessageSemantics.INVALIDATE_REPORT)
def invalidate_report(dispatchable: DispatchActivity) -> None:
    """
    Process an InvalidateReport activity (TentativeReject(Offer(VulnerabilityReport))).

    Updates the offer status to TENTATIVELY_REJECTED and report status to INVALID.

    Args:
        dispatchable: DispatchActivity containing the as_TentativeReject with Offer object
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.api.v2.data.status import (
        OfferStatus,
        ReportStatus,
        set_status,
    )
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
    from vultron.bt.report_management.states import RM
    from vultron.enums import OfferStatusEnum

    activity = dispatchable.payload

    try:
        # Rehydrate actor, offer, and report
        actor = rehydrate(obj=activity.actor)
        actor_id = actor.as_id

        # Rehydrate the rejected offer (may be embedded or reference)
        rejected_offer = rehydrate(activity.as_object)

        # Rehydrate the report that's the subject of the offer
        subject_of_offer = rehydrate(rejected_offer.as_object)

        logger.info(
            "Actor '%s' tentatively rejects offer '%s' of VulnerabilityReport '%s'",
            actor_id,
            rejected_offer.as_id,
            subject_of_offer.as_id,
        )

        # Update offer status
        offer_status = OfferStatus(
            object_type=rejected_offer.as_type,
            object_id=rejected_offer.as_id,
            status=OfferStatusEnum.TENTATIVELY_REJECTED,
            actor_id=actor_id,
        )
        set_status(offer_status)
        logger.info(
            "Set offer '%s' status to TENTATIVELY_REJECTED",
            rejected_offer.as_id,
        )

        # Update report status
        report_status = ReportStatus(
            object_type=subject_of_offer.as_type,
            object_id=subject_of_offer.as_id,
            status=RM.INVALID,
            actor_id=actor_id,
        )
        set_status(report_status)
        logger.info(
            "Set report '%s' status to INVALID", subject_of_offer.as_id
        )

        # Store the activity
        dl = get_datalayer()
        try:
            dl.create(activity)
            logger.info(
                "Stored InvalidateReport activity with ID: %s", activity.as_id
            )
        except ValueError as e:
            logger.warning(
                "InvalidateReport activity %s already exists: %s",
                activity.as_id,
                e,
            )

    except Exception as e:
        logger.error(
            "Error invalidating report in activity %s: %s",
            activity.as_id,
            str(e),
        )

    return None


@verify_semantics(MessageSemantics.ACK_REPORT)
def ack_report(dispatchable: DispatchActivity) -> None:
    """
    Process an AckReport activity (Read(Offer(VulnerabilityReport))).

    Acknowledges receipt of a vulnerability report submission.
    Stores the activity and logs the acknowledgement.

    Args:
        dispatchable: DispatchActivity containing the as_Read with Offer object
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer

    activity = dispatchable.payload

    try:
        # Rehydrate actor and offer
        actor = rehydrate(obj=activity.actor)
        actor_id = actor.as_id

        # Rehydrate the offer being acknowledged
        offer = rehydrate(activity.as_object)

        # Rehydrate the report that's the subject of the offer
        subject_of_offer = rehydrate(offer.as_object)

        logger.info(
            "Actor '%s' acknowledges receipt of offer '%s' of VulnerabilityReport '%s'",
            actor_id,
            offer.as_id,
            subject_of_offer.as_id,
        )

        # Store the activity
        dl = get_datalayer()
        try:
            dl.create(activity)
            logger.info(
                "Stored AckReport activity with ID: %s", activity.as_id
            )
        except ValueError as e:
            logger.warning(
                "AckReport activity %s already exists: %s", activity.as_id, e
            )

    except Exception as e:
        logger.error(
            "Error acknowledging report in activity %s: %s",
            activity.as_id,
            str(e),
        )

    return None


@verify_semantics(MessageSemantics.CLOSE_REPORT)
def close_report(dispatchable: DispatchActivity) -> None:
    """
    Process a CloseReport activity (Reject(Offer(VulnerabilityReport))).

    Updates the offer status to REJECTED and report status to CLOSED.

    Args:
        dispatchable: DispatchActivity containing the as_Reject with Offer object
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.api.v2.data.status import (
        OfferStatus,
        ReportStatus,
        set_status,
    )
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
    from vultron.bt.report_management.states import RM
    from vultron.enums import OfferStatusEnum

    activity = dispatchable.payload

    try:
        # Rehydrate actor, offer, and report
        actor = rehydrate(obj=activity.actor)
        actor_id = actor.as_id

        # Rehydrate the rejected offer (may be embedded or reference)
        rejected_offer = rehydrate(activity.as_object)

        # Rehydrate the report that's the subject of the offer
        subject_of_offer = rehydrate(rejected_offer.as_object)

        logger.info(
            "Actor '%s' rejects offer '%s' of VulnerabilityReport '%s'",
            actor_id,
            rejected_offer.as_id,
            subject_of_offer.as_id,
        )

        # Update offer status
        offer_status = OfferStatus(
            object_type=rejected_offer.as_type,
            object_id=rejected_offer.as_id,
            status=OfferStatusEnum.REJECTED,
            actor_id=actor_id,
        )
        set_status(offer_status)
        logger.info("Set offer '%s' status to REJECTED", rejected_offer.as_id)

        # Update report status
        report_status = ReportStatus(
            object_type=subject_of_offer.as_type,
            object_id=subject_of_offer.as_id,
            status=RM.CLOSED,
            actor_id=actor_id,
        )
        set_status(report_status)
        logger.info("Set report '%s' status to CLOSED", subject_of_offer.as_id)

        # Store the activity
        dl = get_datalayer()
        try:
            dl.create(activity)
            logger.info(
                "Stored CloseReport activity with ID: %s", activity.as_id
            )
        except ValueError as e:
            logger.warning(
                "CloseReport activity %s already exists: %s",
                activity.as_id,
                e,
            )

    except Exception as e:
        logger.error(
            "Error closing report in activity %s: %s",
            activity.as_id,
            str(e),
        )

    return None


@verify_semantics(MessageSemantics.CREATE_CASE)
def create_case(dispatchable: DispatchActivity) -> None:
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
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
    from vultron.behaviors.bridge import BTBridge
    from vultron.behaviors.case.create_tree import create_create_case_tree

    activity = dispatchable.payload

    try:
        actor = rehydrate(obj=activity.actor)
        actor_id = actor.as_id
        case = rehydrate(obj=activity.as_object)
        case_id = case.as_id

        logger.info("Actor '%s' creates case '%s'", actor_id, case_id)

        dl = get_datalayer()
        bridge = BTBridge(datalayer=dl)
        tree = create_create_case_tree(case_obj=case, actor_id=actor_id)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=actor_id, activity=activity
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
            activity.as_id,
            str(e),
        )


@verify_semantics(MessageSemantics.ENGAGE_CASE)
def engage_case(dispatchable: DispatchActivity) -> None:
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
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
    from vultron.behaviors.bridge import BTBridge
    from vultron.behaviors.report.prioritize_tree import (
        create_engage_case_tree,
    )

    activity = dispatchable.payload

    try:
        actor = rehydrate(obj=activity.actor)
        actor_id = actor.as_id
        case = rehydrate(obj=activity.as_object)
        case_id = case.as_id

        logger.info(
            "Actor '%s' engages case '%s' (RM → ACCEPTED)", actor_id, case_id
        )

        dl = get_datalayer()
        bridge = BTBridge(datalayer=dl)
        tree = create_engage_case_tree(case_id=case_id, actor_id=actor_id)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=actor_id, activity=activity
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
            activity.as_id,
            str(e),
        )

    return None


@verify_semantics(MessageSemantics.DEFER_CASE)
def defer_case(dispatchable: DispatchActivity) -> None:
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
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
    from vultron.behaviors.bridge import BTBridge
    from vultron.behaviors.report.prioritize_tree import create_defer_case_tree

    activity = dispatchable.payload

    try:
        actor = rehydrate(obj=activity.actor)
        actor_id = actor.as_id
        case = rehydrate(obj=activity.as_object)
        case_id = case.as_id

        logger.info(
            "Actor '%s' defers case '%s' (RM → DEFERRED)", actor_id, case_id
        )

        dl = get_datalayer()
        bridge = BTBridge(datalayer=dl)
        tree = create_defer_case_tree(case_id=case_id, actor_id=actor_id)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=actor_id, activity=activity
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
            activity.as_id,
            str(e),
        )

    return None


@verify_semantics(MessageSemantics.ADD_REPORT_TO_CASE)
def add_report_to_case(dispatchable: DispatchActivity) -> None:
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
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer

    activity = dispatchable.payload

    try:
        report = rehydrate(obj=activity.as_object)
        case = rehydrate(obj=activity.target)
        report_id = report.as_id
        case_id = case.as_id

        dl = get_datalayer()

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
            activity.as_id,
            str(e),
        )


@verify_semantics(MessageSemantics.SUGGEST_ACTOR_TO_CASE)
def suggest_actor_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug("suggest_actor_to_case handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.ACCEPT_SUGGEST_ACTOR_TO_CASE)
def accept_suggest_actor_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "accept_suggest_actor_to_case handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.REJECT_SUGGEST_ACTOR_TO_CASE)
def reject_suggest_actor_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "reject_suggest_actor_to_case handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER)
def offer_case_ownership_transfer(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "offer_case_ownership_transfer handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER)
def accept_case_ownership_transfer(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "accept_case_ownership_transfer handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER)
def reject_case_ownership_transfer(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "reject_case_ownership_transfer handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.INVITE_ACTOR_TO_CASE)
def invite_actor_to_case(dispatchable: DispatchActivity) -> None:
    """
    Process an Invite(actor=CaseOwner, object=Actor, target=Case) activity.

    This arrives in the *invited actor's* inbox. The handler persists the
    Invite so that the actor can later accept or reject it.

    Args:
        dispatchable: DispatchActivity containing the RmInviteToCase activity
    """
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer

    activity = dispatchable.payload

    try:
        dl = get_datalayer()
        existing = dl.get(activity.as_type.value, activity.as_id)
        if existing is not None:
            logger.info(
                "Invite '%s' already stored — skipping (idempotent)",
                activity.as_id,
            )
            return None

        dl.create(activity)
        logger.info(
            "Stored invite '%s' (actor=%s, target=%s)",
            activity.as_id,
            activity.as_actor,
            activity.target,
        )

    except Exception as e:
        logger.error(
            "Error in invite_actor_to_case for activity %s: %s",
            activity.as_id,
            str(e),
        )


@verify_semantics(MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE)
def accept_invite_actor_to_case(dispatchable: DispatchActivity) -> None:
    """
    Process an Accept(object=RmInviteToCase) activity.

    This arrives in the *case owner's* inbox after the invited actor accepts.
    The handler creates a CaseParticipant for the invited actor and adds them
    to the case's participant list. Idempotent: if the participant is already
    in the case, the handler returns without side effects (ID-04-004).

    Args:
        dispatchable: DispatchActivity containing the RmAcceptInviteToCase
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.api.v2.datalayer.db_record import object_to_record
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
    from vultron.as_vocab.objects.case_participant import CaseParticipant

    activity = dispatchable.payload

    try:
        invite = rehydrate(obj=activity.as_object)
        case = rehydrate(obj=invite.target)
        invitee_ref = invite.as_object
        invitee_id = (
            invitee_ref.as_id
            if hasattr(invitee_ref, "as_id")
            else str(invitee_ref)
        )
        case_id = case.as_id

        dl = get_datalayer()

        existing_ids = [
            (p.as_id if hasattr(p, "as_id") else p)
            for p in case.case_participants
        ]
        if invitee_id in existing_ids:
            logger.info(
                "Actor '%s' already participant in case '%s' — skipping (idempotent)",
                invitee_id,
                case_id,
            )
            return None

        participant = CaseParticipant(
            id=f"{case_id}/participants/{invitee_id.split('/')[-1]}",
            attributed_to=invitee_id,
            context=case_id,
        )
        dl.create(participant)

        case.case_participants.append(participant.as_id)
        dl.update(case_id, object_to_record(case))

        logger.info(
            "Added participant '%s' to case '%s' via accepted invite",
            invitee_id,
            case_id,
        )

    except Exception as e:
        logger.error(
            "Error in accept_invite_actor_to_case for activity %s: %s",
            activity.as_id,
            str(e),
        )


@verify_semantics(MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE)
def reject_invite_actor_to_case(dispatchable: DispatchActivity) -> None:
    """
    Process a Reject(object=RmInviteToCase) activity.

    This arrives in the *case owner's* inbox. The handler logs the rejection;
    no state change is required.

    Args:
        dispatchable: DispatchActivity containing the RmRejectInviteToCase
    """
    activity = dispatchable.payload

    try:
        invite_ref = activity.as_object
        invite_id = (
            invite_ref.as_id
            if hasattr(invite_ref, "as_id")
            else str(invite_ref)
        )
        logger.info(
            "Actor '%s' rejected invitation '%s'",
            activity.as_actor,
            invite_id,
        )

    except Exception as e:
        logger.error(
            "Error in reject_invite_actor_to_case for activity %s: %s",
            activity.as_id,
            str(e),
        )


@verify_semantics(MessageSemantics.CREATE_EMBARGO_EVENT)
def create_embargo_event(dispatchable: DispatchActivity) -> None:
    logger.debug("create_embargo_event handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE)
def add_embargo_event_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug("add_embargo_event_to_case handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE)
def remove_embargo_event_from_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "remove_embargo_event_from_case handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE)
def announce_embargo_event_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "announce_embargo_event_to_case handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.INVITE_TO_EMBARGO_ON_CASE)
def invite_to_embargo_on_case(dispatchable: DispatchActivity) -> None:
    logger.debug("invite_to_embargo_on_case handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE)
def accept_invite_to_embargo_on_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "accept_invite_to_embargo_on_case handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE)
def reject_invite_to_embargo_on_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "reject_invite_to_embargo_on_case handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.CLOSE_CASE)
def close_case(dispatchable: DispatchActivity) -> None:
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
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
    from vultron.as_vocab.activities.case import RmCloseCase

    activity = dispatchable.payload

    try:
        actor = rehydrate(obj=activity.actor)
        actor_id = actor.as_id
        case = rehydrate(obj=activity.as_object)
        case_id = case.as_id

        logger.info("Actor '%s' is closing case '%s'", actor_id, case_id)

        dl = get_datalayer()

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
            activity.as_id,
            str(e),
        )


@verify_semantics(MessageSemantics.CREATE_CASE_PARTICIPANT)
def create_case_participant(dispatchable: DispatchActivity) -> None:
    """
    Process a Create(CaseParticipant) activity.

    Persists the new CaseParticipant to the DataLayer. Because
    CaseParticipant uses `attributed_to` (a standard as_Object field) for
    the actor reference, the full object survives inbox deserialization.
    Idempotent: if a participant with the same ID already exists, the
    handler logs at INFO and returns without side effects (ID-04-004).

    Args:
        dispatchable: DispatchActivity containing the as_Create with
                      CaseParticipant object
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer

    activity = dispatchable.payload

    try:
        participant = rehydrate(obj=activity.as_object)
        participant_id = participant.as_id

        dl = get_datalayer()

        existing = dl.get(participant.as_type.value, participant_id)
        if existing is not None:
            logger.info(
                "Participant '%s' already exists — skipping (idempotent)",
                participant_id,
            )
            return None

        dl.create(participant)
        logger.info("Created participant '%s'", participant_id)

    except Exception as e:
        logger.error(
            "Error in create_case_participant for activity %s: %s",
            activity.as_id,
            str(e),
        )


@verify_semantics(MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE)
def add_case_participant_to_case(dispatchable: DispatchActivity) -> None:
    """
    Process an AddParticipantToCase activity
    (Add(CaseParticipant, target=VulnerabilityCase)).

    Appends the participant reference to the case's case_participants list
    and persists the updated case to the DataLayer. Idempotent: re-adding a
    participant already in the case succeeds without side effects (ID-04-004).

    Args:
        dispatchable: DispatchActivity containing the as_Add with
                      CaseParticipant object and VulnerabilityCase target
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.api.v2.datalayer.db_record import object_to_record
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer

    activity = dispatchable.payload

    try:
        participant = rehydrate(obj=activity.as_object)
        case = rehydrate(obj=activity.target)
        participant_id = participant.as_id
        case_id = case.as_id

        dl = get_datalayer()

        existing_ids = [
            (p.as_id if hasattr(p, "as_id") else p)
            for p in case.case_participants
        ]
        if participant_id in existing_ids:
            logger.info(
                "Participant '%s' already in case '%s' — skipping (idempotent)",
                participant_id,
                case_id,
            )
            return None

        case.case_participants.append(participant_id)
        dl.update(case_id, object_to_record(case))

        logger.info(
            "Added participant '%s' to case '%s'", participant_id, case_id
        )

    except Exception as e:
        logger.error(
            "Error in add_case_participant_to_case for activity %s: %s",
            activity.as_id,
            str(e),
        )


@verify_semantics(MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE)
def remove_case_participant_from_case(dispatchable: DispatchActivity) -> None:
    """
    Process a Remove(CaseParticipant, target=VulnerabilityCase) activity.

    Removes the participant reference from the case's case_participants list
    and persists the updated case. Idempotent: if the participant is not in
    the case, the handler returns without error (ID-04-004).

    Args:
        dispatchable: DispatchActivity containing the as_Remove with
                      CaseParticipant object and VulnerabilityCase target
    """
    from vultron.api.v2.data.rehydration import rehydrate
    from vultron.api.v2.datalayer.db_record import object_to_record
    from vultron.api.v2.datalayer.tinydb_backend import get_datalayer

    activity = dispatchable.payload

    try:
        participant = rehydrate(obj=activity.as_object)
        case = rehydrate(obj=activity.target)
        participant_id = participant.as_id
        case_id = case.as_id

        dl = get_datalayer()

        existing_ids = [
            (p.as_id if hasattr(p, "as_id") else p)
            for p in case.case_participants
        ]
        if participant_id not in existing_ids:
            logger.info(
                "Participant '%s' not in case '%s' — skipping (idempotent)",
                participant_id,
                case_id,
            )
            return None

        case.case_participants = [
            p
            for p in case.case_participants
            if (p.as_id if hasattr(p, "as_id") else p) != participant_id
        ]
        dl.update(case_id, object_to_record(case))

        logger.info(
            "Removed participant '%s' from case '%s'",
            participant_id,
            case_id,
        )

    except Exception as e:
        logger.error(
            "Error in remove_case_participant_from_case for activity %s: %s",
            activity.as_id,
            str(e),
        )


@verify_semantics(MessageSemantics.CREATE_NOTE)
def create_note(dispatchable: DispatchActivity) -> None:
    logger.debug("create_note handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.ADD_NOTE_TO_CASE)
def add_note_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug("add_note_to_case handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.REMOVE_NOTE_FROM_CASE)
def remove_note_from_case(dispatchable: DispatchActivity) -> None:
    logger.debug("remove_note_from_case handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.CREATE_CASE_STATUS)
def create_case_status(dispatchable: DispatchActivity) -> None:
    logger.debug("create_case_status handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.ADD_CASE_STATUS_TO_CASE)
def add_case_status_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug("add_case_status_to_case handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.CREATE_PARTICIPANT_STATUS)
def create_participant_status(dispatchable: DispatchActivity) -> None:
    logger.debug("create_participant_status handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT)
def add_participant_status_to_participant(
    dispatchable: DispatchActivity,
) -> None:
    logger.debug(
        "add_participant_status_to_participant handler called: %s",
        dispatchable,
    )
    return None


@verify_semantics(MessageSemantics.UNKNOWN)
def unknown(dispatchable: DispatchActivity) -> None:
    logger.warning("unknown handler called for dispatchable: %s", dispatchable)
    return None
