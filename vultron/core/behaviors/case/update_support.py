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

"""Shared helpers for update-case BT nodes."""

from __future__ import annotations

import logging
from typing import Any, cast

from vultron.core.models.events.case import UpdateCaseReceivedEvent
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.vultron_types import VultronActivity
from vultron.core.ports.case_persistence import (
    CaseOutboxPersistence,
    CasePersistence,
)
from vultron.core.models._helpers import _as_id

logger = logging.getLogger(__name__)


def apply_update_case_fields(
    stored_case: Any, request: UpdateCaseReceivedEvent
) -> bool:
    """Apply mutable case fields from *request* onto *stored_case*."""
    if request.object_type != "VulnerabilityCase" or request.case is None:
        return False

    for field in ("name", "summary", "content"):
        value = getattr(request.case, field, None)
        if value is not None:
            setattr(stored_case, field, value)
    return True


def find_excluded_actor_ids(case: Any, dl: CasePersistence) -> set[str]:
    """Return actor IDs excluded from case-update broadcast by active embargo."""
    excluded: set[str] = set()
    active_embargo = getattr(case, "active_embargo", None)
    if active_embargo is None:
        return excluded

    embargo_id = _as_id(active_embargo)
    for actor_id, participant_id in getattr(
        case, "actor_participant_index", {}
    ).items():
        participant = dl.read(participant_id)
        if participant is None:
            logger.warning(
                "update_case: could not read participant '%s' for embargo acceptance check",
                participant_id,
            )
            continue
        if not isinstance(participant, CaseParticipant):
            continue
        accepted_ids = getattr(participant, "accepted_embargo_ids", []) or []
        if embargo_id not in accepted_ids:
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


def broadcast_case_update(
    dl: CasePersistence,
    case_id: str,
    case: Any,
    actor_id: str,
    excluded_actor_ids: set[str] | None = None,
) -> None:
    """Create and queue an ``Announce`` for a case update (CM-06-001).

    Args:
        dl: The broadcasting actor's own DataLayer.
        case_id: The case whose update is being announced.
        case: The updated case object to announce.
        actor_id: The broadcasting actor. The caller MUST already have
            established that this actor holds ``CVDRole.CASE_MANAGER`` for the
            case — see ``create_update_case_received_tree``, which wraps the
            calling node in a ``CheckIsCaseManagerNode`` gate.
        excluded_actor_ids: Participants to omit (CM-10-004).

    This used to resolve the announcing identity itself, via a scan for a
    ``Service`` whose ``context`` matched *case_id*, and then enqueue against
    that id. Two problems: it was a second, weaker mechanism for an authority
    the ``CASE_MANAGER`` role already expresses (the role holder may be any
    Actor type, not necessarily a ``Service``), and it enqueued under an id
    that was not necessarily the store it had just written the activity to.
    A shared pool hid the mismatch; per-actor stores do not. The authority is
    now a role gate in the tree, so the executing actor *is* the announcer and
    both halves of the emit land in one store (ADR-0066, CLP-09 precedent).
    """
    excluded = excluded_actor_ids or set()

    participant_ids = [
        actor_id
        for actor_id in getattr(case, "actor_participant_index", {}).keys()
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
        actor=actor_id,
        object_=case,
        to=participant_ids,
    )
    try:
        dl.create(broadcast)
    except ValueError:
        logger.debug(
            "update_case: broadcast activity %s already exists — skipping",
            broadcast.id_,
        )
        return

    cast(CaseOutboxPersistence, dl).outbox_append(broadcast.id_)
    logger.info(
        "update_case: CaseActor '%s' broadcast Announce for case '%s' to %d participants (CM-06-001)",
        actor_id,
        case_id,
        len(participant_ids),
    )
