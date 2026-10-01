"""Verb-keyed trigger registry for the Vultron Protocol (ADR-0110).

``TRIGGER_REGISTRY`` is the single source mapping each trigger verb — the
final path segment of its route — to the data every consumer of the verb
reads (TRIG-12-004):

- ``request_model`` — the core ``TriggerRequest`` subclass the route builds
- ``use_case_class`` — the ``Svc*UseCase`` the dispatcher constructs
- ``result_type`` — the ``TriggerResult`` subtype it returns
- ``exposure`` — general-purpose (``/trigger/``) or demo-only (``/demo/``)
- ``bt_backed`` — whether it runs a behavior tree via ``SvcBTTriggerBase``
- ``spec_ids`` — the requirements the verb implements

The registry exists for **enumeration, not routing**: a route already knows
its verb.  What needs a table to iterate is the set of properties that were
otherwise asserted by inspection — the route-to-row and use-case-to-row
bijections, the exposure axis, the single non-BT-backed row and each verb's
exact response keys — which the ratchets under ``test/architecture/`` and the
route tests now read off these rows.  The
:class:`~vultron.core.trigger_dispatcher.RegistryTriggerDispatcher` resolves a
request to its row through :func:`index_by_request_model`.

It is a data table with a lookup.  It MUST NOT acquire per-verb behavior; a
method per verb here would be the facade ADR-0110 removed under a new name.

Mirrors ``vultron/semantic_registry/``: each domain sub-module (``report``,
``case``, ``embargo``, ``actor``, ``note``, ``status``, ``sync``) exports an
``ENTRIES`` list and this ``__init__`` assembles them.  Order carries no
meaning — verbs are looked up, never pattern-matched.  Importable by core,
adapter and test code; it imports only core.

Public API
----------
``TriggerEntry`` — frozen dataclass holding one verb's data
``TriggerExposure`` — ``StrEnum``: general-purpose / demo-only
``TRIGGER_REGISTRY`` — the assembled rows
``entries()`` — enumeration: every row, in assembly order
``lookup_entry(verb)`` — lookup: the row for a verb
``index_by_request_model(rows)`` — lookup: rows keyed by request model
"""

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

from vultron.errors import TriggerRegistryError, VultronApiHandlerNotFoundError
from vultron.trigger_registry._entry import (
    GENERAL_TRIGGER_SPECS,
    TriggerEntry,
    TriggerExposure,
    _iter_duplicate_verbs,
    index_by_request_model,
)

from . import actor, case, embargo, note, report, status, sync

TRIGGER_REGISTRY: tuple[TriggerEntry, ...] = tuple(
    report.ENTRIES
    + case.ENTRIES
    + embargo.ENTRIES
    + actor.ENTRIES
    + note.ENTRIES
    + status.ENTRIES
    + sync.ENTRIES
)

# ---------------------------------------------------------------------------
# Import-time integrity: a verb names one row, and a request model resolves
# to one use case.  Both fail here so a bad row is impossible to miss.
# ---------------------------------------------------------------------------

_duplicates = sorted(set(_iter_duplicate_verbs(TRIGGER_REGISTRY)))
if _duplicates:
    raise TriggerRegistryError(
        f"trigger verbs registered more than once: {_duplicates}"
    )

_BY_VERB: dict[str, TriggerEntry] = {e.verb: e for e in TRIGGER_REGISTRY}

# Raises ``TriggerRegistryError`` on a shared request model whose rows
# disagree; the result is discarded because the dispatcher builds its own
# index from the rows it is given.
index_by_request_model(TRIGGER_REGISTRY)


def entries() -> tuple[TriggerEntry, ...]:
    """Every registry row, in assembly order (the enumeration function)."""
    return TRIGGER_REGISTRY


def lookup_entry(verb: str) -> TriggerEntry:
    """Return the row for *verb* (the lookup function).

    Raises:
        VultronApiHandlerNotFoundError: *verb* names no registered trigger.
            A verb is a path segment the caller already holds, so an unknown
            one is a caller fault, not an unknown activity to fall back on;
            the received-side dispatcher raises the same error for an
            unregistered semantics.
    """
    try:
        return _BY_VERB[verb]
    except KeyError:
        raise VultronApiHandlerNotFoundError(
            f"no trigger registry row for verb {verb!r}"
        ) from None


__all__ = [
    "GENERAL_TRIGGER_SPECS",
    "TRIGGER_REGISTRY",
    "TriggerEntry",
    "TriggerExposure",
    "entries",
    "index_by_request_model",
    "lookup_entry",
]
