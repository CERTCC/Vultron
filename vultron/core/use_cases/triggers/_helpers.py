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
from collections.abc import Callable

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sender.send_tree import sender_side_bt
from vultron.core.models.case import VulnerabilityCase
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.services.embargo_ordering import (
    earliest_expiring_embargo_id,
)
from vultron.core.use_cases._helpers import _find_case_actor_id
from vultron.errors import VultronNotFoundError, VultronValidationError

logger = logging.getLogger(__name__)


def resolve_actor(actor_id: str, dl: CasePersistence):
    """Resolve actor by full ID or short ID; raise VultronNotFoundError if absent."""
    actor = dl.read(actor_id)
    if actor is None:
        actor = dl.find_actor_by_short_id(actor_id)
    if actor is None:
        raise VultronNotFoundError("Actor", actor_id)
    return actor


def resolve_case(case_id: str, dl: CasePersistence) -> VulnerabilityCase:
    """Resolve a VulnerabilityCase by ID; raise domain error if absent."""
    case_raw = dl.read_case(case_id)
    if case_raw is None:
        case_raw = dl.find_case_by_short_id(case_id)
    if case_raw is None:
        raise VultronNotFoundError("VulnerabilityCase", case_id)
    return case_raw


def find_embargo_proposal_id(
    case: VulnerabilityCase, dl: CasePersistence
) -> str | None:
    """Return the earliest-expiring open embargo proposal ID from core state.

    Looks up ``case.pending_embargo_proposal_index`` (embargo_id → proposal_id)
    and selects the entry whose ``EmbargoEvent.end_time`` is earliest
    (EP-08-001, EP-08-002, ADR-0100) — never the first recorded, because a
    counter-proposal is recorded *after* the terms it supersedes.  Returns
    None when no pending proposal is recorded.  ADR-0035: no DL wire re-read;
    the embargo records read here are core objects.

    Raises:
        VultronNotFoundError: If an indexed embargo does not resolve in *dl*.
        VultronValidationError: If one resolves to something that cannot be
            ordered (EP-08-002 fails closed rather than picking arbitrarily).
    """
    index = {
        embargo_id: proposal_id
        for embargo_id, proposal_id in case.pending_embargo_proposal_index.items()
        if proposal_id
    }
    if not index:
        return None
    return index[earliest_expiring_embargo_id(dl, index)]


def _coerce_embargo_event(raw_embargo: object, embargo_id: str) -> object:
    """Normalize a persisted embargo record; raise domain errors on failure."""
    if getattr(raw_embargo, "type_", "") == "EmbargoEvent":
        return raw_embargo
    if raw_embargo is None:
        raise VultronNotFoundError("EmbargoEvent", embargo_id)
    raise VultronValidationError(
        f"Could not resolve EmbargoEvent '{embargo_id}'."
    )


def _resolve_embargo_proposal(
    case: VulnerabilityCase,
    proposal_id: str | None,
    dl: CasePersistence,
) -> str:
    """Return the proposal ID for a pending embargo on *case*.

    When *proposal_id* is provided it is used directly (after verifying it
    appears in ``case.pending_embargo_proposal_index``).  When absent, the
    earliest-expiring open proposal is used (EP-08-002).  Raises
    ``VultronNotFoundError`` when no pending proposal can be located.
    ADR-0035: no DL wire re-read.
    """
    index = case.pending_embargo_proposal_index

    if proposal_id:
        if proposal_id not in index.values():
            raise VultronNotFoundError("EmbargoProposal", proposal_id)
        return proposal_id

    resolved = find_embargo_proposal_id(case, dl)
    if resolved is None:
        raise VultronNotFoundError(
            "EmbargoProposal",
            f"(pending for case '{case.id_}')",
        )
    return resolved


def _resolve_embargo_id_from_proposal_id(
    case: VulnerabilityCase,
    proposal_id: str,
) -> str:
    """Return the embargo ID for *proposal_id* from ``case.pending_embargo_proposal_index``.

    The index maps embargo_id → proposal_id; this function inverts the lookup.
    Raises ``VultronValidationError`` when the proposal_id is not found.
    """
    for embargo_id, pid in case.pending_embargo_proposal_index.items():
        if pid == proposal_id:
            return embargo_id
    raise VultronValidationError(
        f"No embargo found for proposal '{proposal_id}' in case '{case.id_}'."
    )


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
    bridge = BTBridge(datalayer=dl, trigger_activity=trigger_activity)
    tree = sender_side_bt(case_id=case_id, activity_builder=activity_builder)
    result = bridge.execute_with_setup(tree, actor_id=actor_id)
    if result.status != Status.SUCCESS:
        raise VultronValidationError(
            f"{failure_label} failed: {BTBridge.get_failure_reason(tree)}"
        )


def _prepare_delegated_context(
    dl: CasePersistence,
    case_id: str,
    requesting_actor_id: str,
) -> tuple[str, str | None]:
    """Return (actor_id, attributed_to) for a CaseActor-delegated trigger.

    Implements the delegated-message contract (CM-24-001 through CM-24-003):
    when a CaseActor is present, the activity MUST be sent under the
    CaseActor's identity (actor_id) with the requesting actor recorded in
    attributed_to.  When no CaseActor exists the requesting actor sends
    directly and attributed_to is None.
    """
    case_actor_id = _find_case_actor_id(dl, case_id)
    actor_id = case_actor_id if case_actor_id else requesting_actor_id
    attributed_to = requesting_actor_id if case_actor_id else None
    return actor_id, attributed_to
