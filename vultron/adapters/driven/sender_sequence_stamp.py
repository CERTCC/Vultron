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

"""Number an outbound case activity with its sender's next sequence (SYNC-21).

A participant numbers each case activity it sends the CASE_MANAGER that
states a ``ledgerPosition``, except a ledger request (SYNC-21-001); the
CASE_MANAGER numbers none of its own.  The wire factories hold no counter
and no roster, so :func:`with_sender_sequence` decides here, from the
sender's store, whether the activity takes a number, allocates it
(:func:`~vultron.core.sync_helpers.allocate_sender_sequence`) and has the
factory stamp it (:func:`~vultron.wire.as2.factories.stamp_sender_sequence`).

:func:`with_outbound_stamps` is what an adapter path that stores or seals an
outbound activity calls: the ledger position first, because the number goes
only on an activity that states one, then the number.  The caller holds one
``dl.transaction()`` around the stamps and the seal, so the number is used
exactly when the body carrying it is sealed: a failed seal gives it back,
and a sealed body keeps it for every resend (SYNC-21-003).
"""

import logging
from typing import TypeVar, cast

from vultron.adapters.driven.ledger_position_stamp import (
    with_sender_ledger_position,
)
from vultron.adapters.outbox_sealed_body import read_sealed_body
from vultron.core.behaviors.case.nodes.addressee import named_in_to
from vultron.core.models._helpers import _as_id
from vultron.core.participants.authority import case_manager_address
from vultron.core.participants.role_predicate import has_role
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.sync_helpers import (
    allocate_sender_sequence,
    first_case_with_ledger,
    resume_sender_sequence_at,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    sender_sequence_case_ids,
    stamp_sender_sequence,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

logger = logging.getLogger(__name__)

_Model = TypeVar("_Model")


def _recipient_ids(to: object) -> list[str]:
    """*to* as a list of ids: AS2 allows one recipient or a list of them."""
    if to is None:
        return []
    values = to if isinstance(to, (list, tuple)) else [to]
    return [rid for rid in (_as_id(value) for value in values) if rid]


def _goes_to_the_case_manager(
    dl: CasePersistence, activity: as_Activity, case_id: str, sender: str
) -> bool:
    """Whether *sender* is a participant sending *activity* to the manager.

    The CASE_MANAGER's own activities take no number: the ledger orders its
    case events (SYNC-21-001, CLP-14-001).  A participant's activity takes
    one when its ``to`` addresses the case's CASE_MANAGER by the rule the
    CASE_MANAGER's own addressee door reads (:func:`named_in_to`): named
    directly, or through a participants collection it belongs to.
    """
    if has_role(sender, case_id, CVDRole.CASE_MANAGER, dl):
        return False
    address = case_manager_address(dl, case_id)
    if address is None:
        return False
    return named_in_to(dl, address, _recipient_ids(activity.to))


def with_sender_sequence(dl: CasePersistence, activity: _Model) -> _Model:
    """Return *activity* numbered with its sender's next ``senderSequence``.

    Allocates and saves the number in *dl*, so call it inside the
    transaction that seals the activity.  *activity* is returned unchanged
    when it is no activity, takes no number
    (:func:`~vultron.wire.as2.factories.sender_sequence_case_ids`), names
    no case whose ledger *dl* holds, is the CASE_MANAGER's own or not
    addressed to it, or was already sealed under its id: a rebuild hands
    back the sealed body, so it must not use a second number (SYNC-21-003).
    One that already carries a number (posted to the outbox numbered) keeps
    it, and the counter moves up to it so the number is not used again.
    """
    if not isinstance(activity, as_Activity):
        return activity
    case_id = first_case_with_ledger(
        list(sender_sequence_case_ids(activity)), dl
    )
    if case_id is None:
        return activity
    if activity.id_ and read_sealed_body(dl, activity.id_) is not None:
        return activity
    sender = _as_id(activity.actor)
    if sender is None or not _goes_to_the_case_manager(
        dl, activity, case_id, sender
    ):
        return activity
    if activity.sender_sequence is not None:
        # Numbered by whoever posted it: keep its number, and count it as
        # used, so no later activity is numbered with it again (SYNC-21-002).
        resume_sender_sequence_at(
            dl, case_id, sender, activity.sender_sequence + 1
        )
        return activity
    number = allocate_sender_sequence(dl, case_id, sender)
    logger.debug(
        "Numbered activity '%s' from '%s' on case '%s' with sender"
        " sequence %d (SYNC-21-001)",
        activity.id_,
        sender,
        case_id,
        number,
    )
    return cast(_Model, stamp_sender_sequence(activity, number))


def with_outbound_stamps(dl: CasePersistence, activity: _Model) -> _Model:
    """*activity* with its sender's ledger position, then its number.

    See :func:`~vultron.adapters.driven.ledger_position_stamp.with_sender_ledger_position`
    and :func:`with_sender_sequence`; call it inside the transaction that
    seals the activity.
    """
    return with_sender_sequence(dl, with_sender_ledger_position(dl, activity))


__all__ = ["with_outbound_stamps", "with_sender_sequence"]
