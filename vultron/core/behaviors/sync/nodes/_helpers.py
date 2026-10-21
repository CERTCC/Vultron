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

"""Shared helpers for SYNC log-replication effect nodes.

Provides the ``_extract_id_from_field`` utility, the
``hold_received_announce`` step every holding node shares, and the
``_LedgerEffectNode`` base class used by all per-semantic-type effect nodes.
"""

from __future__ import annotations

import logging
from typing import Any

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.behaviors.sync.nodes.conditions import (
    _require_log_entry,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.held_ledger_announces import hold_ledger_announce
from vultron.errors import VultronWiringError

logger = logging.getLogger(__name__)


def hold_received_announce(
    node_name: str, dl: CasePersistence, activity: object
) -> bool:
    """Hold the received ``Announce`` that carried *activity*'s ledger entry.

    Holds the ``Announce`` as it was received, never its entry alone
    (:func:`~vultron.core.services.held_ledger_announces.hold_ledger_announce`,
    SYNC-14-001).  Returns whether it is now held.

    Raises:
        VultronWiringError: When the event names no activity to hold.
    """
    entry = _require_log_entry(activity, node_name)
    activity_id = getattr(activity, "activity_id", None)
    if not isinstance(activity_id, str) or not activity_id:
        raise VultronWiringError(
            f"{node_name}: the event carrying ledger entry '{entry.id_}'"
            " names no activity to hold"
        )
    return hold_ledger_announce(dl, entry, activity_id)


def _extract_id_from_field(value: Any) -> str | None:
    """Return the string ID from an AS2 object field.

    Handles None, bare string, inline dict (``{"id": ...}`` or ``{"id_": ...}``
    form), and object instances with ``id_`` or ``id`` attributes.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        return value.get("id") or value.get("id_") or None
    return getattr(value, "id_", None) or getattr(value, "id", None) or None


class _LedgerEffectNode(DataLayerActionWithPorts, StateWriteCapable):
    """Base class for Announce(CaseLedgerEntry) received-side effect nodes.

    Declares an ``activity`` input port and exposes ``_get_entry()`` to
    retrieve the log entry without repeating the import in every subclass.

    Subclasses override only ``update()`` with their specific side-effect logic.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def initialise(self) -> None:
        super().initialise()
        try:
            self.activity = self.get_input("activity")
        except (NoDataAvailable, NotImplementedError):
            self.activity = None

    def _get_entry(self):  # type: ignore[return]
        """Return the HashChainLedgerRecord from the blackboard activity."""
        return _require_log_entry(self.activity, self.name)

    def update(self) -> Status:  # pragma: no cover
        raise NotImplementedError
