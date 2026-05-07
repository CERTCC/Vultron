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

"""
Shared helper utilities for trigger use-case functions.

These helpers are internal to the triggers package.  They raise domain
exceptions (``VultronNotFoundError``, ``VultronValidationError``) — no HTTP
framework imports allowed here.
"""

import logging

from vultron.core.models.protocols import (
    CaseModel,
    has_outbox,
    is_case_model,
    is_participant_model,
)
from vultron.core.states.rm import RM
from vultron.core.ports.case_persistence import (
    CasePersistence,
    CaseOutboxPersistence,
)
from vultron.errors import VultronNotFoundError, VultronValidationError

logger = logging.getLogger(__name__)


def _log_label(uri: str) -> str:
    """Return the last path segment of *uri* for use in log messages.

    Using only the final path segment instead of the full URI prevents
    CodeQL from treating tainted actor/activity IDs as clear-text secrets
    while still providing enough context for debug tracing.
    """
    return uri.rsplit("/", 1)[-1] if "/" in uri else uri


def resolve_actor(actor_id: str, dl: CasePersistence):
    """Resolve actor by full ID or short ID; raise VultronNotFoundError if absent."""
    actor = dl.read(actor_id)
    if actor is None:
        actor = dl.find_actor_by_short_id(actor_id)
    if actor is None:
        raise VultronNotFoundError("Actor", actor_id)
    return actor


def resolve_case(case_id: str, dl: CasePersistence) -> CaseModel:
    """Resolve a VulnerabilityCase by ID; raise domain error if absent or wrong type."""
    case_raw = dl.read(case_id)
    if case_raw is None:
        raise VultronNotFoundError("VulnerabilityCase", case_id)
    if not is_case_model(case_raw):
        raise VultronValidationError(
            f"Expected VulnerabilityCase, got {type(case_raw).__name__}."
        )
    return case_raw


def update_participant_rm_state(
    case_id: str, actor_id: str, new_rm_state: RM, dl: CasePersistence
) -> bool:
    """
    Append a new ParticipantStatus with new_rm_state to the actor's
    CaseParticipant in the given case and persist the updated participant.

    Handles both inline and string-reference participants.

    Returns ``True`` on success (including idempotent no-op), ``False`` when
    the case or participant is not found.
    """
    case_obj = dl.read(case_id)
    if not is_case_model(case_obj):
        logger.warning(
            "update_participant_rm_state: case '%s' not found or wrong type",
            case_id,
        )
        return False

    for participant_ref in case_obj.case_participants:
        if isinstance(participant_ref, str):
            participant_raw = dl.read(participant_ref)
            if participant_raw is None:
                continue
        else:
            participant_raw = participant_ref

        if not is_participant_model(participant_raw):
            continue

        participant = participant_raw

        actor_ref = participant.attributed_to
        p_actor_id = (
            actor_ref
            if isinstance(actor_ref, str)
            else getattr(actor_ref, "id_", str(actor_ref))
        )
        if p_actor_id == actor_id:
            if participant.participant_statuses:
                latest = participant.participant_statuses[-1]
                if latest.rm_state == new_rm_state:
                    logger.info(
                        "Participant '%s' already in RM state %s in case '%s' "
                        "(idempotent)",
                        actor_id,
                        new_rm_state,
                        case_id,
                    )
                    return True
            appended = participant.append_rm_state(
                rm_state=new_rm_state, actor=actor_id, context=case_id
            )
            if not appended:
                logger.warning(
                    "update_participant_rm_state: RM transition to %s blocked "
                    "for actor '%s' in case '%s'",
                    new_rm_state,
                    actor_id,
                    case_id,
                )
                return False
            dl.save(participant)
            logger.info(
                "Set participant '%s' RM state to %s in case '%s'",
                actor_id,
                new_rm_state,
                case_id,
            )
            return True

    logger.warning(
        "update_participant_rm_state: no CaseParticipant for actor '%s' "
        "in case '%s'; RM state not updated",
        actor_id,
        case_id,
    )
    return False


def outbox_ids(actor) -> set[str]:
    """Return the set of string activity IDs in actor.outbox.items."""
    if not (hasattr(actor, "outbox") and actor.outbox and actor.outbox.items):
        return set()
    return {item for item in actor.outbox.items if isinstance(item, str)}


def add_activity_to_outbox(
    actor_id: str, activity_id: str, dl: CaseOutboxPersistence
) -> None:
    """Append an activity ID to an actor's outbox and queue it for delivery.

    Appends *activity_id* to the actor's ``outbox.items`` persistent list
    (the AS2 outbox collection, visible via the outbox API endpoint) and
    also writes it to the delivery queue table (``{actor_id}_outbox``) so
    that :func:`outbox_handler` can drain and deliver it.

    Args:
        actor_id: The actor whose outbox should receive the activity.
        activity_id: The ID of the activity to queue for delivery.
        dl: The DataLayer to use for persistence.
    """
    # Persistent record: append to actor.outbox.items for the AS2 collection.
    actor_obj = dl.read(actor_id)
    if has_outbox(actor_obj):
        actor_obj.outbox.items.append(activity_id)
        dl.save(actor_obj)
        logger.debug(
            "Added activity '%s' to actor '%s' outbox.items",
            _log_label(activity_id),
            _log_label(actor_id),
        )
    else:
        logger.debug(
            "add_activity_to_outbox: actor '%s' not found or has no"
            " outbox field; skipping outbox.items update",
            _log_label(actor_id),
        )
    # Delivery queue: write to actor-scoped queue table for outbox_handler.
    dl.record_outbox_item(actor_id, activity_id)
    logger.debug(
        "Queued activity '%s' in delivery queue for actor '%s'",
        _log_label(activity_id),
        _log_label(actor_id),
    )


def find_embargo_proposal(case_id: str, dl: CasePersistence):
    """
    Find the first stored EmProposeEmbargoActivity for the given case.

    Returns None if no matching proposal is found.
    """
    for obj in dl.list_objects("Invite"):
        context = getattr(obj, "context", None)
        c_id = (
            context
            if isinstance(context, str)
            else getattr(context, "id_", str(context))
        )
        if c_id != case_id:
            continue
        embargo_ref = getattr(obj, "object_", None)
        if embargo_ref is None:
            continue
        embargo_id = (
            embargo_ref
            if isinstance(embargo_ref, str)
            else getattr(embargo_ref, "id_", None)
        )
        if embargo_id is None:
            continue
        emb = dl.read(embargo_id)
        if emb is not None and str(getattr(emb, "type_", "")) in (
            "Event",
            "EmbargoEvent",
        ):
            return obj
    return None
