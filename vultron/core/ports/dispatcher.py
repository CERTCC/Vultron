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

See also: ``core/ports/use_case.py`` (inbound, per-use-case contract) and
``notes/architecture-ports-and-adapters.md`` "Core Port Taxonomy".
"""

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from vultron.core.models.events import VultronEvent
    from vultron.core.ports.datalayer import DataLayer


class ActivityDispatcher(Protocol):
    """Driving port: dispatches a domain event to the appropriate use case.

    Adapters (inbox handler, CLI, MCP server) call ``dispatch()`` with a
    fully-populated ``VultronEvent`` and the ``DataLayer`` instance scoped to
    the current actor.  The concrete implementation looks up the matching use
    case from the routing table and invokes it.
    """

    def dispatch(self, event: "VultronEvent", dl: "DataLayer") -> None: ...
