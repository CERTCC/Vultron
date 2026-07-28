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

from vultron.core.models.case import VulnerabilityCase
from vultron.core.ports.case_persistence import (
    CasePersistence,
    CaseOutboxPersistence,
)
from vultron.core.ports.trigger_activity import TriggerActivityPort
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
    """Resolve a VulnerabilityCase by ID; raise domain error if absent or wrong type."""
    case_raw = dl.read(case_id)
    if case_raw is None or not isinstance(case_raw, VulnerabilityCase):
        case_raw = dl.find_case_by_short_id(case_id)
    if case_raw is None:
        raise VultronNotFoundError("VulnerabilityCase", case_id)
    if not isinstance(case_raw, VulnerabilityCase):
        raise VultronValidationError(
            f"Expected VulnerabilityCase, got {type(case_raw).__name__}."
        )
    return case_raw


def find_embargo_proposal_id(case: VulnerabilityCase) -> str | None:
    """Return the first pending embargo proposal ID from core state.

    Looks up ``case.pending_embargo_proposal_index`` (embargo_id → proposal_id)
    and returns the first proposal ID found.  Returns None if no pending
    proposal is recorded.  ADR-0035: no DL wire re-read.
    """
    index = case.pending_embargo_proposal_index
    for proposal_id in index.values():
        if proposal_id:
            return proposal_id
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
    from vultron.core.models._helpers import _as_id

    if case is None:
        return False
    owner_id = _as_id(getattr(case, "attributed_to", None))
    return owner_id is not None and owner_id == actor_id


def _resolve_embargo_proposal(
    case: VulnerabilityCase,
    proposal_id: str | None,
) -> str:
    """Return the proposal ID for a pending embargo on *case*.

    When *proposal_id* is provided it is used directly (after verifying it
    appears in ``case.pending_embargo_proposal_index``).  When absent, the
    first entry in the index is used.  Raises ``VultronNotFoundError`` when
    no pending proposal can be located.  ADR-0035: no DL wire re-read.
    """
    from vultron.errors import VultronNotFoundError

    index = case.pending_embargo_proposal_index

    if proposal_id:
        if proposal_id not in index.values():
            raise VultronNotFoundError("EmbargoProposal", proposal_id)
        return proposal_id

    resolved = find_embargo_proposal_id(case)
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
    from vultron.errors import VultronValidationError

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
