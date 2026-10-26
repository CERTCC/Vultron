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

"""The one emission of a replica's fault about a refused ledger entry.

A replica that refuses a received ``Announce(CaseLedgerEntry)`` tells the
CASE_MANAGER with ``Create(ProcessingFault)`` naming that ``Announce`` by
reference (ASK-07-001, ASK-07-004, MSM-05-001).  The failure class says why:
the entry describes an impossible participant status
(``StatusAssertionRefused/ImpossibleState``, RSH-09-006), its content does not
reproduce its hash (``LedgerEntryRefused/HashMismatch``, SYNC-03-007), or the
replica's case has diverged from the CASE_MANAGER's
(``LedgerEntryRefused/CaseDiverged``, SYNC-16-001).

:func:`emit_ledger_entry_fault` is the emission every refusal path shares: an
apply node that refuses inside its own ``update()`` calls it, and
:class:`EmitLedgerEntryFaultNode` composes it as a tree's fallback.

The fault goes to the ``Announce``'s sender.  The announce tree's sender guard
admits only the case's CASE_MANAGER (SYNC-13-006, HP-01-006), so past it the
sender is the CASE_MANAGER and no one else.  Its id is derived from the
refused ``Announce`` and the failure class by the trigger-activity port, so a
retried refusal builds no second fault (ID-04-004).  The fault is replication
signalling, like ``Reject(CaseLedgerEntry)``, and nothing here commits it to a
case ledger (SYNC-16-002).
"""

from __future__ import annotations

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.sync.nodes.conditions import _require_log_entry

__all__ = ["EmitLedgerEntryFaultNode", "emit_ledger_entry_fault"]


def emit_ledger_entry_fault(
    node: DataLayerActionWithPorts, activity: object, failure_class: str
) -> bool:
    """Queue *node*'s actor's fault about the ``Announce`` *activity* carried.

    *activity* is the received ``Announce(CaseLedgerEntry)`` event.  The fault
    names it by its id and goes to its sender, the CASE_MANAGER past the
    announce tree's sender guard.  Returns whether a fault was queued.  With
    no trigger-activity port, or an event naming no id or sender, nothing can
    be built: the WARNING says so and the refusal stands without its fault.
    """
    failed_id = getattr(activity, "activity_id", None)
    sender_id = getattr(activity, "actor_id", None)
    class_label = failure_class.rsplit("/", 1)[-1]
    if node.trigger_activity_factory is None or node.actor_id is None:
        node.logger.warning(
            "%s: no trigger-activity port or actor id — ProcessingFault/%s"
            " not emitted for refused announce '%s'",
            node.name,
            class_label,
            failed_id,
        )
        return False
    if not failed_id or not sender_id:
        node.logger.warning(
            "%s: the refused announce names no id or sender —"
            " ProcessingFault/%s not emitted",
            node.name,
            class_label,
        )
        return False
    entry = _require_log_entry(activity, node.name)
    node.trigger_activity_factory.emit_processing_fault(
        actor=node.actor_id,
        failed_activity_id=failed_id,
        failure_class=failure_class,
        to=[sender_id],
        case_id=entry.case_id,
    )
    node.logger.info(
        "%s: emitted ProcessingFault/%s to the CASE_MANAGER '%s' for refused"
        " announce '%s' of ledger entry '%s' (case '%s')",
        node.name,
        class_label,
        sender_id,
        failed_id,
        entry.id_,
        entry.case_id,
    )
    return True


class EmitLedgerEntryFaultNode(DataLayerActionWithPorts):
    """Fallback that emits the refusal's fault, then returns FAILURE.

    Sits behind the check or apply node that refuses the entry, in a
    Selector, so either that node succeeds or the fault is emitted
    (:func:`emit_ledger_entry_fault`).  It returns FAILURE whether or not a
    fault was queued, so the Selector still fails and the refused entry is
    not persisted (SYNC-12-001).
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def __init__(self, failure_class: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.failure_class = failure_class

    def initialise(self) -> None:
        super().initialise()
        self.activity = self.get_input("activity")

    def update(self) -> Status:
        emit_ledger_entry_fault(self, self.activity, self.failure_class)
        return Status.FAILURE
