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

Port direction: **outbound (driven)** — the outbox handler calls
``emit(activity_id, json_body, recipients)`` to hand a sealed activity body
to one or more recipient actors.  The adapter layer handles the actual
delivery mechanics (HTTP POST, in-process routing in tests, etc.) without
coupling the core to any transport, and delivers the body unchanged
(VM-08-003).

See also: ``core/ports/dispatcher.py`` (inbound counterpart) and
``vultron/core/ports/AGENTS.md`` "Dispatch vs Emit Terminology".
"""

from typing import Protocol


class ActivityEmitter(Protocol):
    """Driven port: delivers an outbound activity's sealed body to recipients.

    The outbox handler calls ``emit()`` with the JSON text the emitting
    adapter sealed for the activity (VM-08-003).  The concrete implementation
    resolves each recipient's inbox and POSTs that text as-is; it is a dumb
    relay and MUST NOT parse, enrich, or re-serialise the body (ADR-0074).

    ``activity_id`` names the activity, for logging and error reporting.
    ``json_body`` is the sealed AS2 document to deliver, byte for byte.
    ``recipients`` is a sequence of actor ID strings (URI-formatted) that
    should receive the activity.
    """

    async def emit(
        self,
        activity_id: str,
        json_body: str,
        recipients: list[str],
    ) -> None: ...
