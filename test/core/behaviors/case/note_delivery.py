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
"""An ``Add(Note)`` delivery shared by the intake-only and store-node tests.

Both suites need one inbound activity carrying an inline object, so they can
check what intake archives and what, if anything, gets stored.
"""

from test.support.received import received_event
from vultron.core.models.events import AnyReceivedEvent
from vultron.wire.as2.factories import add_note_to_case_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Add
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

SENDER = "https://example.org/actors/sender"
CASE_ID = "https://example.org/cases/intake-only"


def add_note_delivery(
    to: str,
) -> tuple[as_Note, as_Add, AnyReceivedEvent]:
    """Return the note, the ``Add(Note)`` carrying it inline, and its event.

    The activity is addressed *to* the actor the tree runs as: every received
    tree refuses a copy that does not name the receiver (HP-01-005).
    """
    note = as_Note(
        id_=f"{CASE_ID}/notes/n1",
        name="intake-only",
        content="a note",
        context=CASE_ID,
    )
    activity = add_note_to_case_activity(
        note, actor=SENDER, target=CASE_ID, to=[to]
    )
    return note, activity, received_event(activity)
