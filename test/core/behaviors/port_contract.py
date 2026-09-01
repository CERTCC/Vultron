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

"""Reflective discovery of typed-Ports declarations for contract tests.

A blackboard key is a contract between the node that writes it and every node
that reads it, and py_trees enforces that contract only as strongly as the
weakest ``data_type`` on either side (a single ``data_type=object`` reader
accepts anything). A hard-coded roster of node classes cannot police that: a
node added later with the permissive declaration re-opens the hole while the
suite stays green.

These helpers walk a behaviors package and return every leaf node class that
declares a given port, so a contract test parametrizes over what the package
*actually contains*.

Used by the ``participant_case`` (#2907) and ``log_entry`` / ``replay_entry``
contract tests. Supports BTND-03-009.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from types import ModuleType
from typing import Iterable, Iterator

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
)


def iter_port_node_classes(package: ModuleType) -> Iterator[type]:
    """Yield every typed-Ports leaf node class defined under ``package``.

    The walk is **recursive** (``pkgutil.walk_packages``): a node module that
    is later split into a subpackage — the normal response to the BTND-07-004
    line cap — keeps its nodes in the roster instead of silently dropping them
    and leaving a parametrized contract test looking green over nothing.

    A class is yielded by the module that *defines* it (``__module__`` match),
    so a re-export does not produce a second entry. Node classes are expected
    to live in modules rather than in a package's ``__init__.py``, which
    BTND-07-003 reserves for re-exports.

    Args:
        package: An imported package whose modules declare BT leaf nodes.

    Yields:
        Leaf node classes deriving from the typed-Ports DataLayer bases.
    """
    for mod_info in pkgutil.walk_packages(
        package.__path__, prefix=f"{package.__name__}."
    ):
        module = importlib.import_module(mod_info.name)
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ != module.__name__:
                continue
            if issubclass(
                obj, (DataLayerActionWithPorts, DataLayerConditionWithPorts)
            ):
                yield obj


#: One discovered declaration: the node class and the logical port name.
PortDecl = tuple[type, str]


def discover_port_declarations(
    package: ModuleType, ports: Iterable[str]
) -> tuple[list[PortDecl], list[PortDecl]]:
    """Return (input, output) declarations of ``ports`` among ``package``.

    Each entry names both the class and the port, so a node declaring more
    than one of ``ports`` contributes one entry per port. Returning bare
    classes instead would force the caller to guess which port to inspect, and
    a node carrying two of them would have one declaration go unchecked.

    Args:
        package: An imported behaviors package to scan.
        ports: Logical port names (e.g. ``{"log_entry", "replay_entry"}``).

    Returns:
        Two lists of ``(node_cls, port)``, each sorted by class name then port:
        declarations that appear as an input port, and as an output port. A
        node that both reads and writes a port appears in both lists.
    """
    wanted = set(ports)
    inputs: list[PortDecl] = []
    outputs: list[PortDecl] = []
    for node_cls in iter_port_node_classes(package):
        for port in wanted & set(node_cls.input_ports()):  # type: ignore[attr-defined]
            inputs.append((node_cls, port))
        for port in wanted & set(node_cls.output_ports()):  # type: ignore[attr-defined]
            outputs.append((node_cls, port))
    key = lambda decl: (decl[0].__name__, decl[1])  # noqa: E731
    return sorted(inputs, key=key), sorted(outputs, key=key)


def decl_id(decl: PortDecl) -> str:
    """Return a pytest parametrize id for a discovered declaration."""
    node_cls, port = decl
    return f"{node_cls.__name__}.{port}"
