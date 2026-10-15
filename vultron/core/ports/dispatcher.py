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

"""Inbound (driving) port — activity dispatcher interface.

``ActivityDispatcher`` is the interface the core exposes for driving adapters
(e.g., the HTTP inbox handler) to call into the use-case layer. Defining it
here, alongside the other core ports, makes the architectural role explicit and
allows concrete dispatcher implementations to be injected in tests.

Port direction: **inbound (driving)** — external adapters call
``dispatch(event, dl)`` to route an inbound domain event to the
appropriate use case.

``CaseUpkeep`` is the hook a dispatcher runs before it handles anything for
a case, so time-driven case work is done lazily, with no scheduler.  The
dispatchers know only the hook's shape; the composition root decides which
hooks run.

See also: ``core/ports/use_case.py`` (inbound, per-use-case contract) and
``vultron/core/ports/AGENTS.md`` "Core Port Taxonomy".
"""

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from vultron.core.models.events import VultronEvent
    from vultron.core.models.use_case_result import HandlerResult
    from vultron.core.ports.case_outbox import CaseOutboxPersistence
    from vultron.core.ports.datalayer import DataLayer


class ActivityDispatcher(Protocol):
    """Driving port: dispatches a domain event to the appropriate use case.

    Adapters (inbox handler, CLI, MCP server) call ``dispatch()`` with a
    fully-populated ``VultronEvent`` and the ``DataLayer`` instance scoped to
    the current actor.  The concrete implementation looks up the matching use
    case from the routing table, invokes it, and returns its ``HandlerResult``
    (UCORG-05-010). When no handler runs because the activity is unroutable,
    the dispatcher synthesizes a ``REFUSED`` verdict instead (UCORG-05-012).
    Callers other than the inbox pipeline MAY ignore the result.
    """

    def dispatch(
        self, event: "VultronEvent", dl: "DataLayer"
    ) -> "HandlerResult": ...


class CaseUpkeep(Protocol):
    """Work an actor does on a case before it handles anything for it.

    A dispatcher calls each hook it was built with before it runs the use
    case for an activity or a trigger that names a case, so the use case sees
    the case as it now stands.  *case_id* and *actor_id* are full ids;
    *activity_id* is the inbound activity being handled, or ``None`` for a
    trigger.  A hook that does nothing for this actor or case returns quietly.
    A hook whose work fails logs it and returns, leaving it for the next
    time the case is handled; it raises only on a wiring or programming
    error, which the dispatcher does not swallow.
    """

    def __call__(
        self,
        dl: "CaseOutboxPersistence",
        *,
        case_id: str,
        actor_id: str,
        activity_id: str | None,
    ) -> None: ...
