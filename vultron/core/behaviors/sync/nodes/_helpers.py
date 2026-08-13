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

Provides the ``_extract_id_from_field`` utility and the
``_LedgerEffectNode`` base class used by all per-event-type effect nodes.
"""

from __future__ import annotations

import logging
from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction

logger = logging.getLogger(__name__)


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


class _LedgerEffectNode(DataLayerAction):
    """Base class for Announce(CaseLedgerEntry) received-side effect nodes.

    Registers the ``activity`` blackboard key in ``setup()`` and exposes
    ``_get_entry()`` to retrieve the log entry from the blackboard without
    repeating the import and call in every subclass.

    Subclasses override only ``update()`` with their specific side-effect logic.
    """

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )

    def _get_entry(self):  # type: ignore[return]
        """Return the HashChainLedgerRecord from the blackboard activity."""
        from vultron.core.behaviors.sync.nodes.conditions import (
            _require_log_entry,
        )

        return _require_log_entry(self.blackboard.activity, self.name)

    def update(self) -> Status:  # pragma: no cover
        raise NotImplementedError
