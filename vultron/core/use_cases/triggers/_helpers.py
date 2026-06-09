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
import hashlib
from collections.abc import Callable

from vultron.core.models.protocols import (
    CaseModel,
    is_case_model,
    is_participant_model,
)
from vultron.core.states.rm import RM
from vultron.core.ports.case_persistence import (
    CasePersistence,
    CaseOutboxPersistence,
)
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.errors import VultronNotFoundError, VultronValidationError

logger = logging.getLogger(__name__)


def _log_label(uri: str) -> str:
    """Return a deterministic redacted label for IDs used in log messages.

    Do not log raw actor/activity identifiers (or URI segments) because they
    may be sensitive.  Instead, emit a short non-reversible hash token that
    still allows correlation across log lines.
    """
    digest = hashlib.sha256(uri.encode("utf-8")).hexdigest()[:12]
    return f"id:{digest}"


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
    if case_raw is None or not is_case_model(case_raw):
        case_raw = dl.find_case_by_short_id(case_id)
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


def outbox_ids(actor_id: str, dl: CaseOutboxPersistence) -> set[str]:
    """Return the set of string activity IDs in the actor's outbox queue.

    Uses ``outbox_list_for_actor`` when available (explicit actor scope),
    otherwise falls back to the actor-scoped ``outbox_list()``.

    Args:
        actor_id: The actor whose outbox should be queried.
        dl: The DataLayer to use for persistence.

    Returns:
        Set of activity IDs queued for delivery.
    """
    if hasattr(dl, "outbox_list_for_actor"):
        items: list[str] = dl.outbox_list_for_actor(actor_id)  # type: ignore[attr-defined]
        return set(items)
    return set(dl.outbox_list())


def add_activity_to_outbox(
    actor_id: str, activity_id: str, dl: CaseOutboxPersistence
) -> None:
    """Append an activity ID to an actor's outbox and queue it for delivery.

    Uses ``record_outbox_item`` to explicitly enqueue against *actor_id*,
    bypassing any actor-scope on *dl* itself.  This ensures correct delivery
    even when *dl* is a shared (unscoped) DataLayer instance.

    Args:
        actor_id: The actor whose outbox should receive the activity.
        activity_id: The ID of the activity to queue for delivery.
        dl: The DataLayer to use for persistence.
    """
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


def _coerce_embargo_event(raw_embargo: object, embargo_id: str) -> object:
    """Normalize a persisted embargo record; raise domain errors on failure."""
    from vultron.errors import VultronNotFoundError, VultronValidationError

    if getattr(raw_embargo, "type_", "") == "EmbargoEvent":
        return raw_embargo
    if raw_embargo is None:
        raise VultronNotFoundError("EmbargoEvent", embargo_id)
    raise VultronValidationError(
        f"Could not resolve EmbargoEvent '{embargo_id}'."
    )


def _is_case_owner(case: object | None, actor_id: str) -> bool:
    """Return True when ``actor_id`` matches the case owner."""
    from vultron.core.use_cases._helpers import _as_id

    if case is None:
        return False
    owner_id = _as_id(getattr(case, "attributed_to", None))
    return owner_id is not None and owner_id == actor_id


def _resolve_embargo_proposal(
    case: CaseModel, proposal_id: str | None, dl: CaseOutboxPersistence
):
    """Resolve the embargo proposal for a case."""
    from vultron.errors import VultronNotFoundError, VultronValidationError

    if proposal_id:
        proposal = dl.read(proposal_id)
        if proposal is None:
            raise VultronNotFoundError("EmbargoProposal", proposal_id)
    else:
        proposal = find_embargo_proposal(case.id_, dl)
        if proposal is None:
            raise VultronNotFoundError(
                "EmbargoProposal",
                f"(pending for case '{case.id_}')",
            )

    if getattr(proposal, "type_", "") != "Invite":
        raise VultronValidationError(
            f"Expected an EmProposeEmbargoActivity (embargo proposal), got "
            f"type '{getattr(proposal, 'type_', 'unknown')}'."
        )
    return proposal


def _resolve_embargo_id_from_proposal(proposal: object) -> str:
    """Return the embargo ID referenced by a proposal."""
    from vultron.errors import VultronValidationError

    embargo_id = getattr(getattr(proposal, "object_", None), "id_", None)
    if embargo_id is not None and not isinstance(embargo_id, str):
        raise VultronValidationError(
            "Proposal embargo event reference must have a string ID."
        )
    if not embargo_id:
        raise VultronValidationError(
            "Proposal is missing an embargo event reference."
        )
    return embargo_id


def send_case_actor_activity(
    *,
    dl: CaseOutboxPersistence,
    case_id: str,
    actor_id: str,
    trigger_activity: TriggerActivityPort | None,
    failure_label: str,
    activity_builder: Callable[[str], list[str]],
) -> None:
    """Send an activity to the case manager via the sender-side BT."""
    from py_trees.common import Status

    from vultron.core.behaviors.bridge import BTBridge
    from vultron.core.behaviors.sender.send_tree import sender_side_bt

    bridge = BTBridge(datalayer=dl, trigger_activity=trigger_activity)
    tree = sender_side_bt(case_id=case_id, activity_builder=activity_builder)
    result = bridge.execute_with_setup(tree, actor_id=actor_id)
    if result.status != Status.SUCCESS:
        from vultron.errors import VultronValidationError

        raise VultronValidationError(
            f"{failure_label} failed: {BTBridge.get_failure_reason(tree)}"
        )
