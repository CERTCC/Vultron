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
    request_event_type: str,
    reply_event_types: frozenset[str],
    named_actor: Callable[[dict[str, Any]], str | None],
) -> bool:
    """True when the latest *request_event_type* entry naming *actor_id* is unanswered.

    A request the CASE_MANAGER sends is committed under its own activity id
    (ADR-0119), not the id of the actor it concerns, so the entry is found by
    the actor its snapshot names (*named_actor*) and its reply state is then
    read under the entry's ``log_object_id``, as the ownership-transfer Offer
    is (``core/participants/ownership_offer.py``).
    """
    requests = [
        entry
        for entry in sorted_case_ledger_entries(dl, case_id)
        if entry.event_type == request_event_type
        and named_actor(entry.payload_snapshot) == actor_id
    ]
    if not requests:
        return False
    return dl.find_protocol_pair(
        case_id=case_id,
        request_event_type=request_event_type,
        object_id=requests[-1].log_object_id,
        reply_event_types=reply_event_types,
    ).is_pending()


__all__ = [
    "invitee",
    "offered_participant_actor",
    "request_naming_actor_is_pending",
]
