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

"""Ids derived from what an activity answers, so a retry names the same activity.

An outbound activity that answers one request — an inbound activity, or the
earlier activity it supersedes — takes its id from that request rather than
from a fresh UUID.  A retry of the work that sends it then rebuilds the
activity under the id its first attempt used, and the outbox finds that id
already pending instead of queuing a second activity (ID-04-004, OX-06-002,
ADR-0119).

Core owns the derivation because core decides what an activity answers; the
adapter layer's activity factories import it from here for the ids they derive
themselves (ARCH-01-001).
"""

import uuid


def derived_activity_id(*parts: str) -> str:
    """Return a stable ``urn:uuid`` id derived from *parts*.

    An outbound activity that answers one inbound activity takes its id from
    what it answers, not from a fresh UUID, so a redelivery of the inbound
    activity names the response its first delivery emitted (ID-04-004).
    Parts are joined with a separator no IRI can contain, so distinct part lists
    never collide; callers put a kind label first so two kinds
    of response to one activity do not share an id.
    """
    return f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, '\x1f'.join(parts))}"
