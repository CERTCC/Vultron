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
- :data:`CASE_PARTICIPANT_ROLE_OFFER_REPLY_TYPES` — closes when the target's
  ``Accept`` or ``Reject`` of a role ``Offer(CaseParticipantRole)`` is
  ledgered (CM-33-005).
- :data:`OFFER_CASE_OWNERSHIP_TRANSFER_REPLY_TYPES` — closes when the
  transferee's ``Accept`` or ``Reject`` of an ownership-transfer
  ``Offer(VulnerabilityCase)``, or the offerer's ``Undo`` of it, is ledgered
  (CM-21-011, CM-21-014, CM-21-015).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from vultron.primitives import require_non_empty

#: Reply semantic types that close an ``Offer(CaseParticipant)`` protocol pair.
OFFER_CASE_PARTICIPANT_REPLY_TYPES: frozenset[str] = frozenset(
    {
        "accept_offer_case_participant",
        "reject_offer_case_participant",
    }
)

#: Reply semantic types that close an ``Invite(Actor, CaseStub)`` protocol pair.
INVITE_ACTOR_TO_CASE_REPLY_TYPES: frozenset[str] = frozenset(
    {
        "accept_invite_actor_to_case",
        "reject_invite_actor_to_case",
    }
)

#: Reply semantic types that close a full-case ``Invite(Actor)[target=Case]``
#: protocol pair — the ask the CASE_MANAGER puts to a joined participant
#: (CM-11-010, CM-11-011, ADR-0121).
INVITE_ACTOR_TO_FULL_CASE_REPLY_TYPES: frozenset[str] = frozenset(
    {
        "accept_invite_actor_to_full_case",
        "tentative_reject_invite_actor_to_full_case",
        "reject_invite_actor_to_full_case",
    }
)


#: Ledger ``semantic_type`` of a recorded ownership-transfer
#: ``Offer(VulnerabilityCase)`` — the request side of the pair below.
OFFER_CASE_OWNERSHIP_TRANSFER_SEMANTIC_TYPE: str = (
    "offer_case_ownership_transfer"
)

#: Ledger ``semantic_type`` of the owner's withdrawal of its ownership-transfer
#: proposal, ``Undo(Offer(Offer(VulnerabilityCase)))``, which closes the Offer
#: the CASE_MANAGER made from it (CM-21-015, ADR-0148).
UNDO_CASE_OWNERSHIP_TRANSFER_SEMANTIC_TYPE: str = (
    "undo_case_ownership_transfer"
)

#: Semantic types that close an ownership-transfer ``Offer(VulnerabilityCase)``
#: protocol pair once the CASE_MANAGER ledgers them (CM-21-014): the
#: transferee's answer (CM-21-007, CM-21-012) and the offerer's withdrawal
#: (CM-21-015).  Every reader of "is this Offer open?" goes through this set,
#: so a new closing entry needs no other change to close the Offer.  An Offer
#: past its ``end_time`` is closed with no entry (CM-21-017, ADR-0152).
OFFER_CASE_OWNERSHIP_TRANSFER_REPLY_TYPES: frozenset[str] = frozenset(
    {
        "accept_case_ownership_transfer",
        "reject_case_ownership_transfer",
        UNDO_CASE_OWNERSHIP_TRANSFER_SEMANTIC_TYPE,
    }
)


#: Ledger ``semantic_type`` of the target's ``Accept`` of a role
#: ``Offer(CaseParticipantRole)``: the grant (CM-02-016, CM-33-006).
ACCEPT_CASE_PARTICIPANT_ROLE_SEMANTIC_TYPE: str = (
    "accept_case_participant_role"
)

#: Ledger ``semantic_type`` of the target's ``Reject`` of a role
#: ``Offer(CaseParticipantRole)`` (CM-33-006).
REJECT_CASE_PARTICIPANT_ROLE_SEMANTIC_TYPE: str = (
    "reject_case_participant_role"
)

#: Semantic types that close a role ``Offer(CaseParticipantRole)`` once the
#: CASE_MANAGER ledgers them: the target's ``Accept`` or ``Reject``
#: (CM-33-005, CM-33-006).  A case may hold several role Offers open at once,
#: so a reply closes only the Offer it answers
#: (``vultron.core.participants.role_offer``).
CASE_PARTICIPANT_ROLE_OFFER_REPLY_TYPES: frozenset[str] = frozenset(
    {
        ACCEPT_CASE_PARTICIPANT_ROLE_SEMANTIC_TYPE,
        REJECT_CASE_PARTICIPANT_ROLE_SEMANTIC_TYPE,
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

#: Expiry consequence of an ownership-transfer ``Offer(VulnerabilityCase)``
#: (ASK-03-002): void.  The deadline is binding, so an Accept or Reject the
#: CASE_MANAGER processes after ``Offer.end_time`` moves no role and is not
#: ledgered (CM-21-016, ASK-03-006).
OFFER_CASE_OWNERSHIP_TRANSFER_EXPIRY: AskExpiry = AskExpiry.VOID


@dataclass(frozen=True)
class ProtocolPair:
    """Value type representing a protocol request/reply pair.

    A ``ProtocolPair`` tracks whether a protocol handshake (e.g.,
    ``Offer(CaseParticipant)`` → ``Accept/Reject``) is still open or has
    been closed by a matching reply.

    Attributes:
        case_id: URI of the parent :class:`~vultron.core.models.case.VulnerabilityCase`.
        request_semantic_type: Semantic type of the request
            (e.g. ``"offer_case_participant"``).
        object_id: Full URI of the specific thing being offered/invited.
        reply_semantic_types: ``frozenset`` of semantic type strings that constitute
            a valid reply (i.e., that close the pair).
        reply_object_id: Full URI of the reply activity; ``None`` if no reply
            has been found yet.
        reply_semantic_type: Which reply type was received; ``None`` if open.
        request_found: ``True`` when the ledger contains a matching request
            entry for ``(case_id, request_semantic_type, object_id)``.  ``False``
            when no prior request exists (fresh case).  Use :meth:`is_pending`
            rather than :meth:`is_open` when detecting duplicates.
    """

    case_id: str
    request_semantic_type: str
    object_id: str
    reply_semantic_types: frozenset[str] = field(default_factory=frozenset)
    reply_object_id: str | None = None
    reply_semantic_type: str | None = None
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
    "ACCEPT_CASE_PARTICIPANT_ROLE_SEMANTIC_TYPE",
    "AskExpiry",
    "CASE_PARTICIPANT_ROLE_OFFER_REPLY_TYPES",
    "INVITE_ACTOR_TO_CASE_EXPIRY",
    "INVITE_TO_EMBARGO_EXPIRY",
    "ProtocolPair",
    "OFFER_CASE_PARTICIPANT_REPLY_TYPES",
    "INVITE_ACTOR_TO_CASE_REPLY_TYPES",
    "INVITE_ACTOR_TO_FULL_CASE_REPLY_TYPES",
    "OFFER_CASE_OWNERSHIP_TRANSFER_SEMANTIC_TYPE",
    "OFFER_CASE_OWNERSHIP_TRANSFER_EXPIRY",
    "OFFER_CASE_OWNERSHIP_TRANSFER_REPLY_TYPES",
    "REJECT_CASE_PARTICIPANT_ROLE_SEMANTIC_TYPE",
    "UNDO_CASE_OWNERSHIP_TRANSFER_SEMANTIC_TYPE",
]
