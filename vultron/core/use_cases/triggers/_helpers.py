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

from vultron.core.models.protocols import (
    CaseModel,
    is_case_model,
)
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
