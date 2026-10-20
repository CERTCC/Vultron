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

"""Find the CASE_MANAGER's pending request about one actor (CM-16-008/009).

Split from ``conditions.py`` for the BTND-07-004 line limit.  The duplicate-
recommendation checks there ask whether an ``Invite`` to, or an
``Offer(CaseParticipant)`` for, the recommended actor is still unanswered.
"""

from collections.abc import Callable
from typing import Any

from vultron.core.behaviors.sync.nodes.embargo_pause import (
    sorted_case_ledger_entries,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.wire_keys import wire_key
from vultron.core.ports.case_persistence import CasePersistence

_ATTRIBUTED_TO = wire_key("attributed_to")
_IN_REPLY_TO = wire_key("in_reply_to")


def invitee(snapshot: dict[str, Any]) -> str | None:
    """The actor an ``Invite(Actor, Case)`` snapshot invites."""
    return _as_id(snapshot.get("object"))


def offered_participant_actor(snapshot: dict[str, Any]) -> str | None:
    """The actor an ``Offer(CaseParticipant)`` snapshot offers a record for."""
    participant = snapshot.get("object")
    if not isinstance(participant, dict):
        return None
    return _as_id(participant.get(_ATTRIBUTED_TO))


def request_naming_actor_is_pending(
    dl: CasePersistence,
    case_id: str,
    actor_id: str,
    request_semantic_type: str,
    reply_semantic_types: frozenset[str],
    named_actor: Callable[[dict[str, Any]], str | None],
) -> bool:
    """True when the latest *request_semantic_type* entry naming *actor_id* is unanswered.

    A request the CASE_MANAGER sends is committed under its own activity id
    (ADR-0119), not the id of the actor it concerns, so the entry is found by
    the actor its snapshot names (*named_actor*).  It is answered only by a
    later *reply_semantic_types* entry that answers it (:func:`answers`): with
    Invites to two actors open, the Accept of one leaves the other pending.
    """
    entries = sorted_case_ledger_entries(dl, case_id)
    requests = [
        entry
        for entry in entries
        if entry.semantic_type == request_semantic_type
        and named_actor(entry.payload_snapshot) == actor_id
    ]
    if not requests:
        return False
    request = requests[-1]
    return not any(
        entry.log_index > request.log_index
        and entry.semantic_type in reply_semantic_types
        and answers(entry.payload_snapshot, request.log_object_id)
        for entry in entries
    )


def answers(reply_snapshot: dict[str, Any], request_id: str) -> bool:
    """True when the reply snapshot's ``object`` or ``inReplyTo`` is *request_id*."""
    return request_id in (
        _as_id(reply_snapshot.get("object")),
        _as_id(reply_snapshot.get(_IN_REPLY_TO)),
    )


__all__ = [
    "answers",
    "invitee",
    "offered_participant_actor",
    "request_naming_actor_is_pending",
]
