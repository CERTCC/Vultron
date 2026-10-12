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
from typing import NamedTuple

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sender.send_tree import sender_side_bt
from vultron.core.behaviors.sender_entitlement import is_case_owner
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.predicates.addressing import (
    distinct_recipients,
    normalise_actor_id,
)
from vultron.core.services.embargo_ordering import (
    earliest_expiring_embargo_id,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.use_cases._helpers import (
    read_received_activity,
    resolve_case_participant_id_for_actor,
)
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
        if proposal_id and case.proposal_is_undecided(embargo_id)
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


class EmbargoAnswerTarget(NamedTuple):
    """The ``Invite(EmbargoEvent)`` an accept or reject trigger answers.

    Attributes:
        invite_id: The Invite the answer's ``Accept``/``Reject`` wraps.
        embargo_id: The ``EmbargoEvent`` that Invite proposes, whose consent
            row the answer moves.
    """

    invite_id: str
    embargo_id: str


_ANSWERABLE_IN_FORCE = frozenset(
    {EmbargoConsentState.INVITED, EmbargoConsentState.TIMED_OUT}
)
"""Row states from which the embargo in force can still be answered.

An ``INVITED`` row never answered the relayed Invite; a ``TIMED_OUT`` row let
its deadline pass, and a late Accept of the embargo in force is honoured
(EMB-17-002).  An ``AGREED`` row has nothing left to answer — leaving it is a
withdrawal, not an answer (EP-09-013) — and a ``DECLINED`` row is re-invited
before it can agree (CM-18-003).
"""


def _resolve_embargo_proposal(
    case: VulnerabilityCase,
    proposal_id: str | None,
    actor_id: str,
    dl: CasePersistence,
) -> EmbargoAnswerTarget:
    """Return the Invite an accept or reject trigger answers, and its embargo.

    With an explicit *proposal_id*, the open-proposal record
    (``case.pending_embargo_proposal_index``) is looked in first; an id it
    does not hold is then resolved as the actor's own received Invite for the
    embargo in force (EP-09-012), which activation took out of that record
    (EP-08-003).  With no *proposal_id*, the earliest-expiring open proposal
    is used (EP-08-002) and the embargo in force is never a fallback, because
    answering an embargo is an intentional act.  ADR-0035: no DL wire
    re-read.

    Raises:
        VultronNotFoundError: No open proposal and no answerable Invite for
            the embargo in force can be located.
    """
    if proposal_id:
        if proposal_id in case.pending_embargo_proposal_index.values():
            return EmbargoAnswerTarget(
                proposal_id,
                _resolve_embargo_id_from_proposal_id(case, proposal_id),
            )
        return _resolve_invite_to_embargo_in_force(
            case, proposal_id, actor_id, dl
        )

    resolved = find_embargo_proposal_id(case, dl)
    if resolved is None:
        raise VultronNotFoundError(
            "EmbargoProposal",
            f"(pending for case '{case.id_}')",
        )
    return EmbargoAnswerTarget(
        resolved, _resolve_embargo_id_from_proposal_id(case, resolved)
    )


def _resolve_invite_to_embargo_in_force(
    case: VulnerabilityCase,
    invite_id: str,
    actor_id: str,
    dl: CasePersistence,
) -> EmbargoAnswerTarget:
    """Resolve *invite_id* as the actor's Invite for the embargo in force.

    The Invite is read from *actor_id*'s own record of what it received
    (``read_received_activity``), never from the open-proposal record
    (EP-09-012).  It must be an ``Invite`` whose sole ``to`` recipient is
    *actor_id* (EP-09-010) and whose object is the case's active embargo,
    and the actor's consent row for that embargo must be ``INVITED`` or
    ``TIMED_OUT`` (CM-18-001).  The answer is built from the copy
    ``CreateAndStoreInviteNode`` keeps under the Invite's own id, which
    every received relay stores alongside the archive record, so that copy
    must be held too.

    Raises:
        VultronNotFoundError: The actor holds no such Invite (or no copy of
            it under its own id), the Invite names another embargo or
            another invitee, the actor is the case owner, the actor has no
            participant record or no row for the embargo, or the row is in
            any other state.
    """
    resource = "Invite(EmbargoEvent)"
    # The archived record holds a core activity; a copy stored under the
    # sender's id may rehydrate as its wire class, so both are read by field.
    invite = read_received_activity(dl, invite_id, resource)
    if getattr(invite, "type_", None) != "Invite":
        raise VultronNotFoundError(resource, invite_id)
    # The answer factory reads the Invite under its own id; an archive
    # record with no such copy cannot be answered.
    if dl.read(invite_id) is None:
        raise VultronNotFoundError(resource, f"{invite_id} (own-id copy)")
    embargo_id = _as_id(getattr(invite, "object_", None))
    if embargo_id is None or embargo_id != case.active_embargo_id:
        raise VultronNotFoundError(
            resource, f"{invite_id} for the embargo in force on {case.id_}"
        )
    # The invitee of an Invite(EmbargoEvent) is its sole ``to`` recipient
    # (EP-09-010); a ``cc`` copy is not an invitation to answer.
    recipients = distinct_recipients(
        _as_id(t) for t in getattr(invite, "to", None) or []
    )
    if recipients != [normalise_actor_id(actor_id)]:
        raise VultronNotFoundError(
            resource, f"{invite_id} addressed to {actor_id}"
        )
    # The case owner's answer is its decision for the case (ADR-0122), and
    # the embargo in force is already decided: there is nothing to activate
    # or reject.
    if is_case_owner(case, actor_id):
        raise VultronNotFoundError(
            resource,
            f"{invite_id} answerable by {actor_id} (the case owner decided"
            f" the embargo in force; EP-09-012)",
        )
    participant_id = resolve_case_participant_id_for_actor(case, actor_id, dl)
    participant = dl.read(participant_id) if participant_id else None
    if not isinstance(participant, CaseParticipant):
        raise VultronNotFoundError(
            "CaseParticipant", f"{actor_id} on case {case.id_}"
        )
    state = participant.consent_for(embargo_id)
    if state not in _ANSWERABLE_IN_FORCE:
        raise VultronNotFoundError(
            resource,
            f"{invite_id} answerable by {actor_id} (its row for embargo"
            f" {embargo_id} is {state.value}; EP-09-012)",
        )
    logger.debug(
        "Actor '%s' answers the embargo in force '%s' on case '%s' through"
        " Invite '%s' (row %s, EP-09-012)",
        actor_id,
        embargo_id,
        case.id_,
        invite_id,
        state.value,
    )
    return EmbargoAnswerTarget(invite_id, embargo_id)


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
