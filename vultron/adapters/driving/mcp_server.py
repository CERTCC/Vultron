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

"""MCP server driving adapter — **unimplemented stub**.

Nothing here works, and nothing imports it. The intent is only the
placeholder ambition "someday the Vultron service should speak MCP (Model
Context Protocol) so that coordination agents can drive trigger use cases as
tools". No design work has been done: no transport, no tool schemas, no
authentication, and no answer to the question below.

Per OX-10-004 / OX-11-004 this raises :class:`NotImplementedError` rather than
being a docstring-only stub, so the gap is loud instead of silent.

Design work is tracked on **issue #426 (AGENTIC-00)**. (An earlier version of
this module pointed at ``plan/PRIORITIES.md`` PRIORITY 1000; that file has since
been retired, which is itself a fair indication of how long this has sat.)

**The open question, recorded so it is not rediscovered.** An MCP server has no
request path to carry an actor identity, so unlike the HTTP adapter it cannot
derive one per call from ``{actor_id}``. Under ADR-0073 every DataLayer belongs
to exactly one actor, so an MCP implementation MUST decide how a tool call
selects its actor before it can touch persistence at all. At least three
options, none evaluated:

1. The server is bound to one actor at startup (a flag or config value), so
   every tool call acts as that actor.
2. Each tool takes an ``actor_id`` argument and the server opens that actor's
   store per call — mirroring the HTTP routes.
3. The server hosts a session concept that binds an actor for a run of calls.

The previous revision of this module leaned toward (2) — every tool function
accepted ``actor_id`` — but then called the *unscoped* ``get_datalayer()`` and
ignored it, which under ADR-0073 no longer exists. That inconsistency is the
main reason this was converted to an explicit stub rather than mechanically
migrated: migrating it would have meant inventing a decision nobody has made.
"""

from typing import Any, NoReturn

#: Trigger use cases the earlier sketch intended to expose as MCP tools.
#:
#: Names only, deliberately not callables: a list of working-looking functions
#: is what let this module appear implemented for as long as it did. Kept
#: because the *selection* is the only real design content the sketch had.
PLANNED_TOOLS: tuple[str, ...] = (
    "validate_report",
    "invalidate_report",
    "reject_report",
    "close_report",
    "engage_case",
    "defer_case",
    "propose_embargo",
    "accept_embargo",
    "reject_embargo",
    "propose_embargo_revision",
    "terminate_embargo",
)

_UNIMPLEMENTED = (
    "The Vultron MCP server adapter is an unimplemented stub. No transport, "
    "tool schema, or actor-selection model has been designed. See issue #426 "
    "(AGENTIC-00) and the module docstring in "
    "vultron/adapters/driving/mcp_server.py."
)


def serve(*_args: Any, **_kwargs: Any) -> NoReturn:
    """Entry point an MCP implementation would provide.

    Raises:
        NotImplementedError: Always (OX-10-004).
    """
    raise NotImplementedError(_UNIMPLEMENTED)


def __getattr__(name: str) -> NoReturn:
    """Fail loudly for the tool functions the previous revision defined.

    Anything reaching for ``mcp_validate_report`` and friends gets an explicit
    NotImplementedError naming the tracking issue, rather than an
    ``AttributeError`` that reads like a typo.

    Raises:
        NotImplementedError: For any ``mcp_*`` attribute.
        AttributeError: For anything else, per normal module semantics.
    """
    if name.startswith("mcp_"):
        raise NotImplementedError(f"{_UNIMPLEMENTED} (requested: {name!r})")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
