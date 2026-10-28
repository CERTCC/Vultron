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

"""Stamp an outbound case activity with its sender's ledger tail (SYNC-18-001).

The adapters that build outbound activities hold the sender's store, which
the wire factories do not.  :func:`with_sender_ledger_position` reads the tail
of the case the activity is about from that store and has the factory stamp
it (:func:`~vultron.wire.as2.factories.stamp_ledger_position`), so the stamp
is the tail when the activity is built (SYNC-18-002).  Every adapter path that
stores or seals an outbound activity calls it before the activity is stored,
so the stored activity, the sealed body the outbox delivers and the CASE_MANAGER's
ledger entry for its own act all carry the same position.
"""

import logging
from typing import TypeVar, cast

from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.sync_helpers import (
    first_case_with_ledger,
    ledger_tail_position,
)
from vultron.wire.as2.factories import (
    ledger_position_case_ids,
    stamp_ledger_position,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

logger = logging.getLogger(__name__)

_Model = TypeVar("_Model")


def with_sender_ledger_position(
    dl: CasePersistence, activity: _Model
) -> _Model:
    """Return *activity* stamped with the tail of the case it is about.

    The case is the first one :func:`ledger_position_case_ids` names whose
    ledger *dl* holds (:func:`first_case_with_ledger`).  *activity* is returned
    unchanged when it is no activity, already states a position, has an
    object that states its own, or names no case *dl* holds: its sender
    holds no ledger to state yet (SYNC-18-001).
    """
    if not isinstance(activity, as_Activity):
        return activity
    case_id = first_case_with_ledger(
        list(ledger_position_case_ids(activity)), dl
    )
    if case_id is None:
        return activity
    position = ledger_tail_position(case_id, dl)
    logger.debug(
        "Stamped activity '%s' with ledger position %d of case '%s'"
        " (SYNC-18-001)",
        activity.id_,
        position.log_index,
        case_id,
    )
    return cast(_Model, stamp_ledger_position(activity, position))


__all__ = ["with_sender_ledger_position"]
