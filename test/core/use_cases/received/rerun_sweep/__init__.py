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

"""Scenario builders for the re-run-from-holding sweep (ADR-0154, #5047).

Each routed :class:`~vultron.core.models.events.base.MessageSemantics` has one
builder that sets up a store and a received event whose first run reaches its
handling tree's effects (:data:`APPLIED`), and each tree with refusal effects
has one builder whose first run is refused at the CASE_MANAGER and reaches
those effects (:data:`REFUSED`).  A semantic whose use case builds no tree is
declared in :data:`NO_TREE` with its reason.

``test_rerun_from_holding_sweep.py`` derives its subjects from
``use_case_map()`` and refuses to collect when a routed semantic has neither a
builder nor a declared reason, so a new or renamed semantic cannot slip out
of the sweep.

A builder is registered with :func:`applied` or :func:`refused`.  It returns a
:class:`Scenario`: the receiver's store and the event, as the inbox would
dispatch it.  Its first run must change what the store committed or queued;
a tree whose effect is a state write alone names a ``reached`` check.
"""

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from test.support.ledger_rebuild import run_use_case
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.use_case_result import HandlerDisposition


@dataclass(frozen=True)
class Scenario:
    """One received event, ready to run against its receiver's store.

    Attributes:
        dl: The receiver's store, set up so the first run reaches the
            tree's effects.
        event: The received event, as the inbox extracts it.
        reached: For a tree whose first run commits and queues nothing (a
            replica's state write), a check that its effect happened.
            Returns a failure message, or ``None`` when the effect is there.
        disposition: The first run's verdict.  A builder registered with
            :func:`applied` expects ``APPLIED`` unless its tree's effect is
            a refusal's own record (a dead letter).
        run: How one delivery is run; the default runs the use case as the
            inbox composes it.
    """

    dl: SqliteDataLayer
    event: Any
    reached: Callable[[SqliteDataLayer], str | None] | None = None
    disposition: HandlerDisposition = HandlerDisposition.APPLIED
    run: Callable[[SqliteDataLayer, Any], Any] = run_use_case


Builder = Callable[[], Scenario]

#: Semantic -> the builder whose first run reaches the tree's effects.
APPLIED: dict[MessageSemantics, Builder] = {}

#: Semantic -> the builder whose first run is refused at the CASE_MANAGER
#: and reaches the tree's refusal effects.
REFUSED: dict[MessageSemantics, Builder] = {}

#: Semantic -> why its use case runs no handling tree, so it has nothing to
#: re-run.  The sweep checks that it indeed runs none.
NO_TREE: dict[MessageSemantics, tuple[str, Builder]] = {}


#: Semantic -> why its tree's refusal stage can never run its effects, so it
#: has no refusal builder.  The sweep checks that the tree has the stage.
REFUSAL_UNREACHABLE: dict[MessageSemantics, str] = {
    MessageSemantics.ENGAGE_CASE: (
        "its one guard (AdjudicateRMDeclarationNode) refuses only a backward"
        " RM step, and only RM.CLOSED steps back to ACCEPTED; a CLOSED"
        " sender is refused first at the sender-guard door"
    ),
    MessageSemantics.DEFER_CASE: (
        "its one guard (AdjudicateRMDeclarationNode) refuses only a backward"
        " RM step, and only RM.CLOSED steps back to DEFERRED; a CLOSED"
        " sender is refused first at the sender-guard door"
    ),
    MessageSemantics.ADD_REPORT_TO_CASE: (
        "its one guard (CaseReferenceEditPendingNode) fails only on a repeat,"
        " which is SKIPPED with no effects, or on an unknown case, which a"
        " door refuses first"
    ),
    MessageSemantics.REMOVE_NOTE_FROM_CASE: (
        "its one guard (CaseReferenceEditPendingNode) fails only on a repeat,"
        " which is SKIPPED with no effects, or on an unknown case, which a"
        " door refuses first"
    ),
    MessageSemantics.ADD_CASE_STATUS_TO_CASE: (
        "the tree declares the participant-replica path alone, so the"
        " CASE_MANAGER, the only receiver that runs refusal effects, is"
        " refused at the path stage before the guards"
    ),
}


def _register(
    table: dict[MessageSemantics, Builder], semantic: MessageSemantics
) -> Callable[[Builder], Builder]:
    def _decorate(builder: Builder) -> Builder:
        if semantic in table:
            raise ValueError(
                f"{semantic.value}: a second builder"
                f" {builder.__qualname__}; keep one per semantic"
            )
        table[semantic] = builder
        return builder

    return _decorate


def applied(semantic: MessageSemantics) -> Callable[[Builder], Builder]:
    """Register *builder* as *semantic*'s scenario that reaches its effects."""
    return _register(APPLIED, semantic)


def refused(semantic: MessageSemantics) -> Callable[[Builder], Builder]:
    """Register *builder* as *semantic*'s refusal scenario."""
    return _register(REFUSED, semantic)


def no_tree(
    semantic: MessageSemantics, reason: str
) -> Callable[[Builder], Builder]:
    """Declare that *semantic* runs no tree, with a delivery that shows it."""

    def _decorate(builder: Builder) -> Builder:
        if semantic in NO_TREE:
            raise ValueError(f"{semantic.value}: declared twice")
        NO_TREE[semantic] = (reason, builder)
        return builder

    return _decorate


#: The builder modules, one per area; importing each registers its builders.
_MODULES = (
    "report",
    "case",
    "actor",
    "ownership",
    "invite",
    "embargo",
    "sync",
    "misc",
)

for _module in _MODULES:
    importlib.import_module(f"{__name__}.{_module}")


__all__ = [
    "APPLIED",
    "NO_TREE",
    "REFUSAL_UNREACHABLE",
    "REFUSED",
    "Builder",
    "Scenario",
    "applied",
    "no_tree",
    "refused",
]
