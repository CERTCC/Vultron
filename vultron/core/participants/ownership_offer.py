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
"""The recorded ownership-transfer Offer a reply names (CM-21-011, CM-21-013).

A transfer has two ``Offer(VulnerabilityCase)`` activities of one shape
(ADR-0199): the Case Owner's own, its proposal, sent to the CASE_MANAGER, and
the one the CASE_MANAGER makes from it, under an id it derives from the
Owner's (:func:`ownership_offer_id`), with the owner in ``attributedTo`` and
the Owner's Offer in ``inReplyTo`` (CM-21-028).  The CASE_MANAGER ledgers
both as ``offer_case_ownership_transfer`` entries; its own, committed once it
is queued, is the one the transferee holds and answers, and the one that is
closed and expired.  Every reader here reads only the CASE_MANAGER's Offers,
told from the Owner's by the id derived from the Owner's Offer
(:func:`_offer_entries`), so an answer naming the Owner's Offer names nothing
that can be accepted.
"Recorded" means ledgered, and whether the Offer is still open is read from
the same ledger and the ``end_time`` the ledgered Offer carries (CM-21-014,
CM-21-017, CLP-11-001).

A reply names it directly: the transferee's ``Accept`` or ``Reject`` by its
id, and the owner's ``Undo`` of its own Offer through the id derived from
that Offer (CM-21-015, CM-21-037).  No back-link is followed.

:func:`recorded_ownership_offer` returns that Offer and its protocol pair;
the sender-entitlement guards read the transferee, the offerer and the open
state from it, and the use case reads the new owner from it (never from the
sender).  The recorded Offer also carries its deadline, the ``end_time`` the
ledgered Offer names (CM-21-016).
:func:`open_ownership_offer` returns the case's Offer that is still open, if
any, so the CASE_MANAGER can refuse a second one (CM-21-014);
:func:`offer_made_from_proposal` tells a redelivered proposal from a new one.

Spec: CM-21-005, CM-21-011, CM-21-013, CM-21-014, CM-21-015, CM-21-016,
CLP-11-001.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from vultron.core.models._helpers import parse_published
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.protocol_pair import (
    OFFER_CASE_OWNERSHIP_TRANSFER_REPLY_TYPES,
    OFFER_CASE_OWNERSHIP_TRANSFER_SEMANTIC_TYPE,
    ProtocolPair,
)
from vultron.core.models.wire_keys import wire_key
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.participants.offer_forward import entry_target
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.predicates.addressing import (
    normalise_actor_id,
    same_actor_id,
    snapshot_actor_id,
)
from vultron.core.sync_helpers import recorded_entries_for_case
from vultron.errors import VultronNotFoundError


@dataclass(frozen=True)
class RecordedOwnershipOffer:
    """An ownership-transfer Offer the CASE_MANAGER ledgered for a case.

    Attributes:
        case_id: The case whose ownership the Offer transfers.
        offer_id: The id of the ledgered Offer (the entry's ``log_object_id``),
            the one the CASE_MANAGER derived from the owner's proposal.
        transferee_id: The actor the Offer names as the new owner, read from
            the ledger entry's ``target``.
        offer_actor_id: The ledgered Offer's ``actor``, the CASE_MANAGER
            that made it.
        offer_attributed_to: The ledgered Offer's ``attributedTo``, the Case
            Owner whose Offer it was made from (CM-24-002), read as
            :attr:`offerer_id`.
        pair: The Offer's request/reply state, read from the ledger.
        end_time: The ledgered Offer's activity-level ``end_time``, in UTC:
            the deadline to answer it (CM-21-016).  ``None`` when the Offer
            carries none, so it stays open until answered or withdrawn.
    """

    case_id: str
    offer_id: str
    transferee_id: str
    offer_actor_id: str | None
    offer_attributed_to: str | None
    pair: ProtocolPair
    end_time: datetime | None = None

    @property
    def offerer_id(self) -> str | None:
        """The Case Owner the Offer speaks for: its ``attributedTo``.

        Every recorded Offer is one the CASE_MANAGER made from an Owner's
        Offer, with itself as ``actor`` and that Owner as ``attributedTo``
        (CM-24-001, CM-24-002, :func:`_offer_entries`), so it speaks for that
        Owner.
        """
        return self.offer_attributed_to

    @property
    def answer_id(self) -> str | None:
        """The ledgered entry that closed the Offer, or ``None`` while open.

        Any semantic type in ``OFFER_CASE_OWNERSHIP_TRANSFER_REPLY_TYPES``
        closes it: the transferee's answer or the offerer's withdrawal.  An
        Offer past its ``end_time`` is closed too, with no entry: see
        :meth:`is_open_at`.
        """
        return self.pair.reply_object_id

    @property
    def closed_by_semantic_type(self) -> str | None:
        """The ``semantic_type`` of the entry that closed the Offer, if any."""
        return self.pair.reply_semantic_type

    def is_past_deadline(self, now: datetime) -> bool:
        """Return ``True`` when *now* is at or after the Offer's ``end_time``.

        The comparison an embargo Invite's expiry makes (``now >= end_time``),
        so the deadline instant itself is too late (CM-21-016).  An Offer
        with no ``end_time`` never passes it.  Whether the Offer is still
        open is a separate question: see :meth:`is_open_at`.
        """
        return self.end_time is not None and now >= self.end_time

    def is_open_at(self, now: datetime) -> bool:
        """Return ``True`` when the Offer is still open at *now* (CM-21-014).

        Open until the ledger records an answer or a withdrawal for it, or
        *now* reaches its ``end_time``.  Nothing records the expiry: it is
        read from the ledgered Offer's own ``end_time`` (CM-21-017,
        ADR-0152).
        """
        return self.answer_id is None and not self.is_past_deadline(now)

    def is_answered_other_than(self, answer_id: str) -> bool:
        """Return ``True`` when another answer has already closed the Offer.

        A redelivered answer finds its own ledger entry as the reply; it is
        the same answer, so it does not count as a second one (HP-01-014).
        """
        return self.answer_id is not None and self.answer_id != answer_id


def _case_manager_of(dl: CasePersistence, case_id: str) -> str | None:
    """The CASE_MANAGER of *case_id* as *dl* holds it, or ``None``.

    ``None`` when the store does not hold the case or the case names no
    CASE_MANAGER.
    """
    case = dl.read_case(case_id)
    return resolve_case_manager_id(case, dl) if case is not None else None


def _offer_entries(dl: CasePersistence, case_id: str) -> list[CaseLedgerEntry]:
    """The case's CASE_MANAGER-made ownership-transfer Offers, oldest first.

    The ``offer_case_ownership_transfer`` entries the CASE_MANAGER made from
    an Owner's Offer: its ``actor`` is the case's CASE_MANAGER and its id is
    the one :func:`ownership_offer_id` derives from its ``inReplyTo`` (the
    Owner's Offer) and ``attributedTo`` (the Owner), as CM-21-028 builds it.
    The Case Owner's own Offer is ledgered under the same semantic type
    (ADR-0199), but it is the proposal, never the Offer that is answered,
    closed or expired (CM-21-029), so it is left out.  The derived id, not
    the ``actor`` alone, tells them apart: an Owner that is also the
    CASE_MANAGER (CM-02-010) sends its own Offer as the CASE_MANAGER.  A case
    this store does not hold, or one that names no CASE_MANAGER, has none.
    """
    manager_id = _case_manager_of(dl, case_id)
    if manager_id is None:
        return []
    return [
        entry
        for entry in recorded_entries_for_case(case_id=case_id, dl=dl)
        if entry.semantic_type == OFFER_CASE_OWNERSHIP_TRANSFER_SEMANTIC_TYPE
        and _made_by(entry, manager_id, case_id)
    ]


def _made_by(entry: CaseLedgerEntry, manager_id: str, case_id: str) -> bool:
    """Return ``True`` when *entry* is an Offer *manager_id* made (CM-21-028).

    Its ``actor`` is *manager_id*, and its id is the one *manager_id* derives
    from the Owner's Offer it names in ``inReplyTo`` and the Owner it names
    in ``attributedTo``.
    """
    actor_id = _entry_actor(entry)
    owner_id = _entry_attributed_to(entry)
    owners_offer_id = _entry_in_reply_to(entry)
    if actor_id is None or owner_id is None or owners_offer_id is None:
        return False
    return same_actor_id(actor_id, manager_id) and (
        entry.log_object_id
        == ownership_offer_id(manager_id, case_id, owners_offer_id, owner_id)
    )


def _entry_actor(entry: CaseLedgerEntry) -> str | None:
    """The ledgered Offer's sender (its ``actor``)."""
    return snapshot_actor_id(entry.payload_snapshot.get("actor"))


def _entry_attributed_to(entry: CaseLedgerEntry) -> str | None:
    """The participant the ledgered Offer claims to speak for, if any."""
    return snapshot_actor_id(
        entry.payload_snapshot.get(wire_key("attributed_to"))
    )


def _entry_in_reply_to(entry: CaseLedgerEntry) -> str | None:
    """The id of the activity the ledgered Offer answers, if any."""
    raw = entry.payload_snapshot.get(wire_key("in_reply_to"))
    if isinstance(raw, Mapping):
        raw = raw.get("id")
    return raw if isinstance(raw, str) and raw else None


def _entry_end_time(entry: CaseLedgerEntry) -> datetime | None:
    """The ledgered Offer's ``end_time``, normalised to UTC (CM-21-042).

    The snapshot carries the time as the sender wrote it; reading it here
    converts any offset to UTC, so every comparison and every message speaks
    one zone (CS-13-001).  A value that is not a timestamp reads as absent:
    the wire edge refused a malformed ``endTime`` before the Offer was
    ledgered, so only a hand-made entry could hold one.
    """
    return parse_published(entry.payload_snapshot.get(wire_key("end_time")))


#: Kind label of the id the CASE_MANAGER derives for the Offer it makes from
#: a proposal (see ``derived_activity_id``).
OWNERSHIP_OFFER_ID_KIND = "offer-case-ownership-transfer"


def ownership_offer_id(
    manager_id: str, case_id: str, proposal_id: str, proposer_id: str
) -> str:
    """The id of the Offer *manager_id* makes from *proposer_id*'s own Offer.

    Derived, never taken from the Owner's Offer: the CASE_MANAGER keys
    nothing it emits or stores by an id another party chose (ADR-0148,
    DL-06-006).  A redelivery of the proposal rebuilds
    the same Offer, which the outbox queues once (OX-06-002), and the
    owner's withdrawal of its Offer names that Offer through the same
    derivation (CM-21-015, CM-21-037).  The proposer is part of the derivation, so a
    proposal id another sender reuses names a different Offer; both actor
    ids are normalised first, so every caller derives one id whatever
    spelling it read them in (OID-01-006).
    """
    return derived_activity_id(
        OWNERSHIP_OFFER_ID_KIND,
        normalise_actor_id(manager_id),
        case_id,
        proposal_id,
        normalise_actor_id(proposer_id),
    )


def recorded_ownership_offer(
    dl: CasePersistence,
    case_id: str,
    offer_id: str,
) -> RecordedOwnershipOffer:
    """Return the recorded ownership-transfer Offer *offer_id* names.

    Args:
        dl: The CASE_MANAGER's store.
        case_id: The case the reply names.
        offer_id: The Offer the reply names, the CASE_MANAGER's own.

    Raises:
        VultronNotFoundError: no ownership-transfer Offer for *case_id* was
            ledgered under *offer_id*, or the recorded Offer names no
            transferee.
    """
    entry = next(
        (
            e
            for e in _offer_entries(dl, case_id)
            if e.log_object_id == offer_id
        ),
        None,
    )
    if entry is None:
        raise VultronNotFoundError(
            f"Ownership-transfer Offer recorded for case '{case_id}'",
            offer_id,
        )
    return _recorded(dl, case_id, entry)


def _recorded(
    dl: CasePersistence, case_id: str, entry: CaseLedgerEntry
) -> RecordedOwnershipOffer:
    """The recorded Offer *entry* holds, with its pair read from the ledger.

    Raises:
        VultronNotFoundError: the recorded Offer names no transferee.
    """
    transferee_id = entry_target(entry)
    if transferee_id is None:
        raise VultronNotFoundError(
            f"Transferee of recorded ownership-transfer Offer for case"
            f" '{case_id}'",
            entry.log_object_id,
        )
    pair = dl.find_protocol_pair(
        case_id=case_id,
        request_semantic_type=OFFER_CASE_OWNERSHIP_TRANSFER_SEMANTIC_TYPE,
        object_id=entry.log_object_id,
        reply_semantic_types=OFFER_CASE_OWNERSHIP_TRANSFER_REPLY_TYPES,
    )
    return RecordedOwnershipOffer(
        case_id=case_id,
        offer_id=entry.log_object_id,
        transferee_id=transferee_id,
        offer_actor_id=_entry_actor(entry),
        offer_attributed_to=_entry_attributed_to(entry),
        pair=pair,
        end_time=_entry_end_time(entry),
    )


def offer_made_from_proposal(
    dl: CasePersistence, case_id: str, proposal_id: str, proposer_id: str
) -> RecordedOwnershipOffer | None:
    """The recorded Offer the case's CASE_MANAGER made from *proposer_id*'s
    proposal *proposal_id*.

    ``None`` when the ledger records no such Offer, or the case is not held
    or names no CASE_MANAGER: the proposal is then a new one.  A proposal
    whose Offer the ledger records is a redelivery (HP-01-014); its standing
    is that Offer's offerer (CM-21-019).
    """
    manager_id = _case_manager_of(dl, case_id)
    if manager_id is None:
        return None
    try:
        return recorded_ownership_offer(
            dl,
            case_id,
            ownership_offer_id(manager_id, case_id, proposal_id, proposer_id),
        )
    except VultronNotFoundError:
        return None


def open_ownership_offer(
    dl: CasePersistence, case_id: str, now: datetime
) -> RecordedOwnershipOffer | None:
    """Return a recorded ownership-transfer Offer for *case_id* still open.

    An Offer is open until the ledger holds an answer or a withdrawal
    recorded after it, read through ``find_protocol_pair()`` with
    ``OFFER_CASE_OWNERSHIP_TRANSFER_REPLY_TYPES``, or until *now* reaches the
    ``end_time`` the ledgered Offer carries (CM-21-014, CM-21-015,
    CM-21-017, CLP-11-001).  The latest open Offer is returned; ``None``
    when every recorded Offer is closed.

    An Offer that names no transferee could never be answered, so it does not
    hold the case open.

    Args:
        dl: The CASE_MANAGER's store.
        case_id: The case a new proposal names.  The caller has already
            ruled out a redelivery (:func:`offer_made_from_proposal`), so
            every recorded Offer is an earlier one.
        now: The CASE_MANAGER's clock, compared with each Offer's
            ``end_time``.
    """
    for entry in reversed(_offer_entries(dl, case_id)):
        if entry_target(entry) is None:
            continue
        offer = _recorded(dl, case_id, entry)
        if offer.is_open_at(now):
            return offer
    return None


__all__ = [
    "OWNERSHIP_OFFER_ID_KIND",
    "RecordedOwnershipOffer",
    "offer_made_from_proposal",
    "open_ownership_offer",
    "ownership_offer_id",
    "recorded_ownership_offer",
]
