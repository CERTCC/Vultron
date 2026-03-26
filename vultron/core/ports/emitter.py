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

"""Outbound (driven) port — activity emitter interface.

``ActivityEmitter`` is the interface the core uses to send outbound
ActivityStreams activities to recipient actor inboxes.  Defining it here,
alongside the other core ports, makes the architectural role explicit and
allows concrete emitter implementations to be injected in tests.

Port direction: **outbound (driven)** — core use cases call
``emit(activity, recipients)`` to dispatch a completed domain action to
one or more recipient actors.  The adapter layer handles the actual
delivery mechanics (local DataLayer write, HTTP POST, queue, etc.) without
coupling the core to any transport.

See also: ``core/ports/dispatcher.py`` (inbound counterpart) and
``notes/architecture-ports-and-adapters.md`` "Dispatch vs Emit Terminology".
"""

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from vultron.core.models.activity import VultronActivity


class ActivityEmitter(Protocol):
    """Driven port: delivers an outbound domain activity to recipient actors.

    Core use cases call ``emit()`` after completing a state transition that
    produces an outbound activity.  The concrete implementation resolves
    each recipient's inbox and performs the delivery — writing to a local
    DataLayer collection for same-server actors or enqueuing an HTTP POST
    for remote actors.

    ``activity`` is the domain activity to deliver.
    ``recipients`` is a sequence of actor ID strings (URI-formatted) that
    should receive the activity.
    """

    async def emit(
        self,
        activity: "VultronActivity",
        recipients: list[str],
    ) -> None: ...
