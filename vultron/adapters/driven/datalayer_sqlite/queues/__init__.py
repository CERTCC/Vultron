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

"""Inbox/outbox queues, delivery attempt counters and the dead-letter store.

Each of these lives in its owning actor's store (ADR-0073), so none of these
functions takes or filters on an ``actor_id``.  That removes a whole class of
defect in which a queue was written under one spelling of an actor id and read
under another — the cause of BUG-2026040901 and of the ``outbox_list()``
requires-``clone_for_actor`` pitfall.

``record_outbox_item(actor_id, ...)`` and ``outbox_list_for_actor(actor_id)``
used to exist so that an unscoped DataLayer could name the actor explicitly.
Every one of their call sites passed the *executing* actor's own id, so with a
mandatory actor scope they are exactly :func:`outbox_append` and
:func:`outbox_list` and have been folded into them.

The attempt counters and dead-letter store (OX-13-001–004) arrived after the
per-actor split and are scoped the same way: delivery bookkeeping about an
actor's own outbox is that actor's own data, so it is keyed on ``activity_id``
alone within the actor's store rather than on ``(actor_id, activity_id)``
within a shared one.

Grouped by concern (CS-18-005): ``mailboxes`` (the inbox and outbox FIFOs),
``attempts`` (the attempt counters) and ``dead_letters`` (the dead-letter
stores).
"""

from vultron.adapters.driven.datalayer_sqlite.queues.attempts import (
    clear_inbox_attempt_count,
    clear_outbox_attempt_count,
    get_inbox_attempt_count,
    get_outbox_attempt_count,
    set_inbox_attempt_count,
    set_outbox_attempt_count,
)
from vultron.adapters.driven.datalayer_sqlite.queues.dead_letters import (
    dead_letter_append,
    dead_letter_list,
    inbox_dead_letter_append,
    inbox_dead_letter_list,
)
from vultron.adapters.driven.datalayer_sqlite.queues.mailboxes import (
    inbox_append,
    inbox_list,
    inbox_pop,
    outbox_append,
    outbox_list,
    outbox_pop,
)

__all__ = [
    "clear_inbox_attempt_count",
    "clear_outbox_attempt_count",
    "dead_letter_append",
    "dead_letter_list",
    "get_inbox_attempt_count",
    "get_outbox_attempt_count",
    "inbox_append",
    "inbox_dead_letter_append",
    "inbox_dead_letter_list",
    "inbox_list",
    "inbox_pop",
    "outbox_append",
    "outbox_list",
    "outbox_pop",
    "set_inbox_attempt_count",
    "set_outbox_attempt_count",
]
