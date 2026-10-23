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

"""Inbound (driving) port — use-case interface for domain operations.

A UseCase encapsulates a single business operation. The DataLayer and
request object are supplied at construction time; the request is validated
during ``__init__`` so that ``execute()`` can focus entirely on business logic.

Port direction: **inbound (driving)** — the dispatcher calls
``execute()`` on a concrete use-case instance after routing an inbound domain
event from a driving adapter (inbox handler, CLI, MCP server).

See also: ``core/ports/dispatcher.py`` (inbound, higher-level dispatch
contract) and ``vultron/core/ports/AGENTS.md`` "Core Port
Taxonomy".

Usage::

    use_case = SomeUseCase(dl=data_layer, request=some_request)
    result = use_case.execute()
"""

from typing import Any, Protocol

from vultron.core.models.use_case_result import UseCaseResult


class UseCase(Protocol):
    """Driving port for a single core domain use case.

    Concrete implementations must:

    * Accept ``dl`` (a ``DataLayer``) and ``request`` (a domain event or
      trigger request model) in ``__init__`` and validate the request there.
    * Return a ``UseCaseResult`` subtype from ``execute()`` (UCORG-05-001,
      UCORG-05-003): ``HandlerResult`` on the received side, reporting what
      the handler did with its activity. There is no fire-and-forget
      ``None``; a handler that correctly did nothing returns
      ``HandlerResult.skipped()``.
    """

    def __init__(self, dl: Any, request: Any) -> None: ...

    def execute(self) -> UseCaseResult: ...
