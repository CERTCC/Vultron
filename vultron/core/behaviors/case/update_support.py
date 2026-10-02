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
from typing import TYPE_CHECKING, Any, cast

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.events.case import UpdateCaseReceivedEvent
from vultron.core.participants.recipients import (
    case_content_recipients,
    inert_participants,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

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


def find_excluded_actor_ids(
    case: VulnerabilityCase, dl: CasePersistence
) -> set[str]:
    """Return the inert participants a case-update broadcast leaves out.

    Delegates to the shared selection (CM-10-007): the roster less the active
    participants (CM-10-004).  Kept as its own step so the update tree can
    report whom it withheld the broadcast from; :func:`broadcast_case_update`
    applies the active check itself whatever this returns.
    """
    excluded = inert_participants(case, dl)
    if excluded:
        # One line per broadcast, not per participant: an inert participant
        # is routine under ADR-0114, but whom an update skipped is worth
        # one operator-visible line.
        logger.info(
            "update_case: %d participant(s) not active on case '%s' (not"
            " joined, or not SIGNATORY to the active embargo) — case update"
            " will not be broadcast to them (CM-10-004): %s",
            len(excluded),
            case.id_,
            ", ".join(sorted(excluded)),
        )
    return excluded


def broadcast_case_update(
    dl: CasePersistence,
    case_id: str,
    case: VulnerabilityCase,
    actor_id: str,
    trigger_activity: TriggerActivityPort,
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
        trigger_activity: The port that builds, persists, and seals the
            ``Announce(VulnerabilityCase)``.  Core used to construct the
            activity itself; routing it through the adapter is what lets the
            outbox deliver the sealed body rather than a re-read (VM-08-003).
        excluded_actor_ids: Further participants to omit.  The active check
            (CM-10-004) is applied regardless: recipients come from the shared
            selection (CM-10-007).

    This used to resolve the announcing identity itself, via a scan for a
    ``Service`` whose ``context`` matched *case_id*, and then enqueue against
    that id. Two problems: it was a second, weaker mechanism for an authority
    the ``CASE_MANAGER`` role already expresses (the role holder may be any
    Actor type, not necessarily a ``Service``), and it enqueued under an id
    that was not necessarily the store it had just written the activity to.
    A shared pool hid the mismatch; per-actor stores do not. The authority is
    now a role gate in the tree, so the executing actor *is* the announcer and
    both halves of the emit land in one store (ADR-0073, CLP-09 precedent).
    """
    participant_ids = case_content_recipients(
        case, dl, excluding=excluded_actor_ids or set()
    )
    if not participant_ids:
        logger.debug(
            "update_case: no eligible participants in case '%s' — skipping broadcast",
            case_id,
        )
        return

    broadcast_id = trigger_activity.announce_vulnerability_case(
        case_id=case_id,
        actor=actor_id,
        context_id=case_id,
        to=participant_ids,
    )
    cast(CaseOutboxPersistence, dl).outbox_append(broadcast_id)
    logger.info(
        "update_case: CaseActor '%s' broadcast Announce for case '%s' to %d participants (CM-06-001)",
        actor_id,
        case_id,
        len(participant_ids),
    )
