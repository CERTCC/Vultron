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

A transfer has one ``Offer(VulnerabilityCase)``: the one the CASE_MANAGER
makes from the Case Owner's proposal, ``Offer(Offer(VulnerabilityCase))``,
under an id it derives from that proposal (:func:`ownership_offer_id`), with
the owner in ``attributedTo`` (ADR-0148, CM-21-005).  The CASE_MANAGER
commits an ``offer_case_ownership_transfer`` entry for it once it is queued,
and that Offer is the one the transferee holds, answers, and the one that is
closed and expired.  "Recorded" means ledgered, and whether the Offer is
still open is read from the same ledger (CM-21-014, CLP-11-001).

A reply names it directly: the transferee's ``Accept`` or ``Reject`` by its
id, and the owner's ``Undo`` of its proposal through the id derived from the
proposal (CM-21-015).  No back-link is followed.

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

from dataclasses import dataclass
from datetime import datetime

from vultron.core.models._helpers import parse_published
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.protocol_pair import (
    OFFER_CASE_OWNERSHIP_TRANSFER_EXPIRED_SEMANTIC_TYPE,
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
            Owner whose proposal it carries out (CM-24-002).  Read through
            :meth:`offerer_id`, never on its own: it is honoured only on an
            Offer the CASE_MANAGER sent.
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

    def offerer_id(self, manager_id: str) -> str | None:
        """The participant that made the Offer, as *manager_id* recorded it.

        The CASE_MANAGER's Offer carries itself as ``actor`` and the Case
        Owner whose proposal it made as ``attributedTo`` (CM-24-001,
        CM-24-002), so it speaks for that owner.  Any other Offer speaks for
        its ``actor``: an ``attributedTo`` on an Offer the CASE_MANAGER did
        not send is a claim nothing checks (CLP-07-003 validates only
        ``actor``), so it is ignored.  ``None`` when the entry names no
        offerer.

        Args:
            manager_id: The case's CASE_MANAGER.
        """
        actor_id = self.offer_actor_id
        if actor_id is not None and same_actor_id(actor_id, manager_id):
            return self.offer_attributed_to
        return actor_id

    @property
    def answer_id(self) -> str | None:
        """The ledgered entry that closed the Offer, or ``None`` while open.

        Any semantic type in ``OFFER_CASE_OWNERSHIP_TRANSFER_REPLY_TYPES``
        closes it: the transferee's answer, the offerer's withdrawal or the
        CASE_MANAGER's expiry record.
        """
        return self.pair.reply_object_id

    @property
    def closed_by_semantic_type(self) -> str | None:
        """The ``semantic_type`` of the entry that closed the Offer, if any."""
        return self.pair.reply_semantic_type

    @property
    def closed_by_expiry(self) -> bool:
        """``True`` when the CASE_MANAGER's expiry record closed the Offer."""
        return (
            self.closed_by_semantic_type
            == OFFER_CASE_OWNERSHIP_TRANSFER_EXPIRED_SEMANTIC_TYPE
        )

    def is_past_deadline(self, now: datetime) -> bool:
        """Return ``True`` when *now* is at or after the Offer's ``end_time``.

        The comparison an embargo Invite's expiry makes (``now >= end_time``),
        so the deadline instant itself is too late (CM-21-016).  An Offer
        with no ``end_time`` never passes it.  Whether the Offer is still
        open is a separate question: see :attr:`answer_id`.
        """
        return self.end_time is not None and now >= self.end_time

    def is_answered_other_than(self, answer_id: str) -> bool:
        """Return ``True`` when another answer has already closed the Offer.

        A redelivered answer finds its own ledger entry as the reply; it is
        the same answer, so it does not count as a second one (HP-01-003).
        """
        return self.answer_id is not None and self.answer_id != answer_id


def _offer_entries(dl: CasePersistence, case_id: str) -> list[CaseLedgerEntry]:
    """The case's ``offer_case_ownership_transfer`` entries, oldest first."""
    return [
        entry
        for entry in recorded_entries_for_case(case_id=case_id, dl=dl)
        if entry.semantic_type == OFFER_CASE_OWNERSHIP_TRANSFER_SEMANTIC_TYPE
    ]


def _entry_actor(entry: CaseLedgerEntry) -> str | None:
    """The ledgered Offer's sender (its ``actor``)."""
    return snapshot_actor_id(entry.payload_snapshot.get("actor"))


def _entry_attributed_to(entry: CaseLedgerEntry) -> str | None:
    """The participant the ledgered Offer claims to speak for, if any."""
    return snapshot_actor_id(
        entry.payload_snapshot.get(wire_key("attributed_to"))
    )


def _entry_end_time(entry: CaseLedgerEntry) -> datetime | None:
    """The ledgered Offer's ``end_time``, normalised to UTC (CM-21-016).

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
    """The id of the Offer *manager_id* makes from *proposer_id*'s proposal.

    Derived, never taken from the proposal: the CASE_MANAGER keys nothing it
    emits or stores by an id another party chose, the inner Offer's id
    included (ADR-0148, DL-06-006).  A redelivery of the proposal rebuilds
    the same Offer, which the outbox queues once (OX-06-002), and the
    owner's withdrawal of the proposal names that Offer through the same
    derivation (CM-21-015).  The proposer is part of the derivation, so a
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
    whose Offer the ledger records is a redelivery (HP-01-003); its standing
    is that Offer's offerer (CM-21-019).
    """
    case = dl.read_case(case_id)
    manager_id = (
        resolve_case_manager_id(case, dl) if case is not None else None
    )
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
    dl: CasePersistence, case_id: str
) -> RecordedOwnershipOffer | None:
    """Return a recorded ownership-transfer Offer for *case_id* still open.

    An Offer is open until the ledger holds an answer, a withdrawal or an
    expiry recorded after it (CM-21-014, CM-21-015, CM-21-017, CLP-11-001),
    read through
    ``find_protocol_pair()`` with ``OFFER_CASE_OWNERSHIP_TRANSFER_REPLY_TYPES``.
    The latest open Offer is returned; ``None`` when every recorded Offer is
    closed.

    An Offer that names no transferee could never be answered, so it does not
    hold the case open.

    Args:
        dl: The CASE_MANAGER's store.
        case_id: The case a new proposal names.  The caller has already
            ruled out a redelivery (:func:`offer_made_from_proposal`), so
            every recorded Offer is an earlier one.
    """
    for entry in reversed(_offer_entries(dl, case_id)):
        if entry_target(entry) is None:
            continue
        offer = _recorded(dl, case_id, entry)
        if offer.answer_id is None:
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
