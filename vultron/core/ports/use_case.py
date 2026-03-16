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

"""Generic ``UseCase`` protocol for core domain use cases.

``UseCase[Req, Res]`` is the standard interface all use-case classes implement.
Each use case:

* accepts **exactly one request object** (typically a ``VultronEvent`` subclass
  or a trigger-specific request model)
* returns **exactly one response object** (or ``None`` for fire-and-forget cases)
* exposes a single ``execute(request)`` entry point

The ``DataLayer`` instance required by most use cases is supplied at
construction time so that adapters interact with use cases through a uniform
``execute()`` call regardless of their internal dependencies.

See ``notes/use-case-behavior-trees.md`` "Standardized Use Case Interface" for
the rationale and migration guidance.  P75-4 MUST convert every use case it
touches to this class interface — do not leave behind any mix of old-style
``fn(event, dl)`` callables alongside the new class-based ones within a single
migration batch.
"""

from typing import Generic, Protocol, TypeVar

Req = TypeVar("Req")
Res = TypeVar("Res")


class UseCase(Protocol[Req, Res]):
    """Driving port for a single core domain use case.

    Adapters obtain a ``UseCase`` instance (with ``DataLayer`` already
    injected) and call ``execute(request)`` without knowing the concrete
    implementation.

    Type parameters:

    * ``Req`` — the request type (a domain event or trigger request model)
    * ``Res`` — the response type; use ``None`` for fire-and-forget cases
    """

    def execute(self, request: Req) -> Res: ...
