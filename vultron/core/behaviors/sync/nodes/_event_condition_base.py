#!/usr/bin/env python
#
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
"""Shared bases of the semantic-type matcher condition nodes (BTND-08-001).

Each ``Is*EventNode`` reads the ``CaseLedgerEntry`` on the blackboard
``activity`` port and matches its ``semantic_type``; split out of
``event_conditions`` so the embargo matchers can live in a module of their
own (BTND-07-004).
"""

from __future__ import annotations

from typing import Any, ClassVar

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.behaviors.sync.nodes.conditions import _require_log_entry


class _ActivityEventNode(DataLayerConditionWithPorts):
    """Common base for Is*EventNode classes that read activity from a port."""

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
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


class _SemanticTypeSetNode(_ActivityEventNode):
    """Base for an ``Is*EventNode`` that matches a set of ``semantic_type`` values.

    A subclass sets :attr:`matched_semantic_types`; the node returns SUCCESS iff
    the entry's ``semantic_type`` is a member (BTND-08-001, SYNC-12-001).
    """

    matched_semantic_types: ClassVar[frozenset[str]]

    def update(self) -> Status:
        entry = _require_log_entry(self.activity, self.name)
        if entry.semantic_type in self.matched_semantic_types:
            return Status.SUCCESS
        return Status.FAILURE


class _SingleSemanticTypeNode(_SemanticTypeSetNode):
    """Base for an ``Is*EventNode`` that matches exactly one ``semantic_type``.

    A subclass sets :attr:`matched_semantic_type`; the node returns SUCCESS iff
    the entry's ``semantic_type`` equals it (BTND-08-001, SYNC-12-001).
    """

    matched_semantic_type: ClassVar[str]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if "matched_semantic_type" in cls.__dict__:
            cls.matched_semantic_types = frozenset({cls.matched_semantic_type})


__all__ = [
    "_ActivityEventNode",
    "_SemanticTypeSetNode",
    "_SingleSemanticTypeNode",
]
