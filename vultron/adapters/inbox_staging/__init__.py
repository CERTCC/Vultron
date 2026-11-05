#!/usr/bin/env python
"""Staging for an inbound activity and its inline objects (#3763, #4871).

The receiver keeps no copy of a received activity under the id its sender
chose (DL-06-006), and no record of an object the activity carries inline: a
case, note or embargo a sender inlines is a claim, and only the handler, after
its guards, writes the core record it gives rise to (CLP-10-038, CLP-10-039;
ADR-0111 as amended).  Writing them at receipt let a sender seed a case
replica ahead of the trust check that should refuse it (PCR-03-004,
CBT-01-011), and let a received ``Create`` read as one the receiver sent
(#4866).

Routing still needs the activity rebuilt through the store's read pipeline
(``_from_row`` → field expansion → semantic coercion), which is what turns
the parsed wire graph into the shape the patterns match.  So each delivery is
staged in a :class:`_StagingStore`: an in-memory store, emptied before and
after each use, that holds the activity's row and its inline objects' rows,
and answers any other read from the receiver's own store, so an object the
receiver already holds is always the one routing sees.  The rebuild reads the
activity from it, and nothing staged reaches the receiver's store.

An activity deferred until its case is known is replayed later, by id, after
the staging store has been emptied.  It is held for that replay on the
activity's one
:class:`~vultron.core.models.received_activity_record.ReceivedActivityRecord`
(:meth:`InlineObjectStaging.hold_for_replay`), keyed by the receiver: the
received body the parser sealed, beside the staged inline rows, with the
record marked as owing a replay (IO-03-009, ADR-0154).  The replay parses
that body again, stages it with the held rows and releases the record
(:meth:`InlineObjectStaging.rehydrate_deferred`).

The package keeps the scratch store in ``store`` and the staging that uses it
in ``staging`` (CS-18-005).
"""

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

from vultron.adapters.inbox_staging.staging import (
    InlineObjectStaging,
)

__all__ = [
    "InlineObjectStaging",
]
