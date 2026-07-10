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
"""ProtocolPair — shared value type for protocol request/reply state detection.

:class:`ProtocolPair` is the canonical value type used by both:

- :func:`~vultron.core.ports.case_persistence.CasePersistence.find_protocol_pair`
  (durable, DataLayer-backed query)
- :class:`~vultron.core.models.pending_assertion.PendingAssertionStore`
  (ephemeral, in-memory suppression)

The two serve distinct purposes and MUST NOT be unified:
- ``find_protocol_pair`` determines open/closed state from the canonical
  case ledger (durable, survives restarts).
- ``PendingAssertionStore`` suppresses duplicate near-term re-emits while
  waiting for the CaseLedgerEntry round-trip (ephemeral, lost on restart).

Named constants for known request/reply pairs:

- :data:`OFFER_CASE_PARTICIPANT_REPLY_TYPES` — closes when Case Owner sends
  ``Accept`` or ``Reject`` of ``Offer(CaseParticipant)``.
- :data:`INVITE_ACTOR_TO_CASE_REPLY_TYPES` — closes when invited actor sends
  ``Accept`` or ``Reject`` of ``Invite(Case)``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Reply event types that close an ``Offer(CaseParticipant)`` protocol pair.
OFFER_CASE_PARTICIPANT_REPLY_TYPES: frozenset[str] = frozenset(
    {
        "accept_offer_case_participant",
        "reject_offer_case_participant",
    }
)

#: Reply event types that close an ``Invite(Actor, Case)`` protocol pair.
INVITE_ACTOR_TO_CASE_REPLY_TYPES: frozenset[str] = frozenset(
    {
        "accept_invite_actor_to_case",
        "reject_invite_actor_to_case",
    }
)


@dataclass(frozen=True)
class ProtocolPair:
    """Value type representing a protocol request/reply pair.

    A ``ProtocolPair`` tracks whether a protocol handshake (e.g.,
    ``Offer(CaseParticipant)`` → ``Accept/Reject``) is still open or has
    been closed by a matching reply.

    Attributes:
        case_id: URI of the parent :class:`~vultron.core.models.case.VulnerabilityCase`.
        request_event_type: Machine-readable event descriptor for the request
            (e.g. ``"offer_case_participant"``).
        object_id: Full URI of the specific thing being offered/invited.
        reply_event_types: ``frozenset`` of event type strings that constitute
            a valid reply (i.e., that close the pair).
        reply_object_id: Full URI of the reply activity; ``None`` if no reply
            has been found yet.
        reply_event_type: Which reply type was received; ``None`` if open.
    """

    case_id: str
    request_event_type: str
    object_id: str
    reply_event_types: frozenset[str] = field(default_factory=frozenset)
    reply_object_id: str | None = None
    reply_event_type: str | None = None

    def is_open(self) -> bool:
        """Return ``True`` if no matching reply has been recorded yet."""
        return self.reply_object_id is None

    def is_closed(self) -> bool:
        """Return ``True`` if a matching reply has been recorded."""
        return self.reply_object_id is not None


__all__ = [
    "ProtocolPair",
    "OFFER_CASE_PARTICIPANT_REPLY_TYPES",
    "INVITE_ACTOR_TO_CASE_REPLY_TYPES",
]
