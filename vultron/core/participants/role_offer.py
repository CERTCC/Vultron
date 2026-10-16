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

"""The role Offers the CASE_MANAGER recorded in the case ledger (CM-33).

A role Offer is ``Offer(CaseParticipantRole)`` (ADR-0039).  The CASE_MANAGER
commits each one it admits as an ``offer_case_participant_role`` entry before
it forwards the Offer to the target (CM-33-001), so the ledger is the record
of which Offers it holds (CLP-11-001).

The target's ``Accept`` or ``Reject`` names one of two Offers: the recorded
Offer itself, or the CASE_MANAGER's forward of it, which the target holds.
:func:`answered_role_offer` resolves either to the recorded Offer, the
forward through its ``inReplyTo`` (CM-33-005), and reads whether the Offer
is still open from the ledger.

A case may hold several role Offers open at once, to different targets or
of different roles, so an Offer is closed only by an answer *to it*: an
``accept_case_participant_role`` or ``reject_case_participant_role`` entry
whose answered Offer is this one or its forward.  The answer an entry names
is the Offer its snapshot carries as ``object``, which the CASE_MANAGER
checked against the recorded Offer before committing it.
"""

from dataclasses import dataclass

from vultron.core.models._helpers import _as_id
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.protocol_pair import (
    CASE_PARTICIPANT_ROLE_OFFER_REPLY_TYPES,
    ProtocolPair,
)
from vultron.core.participants.offer_forward import (
    entry_target,
    forwarded_offer_entry,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.predicates.addressing import same_actor_id
from vultron.core.sync_helpers import recorded_entries_for_case
from vultron.enums.roles import CVDRole
from vultron.errors import VultronNotFoundError

#: The ``event_type`` of the entry that records an admitted role Offer.
OFFER_CASE_PARTICIPANT_ROLE_EVENT_TYPE = "offer_case_participant_role"

#: The ``event_type`` of the entry that records the target's Accept: the
#: grant (CM-02-016).
ACCEPT_CASE_PARTICIPANT_ROLE = "accept_case_participant_role"


def recorded_role_offer_entries(
    dl: CasePersistence, case_id: str
) -> list[CaseLedgerEntry]:
    """The case's ``offer_case_participant_role`` entries, oldest first."""
    return [
        entry
        for entry in recorded_entries_for_case(case_id=case_id, dl=dl)
        if entry.event_type == OFFER_CASE_PARTICIPANT_ROLE_EVENT_TYPE
    ]


def recorded_role_offer(
    dl: CasePersistence, case_id: str, offer_id: str
) -> CaseLedgerEntry | None:
    """The entry that records the role Offer *offer_id*, or ``None``.

    A role Offer the ledger already records is a redelivery, not a new Offer
    (HP-01-003), when the entry names the same role and target
    (:func:`entry_names_role_offer`).
    """
    return next(
        (
            entry
            for entry in recorded_role_offer_entries(dl, case_id)
            if entry.log_object_id == offer_id
        ),
        None,
    )


def entry_names_role_offer(
    entry: CaseLedgerEntry, role: CVDRole, target_actor_id: str | None
) -> bool:
    """Return ``True`` when *entry* records an Offer of *role* to the target.

    An Offer that reuses a recorded Offer's id but names another role or
    target is not a redelivery of it (ID-02-001).
    """
    role_obj = entry.payload_snapshot.get("object")
    recorded_role = (
        role_obj.get("role") if isinstance(role_obj, dict) else None
    )
    recorded_target = entry_target(entry)
    return (
        recorded_role == role.value
        and target_actor_id is not None
        and recorded_target is not None
        and same_actor_id(recorded_target, target_actor_id)
    )


def role_offer_forward_id(
    case_manager_id: str, case_id: str, offer_id: str
) -> str:
    """The id of the CASE_MANAGER's forward of the role Offer *offer_id*.

    Derived from the recorded Offer (ID-04-004, OX-06-002), so a redelivery
    of the Offer rebuilds the same forward, which the outbox does not queue
    twice while it is pending.
    """
    return derived_activity_id(
        "forward_case_participant_role", case_manager_id, case_id, offer_id
    )


@dataclass(frozen=True)
class RecordedRoleOffer:
    """A role Offer the CASE_MANAGER ledgered, as an answer to it resolves.

    Attributes:
        entry: The ``offer_case_participant_role`` entry that records it.
        target_id: The actor the recorded Offer names as its ``target``: the
            only actor that may answer it (CM-33-005).
        pair: The Offer's request/reply state, read from the ledger: closed
            by the first answer to this Offer committed after it.
    """

    entry: CaseLedgerEntry
    target_id: str
    pair: ProtocolPair

    @property
    def offer_id(self) -> str:
        """The recorded Offer's id (the entry's ``log_object_id``)."""
        return self.entry.log_object_id

    @property
    def answer_id(self) -> str | None:
        """The ledgered answer that closed the Offer, or ``None`` while open."""
        return self.pair.reply_object_id

    @property
    def closed_by_event_type(self) -> str | None:
        """The ``event_type`` of the entry that closed the Offer, if any."""
        return self.pair.reply_event_type


def _closing_answer(
    entries: list[CaseLedgerEntry],
    offer: CaseLedgerEntry,
    forward_id: str,
) -> CaseLedgerEntry | None:
    """The first answer to *offer* committed after it, if any.

    An answer entry answers *offer* when the Offer its snapshot carries is the
    recorded Offer or its forward (*forward_id*).  An answer to another role
    Offer of the same case does not close this one.
    """
    answered = {offer.log_object_id, forward_id}
    return next(
        (
            entry
            for entry in entries
            if entry.log_index > offer.log_index
            and entry.event_type in CASE_PARTICIPANT_ROLE_OFFER_REPLY_TYPES
            and _as_id(entry.payload_snapshot.get("object")) in answered
        ),
        None,
    )


def answered_role_offer(
    dl: CasePersistence, case_id: str, offer_id: str, issuer_id: str
) -> RecordedRoleOffer:
    """Return the recorded role Offer an answer naming *offer_id* answers.

    Args:
        dl: The CASE_MANAGER's store.
        case_id: The case the answer names.
        offer_id: The Offer the answer names: the recorded Offer, or the
            CASE_MANAGER's forward of it, resolved through the forward's
            ``inReplyTo`` as this store holds it (CM-33-005).  The copy of
            the Offer the answer embeds is never read.
        issuer_id: The case's CASE_MANAGER, the only actor whose forward
            stands for a recorded Offer.

    Raises:
        VultronNotFoundError: no role Offer for *case_id* was ledgered under
            *offer_id*, and *offer_id* is not a forward whose ``inReplyTo``
            links to one for the same target; or the recorded Offer names no
            target.
    """
    entries = recorded_entries_for_case(case_id=case_id, dl=dl)
    offers = [
        entry
        for entry in entries
        if entry.event_type == OFFER_CASE_PARTICIPANT_ROLE_EVENT_TYPE
    ]
    entry = next(
        (e for e in offers if e.log_object_id == offer_id), None
    ) or forwarded_offer_entry(
        dl,
        case_id=case_id,
        forward_id=offer_id,
        issuer_id=issuer_id,
        entries=offers,
        case_field="context",
    )
    if entry is None:
        raise VultronNotFoundError(
            f"Role Offer recorded for case '{case_id}'", offer_id
        )
    target_id = entry_target(entry)
    if target_id is None:
        raise VultronNotFoundError(
            f"Target of recorded role Offer for case '{case_id}'",
            entry.log_object_id,
        )
    closing = _closing_answer(
        entries,
        entry,
        role_offer_forward_id(issuer_id, case_id, entry.log_object_id),
    )
    pair = ProtocolPair(
        case_id=case_id,
        request_event_type=OFFER_CASE_PARTICIPANT_ROLE_EVENT_TYPE,
        object_id=entry.log_object_id,
        reply_event_types=CASE_PARTICIPANT_ROLE_OFFER_REPLY_TYPES,
        reply_object_id=closing.log_object_id if closing else None,
        reply_event_type=closing.event_type if closing else None,
        request_found=True,
    )
    return RecordedRoleOffer(entry=entry, target_id=target_id, pair=pair)


__all__ = [
    "ACCEPT_CASE_PARTICIPANT_ROLE",
    "OFFER_CASE_PARTICIPANT_ROLE_EVENT_TYPE",
    "RecordedRoleOffer",
    "answered_role_offer",
    "entry_names_role_offer",
    "recorded_role_offer",
    "recorded_role_offer_entries",
    "role_offer_forward_id",
]
