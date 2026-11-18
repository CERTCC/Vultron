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

"""Server-sent events, read from a stream's lines as a browser reads them.

The live Vultron case reader follows a case over a node's ledger
event-stream endpoint (#6531).  :func:`server_sent_events` turns the lines of
that response into one :class:`ServerSentEvent` per dispatched event, by the
WHATWG HTML rules for an ``EventSource``: a blank line dispatches the event
its ``data:`` lines built, a line starting with ``:`` is a comment, an
``id:`` sets the last event id the stream resumes from, and an event cut off
by the end of the stream is never dispatched.

It reads the lines only; it holds no connection and sends nothing.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Final

#: The type of an event that names none.
MESSAGE: Final = "message"


@dataclass(frozen=True)
class ServerSentEvent:
    """One dispatched server-sent event.

    Attributes:
        type: The event's ``event:`` field, ``message`` when it has none.
        data: Its ``data:`` lines, joined by newlines.
        last_event_id: The last ``id:`` the stream had sent when the event
            was dispatched, ``None`` before any; a reconnect sends it back
            as ``Last-Event-ID``.
    """

    type: str
    data: str
    last_event_id: str | None


def _field(line: str) -> tuple[str, str]:
    """*line*'s field name and value, one leading space dropped."""
    name, colon, value = line.partition(":")
    if not colon:
        return line, ""
    return name, value.removeprefix(" ")


def server_sent_events(lines: Iterable[str]) -> Iterator[ServerSentEvent]:
    """Each event the stream's *lines* dispatch, in order.

    Args:
        lines: The response's lines, without their line endings.
    """
    data: list[str] = []
    event_type = ""
    last_event_id: str | None = None
    for line in lines:
        if line == "":
            if data:
                yield ServerSentEvent(
                    type=event_type or MESSAGE,
                    data="\n".join(data),
                    last_event_id=last_event_id,
                )
            data = []
            event_type = ""
            continue
        if line.startswith(":"):
            continue
        name, value = _field(line)
        if name == "data":
            data.append(value)
        elif name == "event":
            event_type = value
        elif name == "id" and "\0" not in value:
            last_event_id = value
        # Any other field, ``retry:`` among them, is ignored.


__all__ = ["MESSAGE", "ServerSentEvent", "server_sent_events"]
