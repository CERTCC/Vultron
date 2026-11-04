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
"""Actor-local in-memory pending-assertion store.

:class:`PendingAssertionStore` tracks outbound log-entry assertions that
have been emitted but not yet confirmed by a canonical
``Announce(CaseLedgerEntry)`` or ``Reject(CaseLedgerEntry)`` round-trip.
While an entry is *pending* and within the configurable timeout window,
duplicate re-emits for the same ``(case_id, semantic_type, object_id)`` triple
are suppressed.

This is **not** persisted and **not** a DataLayer entity.  The store is
intentionally ephemeral: entries are lost on actor restart (the catch-up
gate in #791 replays any unconfirmed log entries after restart).

**A lookup reads no clock; its caller supplies the instant.**  Every lookup
(:meth:`PendingAssertionStore.is_suppressed`,
:meth:`~PendingAssertionStore.pending_for_subject`,
:meth:`~PendingAssertionStore.clear_activity`) takes the instant it judges an
entry's age against, and applies the SYNC-11-005 timeout mark itself against
that instant.  Under the demo recording clock every clock read costs a 10 ms
tick, so a lookup that read the clock itself moved every later timestamp and
hash in the recording when it raced another thread (#5591).  The instant comes
from the act the caller is already performing — one read per act, taken
whether or not the lookup then suppresses anything — so the lookup's verdict
cannot move the clock and thread interleaving cannot move the verdict.

:meth:`~PendingAssertionStore.expire_timed_out` is the explicit sweep, and the
one method here that reads the clock; nothing depends on it for the timeout to
fire, because every lookup evaluates expiry.

Spec: SYNC-11-001 through SYNC-11-005.
"""

from vultron.core.models.pending_assertion.registry import (
    get_pending_assertion_store,
    record_pending_assertion,
    reset_pending_assertion_stores,
    suppressed_repeat_reason,
)
from vultron.core.models.pending_assertion.store import (
    ASSERTED_ACTIVITY_KEY,
    DEFAULT_PENDING_ASSERTION_TIMEOUT,
    PendingAssertion,
    PendingAssertionStore,
)
from vultron.core.models.protocol_pair import ProtocolPair

__all__ = [
    "ASSERTED_ACTIVITY_KEY",
    "DEFAULT_PENDING_ASSERTION_TIMEOUT",
    "PendingAssertion",
    "PendingAssertionStore",
    "ProtocolPair",
    "get_pending_assertion_store",
    "record_pending_assertion",
    "reset_pending_assertion_stores",
    "suppressed_repeat_reason",
]
