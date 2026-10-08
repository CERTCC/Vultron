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
- :data:`INVITE_ACTOR_TO_FULL_CASE_REPLY_TYPES` — closes when the joined
  participant sends ``Accept``, ``TentativeReject`` or ``Reject`` of the
  full-case ``Invite(Actor)[target=Case]``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from vultron.primitives import require_non_empty

#: Reply event types that close an ``Offer(CaseParticipant)`` protocol pair.
OFFER_CASE_PARTICIPANT_REPLY_TYPES: frozenset[str] = frozenset(
    {
        "accept_offer_case_participant",
        "reject_offer_case_participant",
    }
)

#: Reply event types that close an ``Invite(Actor, CaseStub)`` protocol pair.
INVITE_ACTOR_TO_CASE_REPLY_TYPES: frozenset[str] = frozenset(
    {
        "accept_invite_actor_to_case",
        "reject_invite_actor_to_case",
    }
)

#: Reply event types that close a full-case ``Invite(Actor)[target=Case]``
#: protocol pair — the ask the CASE_MANAGER puts to a joined participant
#: (CM-11-010, CM-11-011, ADR-0121).
INVITE_ACTOR_TO_FULL_CASE_REPLY_TYPES: frozenset[str] = frozenset(
    {
        "accept_invite_actor_to_full_case",
        "tentative_reject_invite_actor_to_full_case",
        "reject_invite_actor_to_full_case",
    }
)


class AskExpiry(StrEnum):
    """What a reply that arrives after an ask's deadline does (ASK-03-002).

    The consequence belongs to the ask kind.  It is never configurable and
    never carried on the ask activity (ASK-03-003).
    """

    STALE = "stale"
    """A late reply still authorizes the action; the asker only stops waiting."""

    VOID = "void"
    """A late reply authorizes nothing; the asker must ask again."""


#: Expiry consequence of an ``Invite(Actor, CaseStub)`` (ASK-03-002): stale.
#: Expiry only means the CASE_MANAGER stops waiting; a late ``Accept`` still
#: joins and a late ``Reject`` still closes the record.  The hazard of stale
#: embargo terms is already covered by the supersede rule (CM-11-016).  The
#: stub's deadline is ``Invite.end_time`` (ASK-03-004); the closing replies are
#: :data:`INVITE_ACTOR_TO_CASE_REPLY_TYPES`.  Declared here until the ask-kind
#: registry (#2884) takes both over.
INVITE_ACTOR_TO_CASE_EXPIRY: AskExpiry = AskExpiry.STALE

#: Expiry consequence of an ``Invite(EmbargoEvent)`` (ASK-03-007): a late reply
#: is still honoured under EMB-17 once the expiry has been recorded.
INVITE_TO_EMBARGO_EXPIRY: AskExpiry = AskExpiry.STALE


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
        request_found: ``True`` when the ledger contains a matching request
            entry for ``(case_id, request_event_type, object_id)``.  ``False``
            when no prior request exists (fresh case).  Use :meth:`is_pending`
            rather than :meth:`is_open` when detecting duplicates.
    """

    case_id: str
    request_event_type: str
    object_id: str
    reply_event_types: frozenset[str] = field(default_factory=frozenset)
    reply_object_id: str | None = None
    reply_event_type: str | None = None
    request_found: bool = False

    def __post_init__(self) -> None:
        # CS-08-001 for a stdlib dataclass: the ids are references and a blank
        # one names nothing.  ``reply_object_id`` is optional, so only a present
        # value is checked.
        require_non_empty(self.case_id, "case_id")
        require_non_empty(self.object_id, "object_id")
        if self.reply_object_id is not None:
            require_non_empty(self.reply_object_id, "reply_object_id")

    def is_open(self) -> bool:
        """Return ``True`` if no matching reply has been recorded yet."""
        return self.reply_object_id is None

    def is_closed(self) -> bool:
        """Return ``True`` if a matching reply has been recorded."""
        return self.reply_object_id is not None

    def is_pending(self) -> bool:
        """Return ``True`` if the request was found but no reply recorded yet.

        Distinguishes "pending" (request found, awaiting reply) from "fresh"
        (no prior request in the ledger at all).  Use this instead of
        ``is_open()`` when testing for a duplicate-recommendation scenario.
        """
        return self.request_found and self.reply_object_id is None


__all__ = [
    "AskExpiry",
    "INVITE_ACTOR_TO_CASE_EXPIRY",
    "INVITE_TO_EMBARGO_EXPIRY",
    "ProtocolPair",
    "OFFER_CASE_PARTICIPANT_REPLY_TYPES",
    "INVITE_ACTOR_TO_CASE_REPLY_TYPES",
    "INVITE_ACTOR_TO_FULL_CASE_REPLY_TYPES",
]
