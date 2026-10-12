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

"""The post-close write-boundary guard of every received tree (CM-23-013).

After ``case_fully_closed`` is committed, the CASE_MANAGER behaves toward the
case as if its process had exited: an inbound activity for the case commits no
``CaseLedgerEntry`` (the receipt entry included) and changes no case or
participant state (CM-23-013, ADR-0085).

:class:`CaseOpenToExternalWritesNode` is that boundary.
:func:`~vultron.core.behaviors.case.receive_activity_tree.create_receive_activity_tree`
places it in every received tree, directly after intake, so no handler can
forget it and no handler carries its own copy (CS-22-001).  It passes on every
store that is not the case's CASE_MANAGER: a replica still applies the
closure fan-out and any later housekeeping entry the CASE_MANAGER announces.

A tree opts out only with a :class:`PostCloseExemption`, a closed set of
reasons, so an exemption is visible at its call site and in review.
"""

from enum import StrEnum

from py_trees.common import Status
from py_trees.ports import PortInformation

from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.behaviors.sync.nodes.embargo_pause import (
    sorted_case_ledger_entries,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.events import VultronEvent, resolve_case_context_id
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.predicates.case_closure import ledger_records_full_closure

__all__ = [
    "CaseOpenToExternalWritesNode",
    "PostCloseExemption",
    "case_is_fully_closed",
]


class PostCloseExemption(StrEnum):
    """Why a received tree does not carry the post-close guard.

    - ``LEDGER_RESYNC`` — the tree replays entries the ledger already holds to
      a replica that asked for them (``Reject(CaseLedgerEntry)``).  It appends
      nothing, and the CASE_MANAGER MAY keep serving resync after close
      (ADR-0085, CM-23-013).
    - ``ENCLOSING_TREE_GUARDS`` — the tree is a subtree of a received tree that
      already carries the guard, ahead of it (the close-case tree's close
      arm).
    """

    LEDGER_RESYNC = "ledger-resync"
    ENCLOSING_TREE_GUARDS = "enclosing-tree-guards"


def case_is_fully_closed(dl: CasePersistence, case_id: str) -> bool:
    """True when *dl* holds the ``case_fully_closed`` entry for *case_id*.

    Reads the store's ledger entries for the case and applies the one shared
    condition, :func:`~vultron.core.predicates.case_closure.ledger_records_full_closure`.
    Store errors propagate: "could not tell" must not admit (see
    ``notes/bt-pitfalls.md`` § "A Refusal Arm in a Selector Fails Toward
    'Admit'").
    """
    return ledger_records_full_closure(sorted_case_ledger_entries(dl, case_id))


def _candidate_case_ids(event: object) -> list[str]:
    """Case ids the received *event* may be scoped to, most specific first.

    ``case_id`` is the field of the case-object events (``Leave``, ``Update``,
    ...); the context resolution covers the case-scoped ones; ``target`` covers
    ``Add(X, target=Case)``.  Each candidate is checked against the store, so
    an id that names something other than a case is skipped.
    """
    candidates: list[object] = [getattr(event, "case_id", None)]
    if isinstance(event, VultronEvent):
        candidates.append(resolve_case_context_id(event))
        candidates.append(event.target_id)
        candidates.append(event.inner_context_id)
    return [c for c in candidates if isinstance(c, str) and c]


class CaseOpenToExternalWritesNode(DataLayerConditionWithPorts):
    """FAILURE when the executing CASE_MANAGER's case is fully closed.

    Returns:
        SUCCESS when the executing actor is not the case's CASE_MANAGER, the
        store holds no such case, no case can be resolved for the activity,
        or the case's ledger holds no ``case_fully_closed`` entry.

        FAILURE when the executing actor is the case's CASE_MANAGER and its
        ledger holds ``case_fully_closed`` (CM-23-013).  The tree then stops
        before its receipt commit and every effect; the handler reports
        ``REFUSED``.  The drop is logged at INFO with the activity id, the
        sender's actor id and the case id.

    ``case_id`` is the case the tree names.  When it is ``None`` (a tree with
    no commit stage), the case is resolved from the received activity on the
    blackboard.

    Store errors propagate rather than returning a status: either status here
    would be a guess, and only a whole-tree failure neither admits nor
    silently refuses the activity.
    """

    def __init__(self, case_id: str | None = None, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._activity: object | None = None
        self.refused_case_id: str | None = None

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def initialise(self) -> None:
        super().initialise()
        self._activity = self._try_get_input("activity")
        self.refused_case_id = None

    def _resolve_case(self) -> VulnerabilityCase | None:
        assert self.datalayer is not None
        candidates = (
            [self._case_id]
            if self._case_id
            else _candidate_case_ids(self._activity)
        )
        for case_id in candidates:
            # Regime 2 (ADR-0087): a store that holds no such case is not its
            # CASE_MANAGER, so absence passes the guard.
            case = self._resolve_case_replica(case_id)
            if case is not None:
                return case
        return None

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        case = self._resolve_case()
        if case is None:
            self.logger.debug(
                "%s: no case held for this activity; nothing to guard",
                self.name,
            )
            return Status.SUCCESS
        # Not the factory's CaseManagerGate: that gate *skips* its branch at a
        # non-manager, and this guard must instead *pass* there, so a replica
        # keeps applying the closure fan-out (CM-23-013 binds the CASE_MANAGER).
        if resolve_case_manager_id(case, self.datalayer) != self.actor_id:
            return Status.SUCCESS
        if not case_is_fully_closed(self.datalayer, case.id_):
            return Status.SUCCESS

        self.refused_case_id = case.id_
        activity_id = getattr(self._activity, "activity_id", None)
        sender_id = getattr(self._activity, "actor_id", None)
        self.feedback_message = (
            f"case '{case.id_}' is fully closed: the CASE_MANAGER records"
            " nothing after case_fully_closed (CM-23-013)"
        )
        self.logger.info(
            "%s: dropped activity_id=%s actor_id=%s for closed case '%s'"
            " (CM-23-013)",
            self.name,
            activity_id,
            sender_id,
            case.id_,
        )
        return Status.FAILURE
