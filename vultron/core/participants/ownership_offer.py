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

A reply to an ownership-transfer ``Offer(VulnerabilityCase)`` — the
transferee's ``Accept`` or ``Reject``, or the offerer's ``Undo`` withdrawing
it (CM-21-015) — is acted on by the CASE_MANAGER only for an Offer it
recorded for that case and that is still open.  "Recorded"
means ledgered: the CASE_MANAGER commits an ``offer_case_ownership_transfer``
entry when it admits the Offer, and whether the Offer is still open is read
from the same ledger (CM-21-014, CLP-11-001).

The answer names one of two Offers:

- the recorded Offer itself, whose id is the entry's ``log_object_id``; or
- the copy the CASE_MANAGER forwarded to the transferee (CM-21-005).  The
  forward is a new activity with its own id, minted after the commit, and it
  is the one the transferee holds and answers.  It is not ledgered, so it is
  matched to the recorded Offer it forwards: an Offer this CASE_MANAGER
  issued, for the same case and transferee, published no earlier than that
  Offer was recorded.

:func:`recorded_ownership_offer` returns that Offer and its protocol pair;
the sender-entitlement guards read the transferee, the offerer and the open
state from it, and the use case reads the new owner from it (never from the
sender).
:func:`open_ownership_offer` returns the case's Offer that is still open, if
any, so the CASE_MANAGER can refuse a second one (CM-21-014);
:func:`is_recorded_ownership_offer` tells a redelivered Offer from a new one.

