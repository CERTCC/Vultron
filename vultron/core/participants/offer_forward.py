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

"""Resolve the CASE_MANAGER's forward of an Offer to the Offer it recorded.

An Offer the CASE_MANAGER relays to its target is ledgered as received, then
forwarded as a new ``Offer`` with its own id, which is the one the target
holds and answers.  The forward is not ledgered, so it carries ``inReplyTo``
set to the recorded Offer's id, and an answer naming the forward is resolved
through that link, read from the forward in the CASE_MANAGER's own store,
never from the copy the answer embeds (CM-21-018, CM-33-005).

:func:`forwarded_offer_entry` is that one resolution, shared by the
ownership-transfer Offer (``vultron.core.participants.ownership_offer``) and
the role Offer (``vultron.core.participants.role_offer``).
"""

from typing import Literal

from vultron.core.models._helpers import _as_id
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.predicates.addressing import snapshot_actor_id


def activity_type_name(obj: object) -> str | None:
    """The activity type of a stored object, read by name.

    The store may hand back the wire class registered for the activity rather
    than the core one, so the type is compared by its AS2 name, not by class.
    """
    type_ = getattr(obj, "type_", None)
    value = getattr(type_, "value", type_)
    return value if isinstance(value, str) else None


def entry_target(entry: CaseLedgerEntry) -> str | None:
    """The actor a ledgered Offer names as its ``target``.

    The snapshot keeps the sender's spelling, so the id is normalised
    (OID-01-006): it is compared with the forward's target, and the
    ownership transferee becomes the case owner.
    """
    return snapshot_actor_id(entry.payload_snapshot.get("target"))


def forwarded_offer_entry(
    dl: CasePersistence,
    *,
    case_id: str,
    forward_id: str,
    issuer_id: str,
    entries: list[CaseLedgerEntry],
    case_field: Literal["object_", "context"],
) -> CaseLedgerEntry | None:
    """The recorded Offer that *forward_id* forwards, if it is a forward.

    A forward is an Offer in this store that *issuer_id* (the CASE_MANAGER)
    sent, for *case_id* (named in *case_field*: the ownership-transfer Offer
    offers the case as its ``object``, a role Offer names it in
    ``context``), naming a target.  It names the recorded Offer it forwards
    in ``inReplyTo``; the entry returned is the one among *entries* whose
    ``log_object_id`` is that link and whose ``target`` is the forward's
    target.  A forward with no link, or a link to no such entry, stands for
    no recorded Offer, and nothing else is tried: matching by time would let
    a late answer to one Offer close a newer one (#4565).
    """
    forward = dl.read(forward_id)
    if forward is None or activity_type_name(forward) != "Offer":
        return None
    if _as_id(getattr(forward, "actor", None)) != issuer_id:
        return None
    if _as_id(getattr(forward, case_field, None)) != case_id:
        return None
    target_id = snapshot_actor_id(getattr(forward, "target", None))
    linked_id = _as_id(getattr(forward, "in_reply_to", None))
    if target_id is None or linked_id is None:
        return None
    return next(
        (
            entry
            for entry in entries
            if entry.log_object_id == linked_id
            and entry_target(entry) == target_id
        ),
        None,
    )


__all__ = ["activity_type_name", "entry_target", "forwarded_offer_entry"]
