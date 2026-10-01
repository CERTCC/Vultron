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

"""Inbound (driving) port — trigger dispatcher interface (ADR-0110).

``TriggerDispatcher`` is the one-method interface driving adapters (the
FastAPI trigger routers, a CLI) call to run an actor-initiated trigger.  It is
the trigger-side twin of :class:`~vultron.core.ports.dispatcher.ActivityDispatcher`:
one method, routed by a data table (``vultron.trigger_registry``), returning the
use case's typed result.

The return type is bound to the request's type.  Every concrete
:class:`~vultron.core.use_cases.triggers.requests.TriggerRequest` binds the
:class:`~vultron.core.models.use_case_result.TriggerResult` subtype its verb
returns, so a call site receives that subtype with no cast and no per-verb
port method (UCORG-05-006).

Port direction: **inbound (driving)** — adapters call
``trigger(request, dl)`` with the request built from the validated HTTP body
plus the path's ``actor_id``, and the addressed actor's own store
(TRIG-06-001).

See also: ``core/ports/dispatcher.py`` (the received-side twin),
``core/trigger_dispatcher.py`` (the registry-backed implementation) and
``vultron/core/ports/AGENTS.md``.
"""

from typing import Protocol

from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.use_cases.triggers.requests import ResultT_co, TriggerRequest


class TriggerDispatcher(Protocol):
    """Driving port: run one trigger request and return its typed result.

    The implementation resolves the request's type to its registry row,
    constructs the row's use case as ``(dl, request, **ports)`` with the
    driven ports it needs, calls ``execute()`` and returns the result, which
    is an instance of the row's ``result_type`` — the same type the request
    binds, so ``ResultT_co`` resolves per verb at the call site.

    Domain failures propagate as bare ``VultronError`` subclasses (and
    pydantic ``ValidationError``); the adapter translates them
    (``domain_error_translation()``).  Scheduling the outbox flush is the
    adapter's job, after this method returns (TRIG-07-001).
    """

    def trigger(
        self,
        request: TriggerRequest[ResultT_co],
        dl: CaseOutboxPersistence,
    ) -> ResultT_co: ...