Spec: CM-21-005, CM-21-011, CM-21-013, CM-21-014, CM-21-015, CLP-11-001.
"""

from dataclasses import dataclass
from datetime import datetime

from vultron.core.models._helpers import _as_id
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.protocol_pair import (
    OFFER_CASE_OWNERSHIP_TRANSFER_EVENT_TYPE,
    OFFER_CASE_OWNERSHIP_TRANSFER_REPLY_TYPES,
    ProtocolPair,
)
from vultron.core.models.wire_keys import wire_key
from vultron.core.ports.case_persistence import CasePersistence
from vultron.errors import VultronNotFoundError


@dataclass(frozen=True)
class RecordedOwnershipOffer:
    """An ownership-transfer Offer the CASE_MANAGER ledgered for a case.

    Attributes:
        case_id: The case whose ownership the Offer transfers.
        offer_id: The id of the ledgered Offer (the entry's ``log_object_id``),
            which may differ from the id the answer names (its forward).
        transferee_id: The actor the Offer names as the new owner, read from
            the ledger entry's ``target``.
        offerer_id: The participant that made the Offer, read from the ledger
            entry: its ``attributedTo`` when the CASE_MANAGER sent it on that
            participant's behalf (CM-24-002), else its ``actor``.  ``None``
            when the entry names neither.
        pair: The Offer's request/reply state, read from the ledger.
    """

    case_id: str
    offer_id: str
    transferee_id: str
    offerer_id: str | None
    pair: ProtocolPair

    @property
    def answer_id(self) -> str | None:
        """The ledgered entry that closed the Offer, or ``None`` while open.

        Any event type in ``OFFER_CASE_OWNERSHIP_TRANSFER_REPLY_TYPES``
        closes it: the transferee's answer or the offerer's withdrawal.
        """
        return self.pair.reply_object_id

    @property
    def closed_by_event_type(self) -> str | None:
        """The ``event_type`` of the entry that closed the Offer, if any."""
        return self.pair.reply_event_type

    def is_answered_other_than(self, answer_id: str) -> bool:
        """Return ``True`` when another answer has already closed the Offer.

        A redelivered answer finds its own ledger entry as the reply; it is
        the same answer, so it does not count as a second one (HP-01-003).
        """
        return self.answer_id is not None and self.answer_id != answer_id


def _offer_entries(dl: CasePersistence, case_id: str) -> list[CaseLedgerEntry]:
    """The case's ``offer_case_ownership_transfer`` entries, oldest first."""
    entries = [
        obj
        for obj in dl.list_objects("CaseLedgerEntry")
        if isinstance(obj, CaseLedgerEntry)
        and obj.case_id == case_id
        and obj.event_type == OFFER_CASE_OWNERSHIP_TRANSFER_EVENT_TYPE
    ]
    entries.sort(key=lambda entry: entry.log_index)
    return entries


def _entry_target(entry: CaseLedgerEntry) -> str | None:
    """The transferee the ledgered Offer names (its ``target``)."""
    return _as_id(entry.payload_snapshot.get("target"))


def _entry_offerer(entry: CaseLedgerEntry) -> str | None:
    """The participant the ledgered Offer speaks for.

    A delegated Offer carries the CASE_MANAGER as ``actor`` and the
    requesting participant as ``attributedTo`` (CM-24-001, CM-24-002); an
    Offer the participant sent itself carries it as ``actor``.
    """
    snapshot = entry.payload_snapshot
    return _as_id(snapshot.get(wire_key("attributed_to"))) or _as_id(
        snapshot.get("actor")
    )


def _type_name(obj: object) -> str | None:
    """The activity type of a stored object, read by name.

    The store may hand back the wire class registered for the activity rather
    than the core one, so the type is compared by its AS2 name, not by class.
    """
    type_ = getattr(obj, "type_", None)
    value = getattr(type_, "value", type_)
    return value if isinstance(value, str) else None


def _forwarded_entry(
    dl: CasePersistence,
    case_id: str,
    offer_id: str,
    issuer_id: str,
    entries: list[CaseLedgerEntry],
) -> CaseLedgerEntry | None:
    """The recorded Offer that *offer_id* forwards, if it is a forward.

    A forward is an Offer in this store that *issuer_id* (the CASE_MANAGER)
    sent, for *case_id*, naming a transferee; it forwards the latest Offer
    for that transferee recorded no later than the forward was published.

    Both times are second-precision (``now_utc``), so a forward published in
    the same second as a later Offer to the same transferee is recorded
    resolves to that later Offer.  That is safe: the later Offer names the
    same transferee, and its own open or answered state still decides.
    """
    forward = dl.read(offer_id)
    if forward is None or _type_name(forward) != "Offer":
        return None
    if _as_id(getattr(forward, "actor", None)) != issuer_id:
        return None
    if _as_id(getattr(forward, "object_", None)) != case_id:
        return None
    transferee_id = _as_id(getattr(forward, "target", None))
    published = getattr(forward, "published", None)
    if transferee_id is None or not isinstance(published, datetime):
        return None
    candidates = [
        entry
        for entry in entries
        if _entry_target(entry) == transferee_id
        and entry.received_at <= published
    ]
    return candidates[-1] if candidates else None


def recorded_ownership_offer(
    dl: CasePersistence,
    case_id: str,
    offer_id: str,
    issuer_id: str,
) -> RecordedOwnershipOffer:
    """Return the recorded ownership-transfer Offer that *offer_id* names.

    Args:
        dl: The CASE_MANAGER's store.
        case_id: The case the answer names.
        offer_id: The Offer the answer names: the recorded Offer, or the
            forward of it the transferee received (CM-21-005).
        issuer_id: The CASE_MANAGER, the only actor whose forward stands for
            a recorded Offer.

    Raises:
        VultronNotFoundError: no ownership-transfer Offer for *case_id* was
            ledgered under *offer_id* or forwarded as it, or the recorded
            Offer names no transferee.
    """
    entries = _offer_entries(dl, case_id)
    entry = next(
        (e for e in entries if e.log_object_id == offer_id), None
    ) or _forwarded_entry(dl, case_id, offer_id, issuer_id, entries)
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
    transferee_id = _entry_target(entry)
    if transferee_id is None:
        raise VultronNotFoundError(
            f"Transferee of recorded ownership-transfer Offer for case"
            f" '{case_id}'",
            entry.log_object_id,
        )
    pair = dl.find_protocol_pair(
        case_id=case_id,
        request_event_type=OFFER_CASE_OWNERSHIP_TRANSFER_EVENT_TYPE,
        object_id=entry.log_object_id,
        reply_event_types=OFFER_CASE_OWNERSHIP_TRANSFER_REPLY_TYPES,
    )
    return RecordedOwnershipOffer(
        case_id=case_id,
        offer_id=entry.log_object_id,
        transferee_id=transferee_id,
        offerer_id=_entry_offerer(entry),
        pair=pair,
    )


def is_recorded_ownership_offer(
    dl: CasePersistence, case_id: str, offer_id: str
) -> bool:
    """Return ``True`` when *offer_id* is already ledgered as an Offer for *case_id*.

    An Offer the ledger already records is a redelivery, not a new Offer
    (HP-01-003): it is neither judged against the one-open-Offer rule nor
    committed or forwarded again.
    """
    return any(
        entry.log_object_id == offer_id
        for entry in _offer_entries(dl, case_id)
    )


def open_ownership_offer(
    dl: CasePersistence, case_id: str
) -> RecordedOwnershipOffer | None:
    """Return a recorded ownership-transfer Offer for *case_id* still open.

    An Offer is open until the ledger holds an answer or a withdrawal
    recorded after it (CM-21-014, CM-21-015, CLP-11-001), read through
    ``find_protocol_pair()`` with ``OFFER_CASE_OWNERSHIP_TRANSFER_REPLY_TYPES``.
    The latest open Offer is returned; ``None`` when every recorded Offer is
    closed.

    An Offer that names no transferee could never be answered, so it does not
    hold the case open.

    Args:
        dl: The CASE_MANAGER's store.
        case_id: The case a new Offer names.  The caller has already ruled out
            a redelivery (:func:`is_recorded_ownership_offer`), so every
            recorded Offer is an earlier one.
    """
    for entry in reversed(_offer_entries(dl, case_id)):
        if _entry_target(entry) is None:
            continue
        offer = _recorded(dl, case_id, entry)
        if offer.answer_id is None:
            return offer
    return None


__all__ = [
    "RecordedOwnershipOffer",
    "is_recorded_ownership_offer",
    "open_ownership_offer",
    "recorded_ownership_offer",
]
