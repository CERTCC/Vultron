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
"""Architecture ratchet: every typed-ports BT node declares its ports as
``INPUT_PORTS`` / ``OUTPUT_PORTS`` class attributes.

py_trees 2.6.0 replaced the overridable ``input_ports()`` / ``output_ports()``
classmethods with class attributes, and treats a ``PortsMixin`` subclass
that lacks them as abstract — instantiating it raises ``TypeError``. The
bump reached ``main`` with every such node still overriding the
classmethods, so no behavior tree could be built (#3610).

Two checks per class:

1. py_trees' own abstract-class predicate says the class is concrete, so
   it can be instantiated.
2. The class does not override ``input_ports`` / ``output_ports``: an
   override would shadow the attribute and give the node two sources of
   truth that can drift apart.

Spec: BTND-03-009 (``specs/behavior-tree-node-design.yaml``).
"""

import importlib
import pkgutil

import pytest
from py_trees.ports import PortsMixin, _ports_class_is_abstract

import vultron.core.behaviors

_OLD_ACCESSORS = ("input_ports", "output_ports")


def _import_all_behavior_modules() -> None:
    for info in pkgutil.walk_packages(
        vultron.core.behaviors.__path__, "vultron.core.behaviors."
    ):
        importlib.import_module(info.name)


def _vultron_ports_classes() -> list[type]:
    _import_all_behavior_modules()
    found: list[type] = []
    pending = list(PortsMixin.__subclasses__())
    while pending:
        cls = pending.pop()
        pending.extend(cls.__subclasses__())
        if cls.__module__.startswith("vultron.") and cls not in found:
            found.append(cls)
    return sorted(found, key=lambda c: f"{c.__module__}.{c.__qualname__}")


@pytest.mark.spec("BTND-03-009")
def test_ports_classes_are_discovered() -> None:
    # Guards the two checks below against passing vacuously.
    assert len(_vultron_ports_classes()) > 100


@pytest.mark.spec("BTND-03-009")
def test_every_ports_node_declares_class_attribute_ports() -> None:
    abstract = [
        f"{c.__module__}.{c.__qualname__}"
        for c in _vultron_ports_classes()
        if _ports_class_is_abstract(c)
    ]
    assert abstract == [], (
        f"{len(abstract)} typed-ports class(es) lack INPUT_PORTS / "
        "OUTPUT_PORTS and cannot be instantiated under py_trees >= 2.6:\n  "
        + "\n  ".join(abstract)
    )


@pytest.mark.spec("BTND-03-009")
def test_no_ports_node_overrides_the_port_accessors() -> None:
    overriding = [
        f"{c.__module__}.{c.__qualname__}.{name}"
        for c in _vultron_ports_classes()
        for name in _OLD_ACCESSORS
        if name in c.__dict__
    ]
    assert overriding == [], (
        "Declare ports as INPUT_PORTS / OUTPUT_PORTS class attributes, not "
        "by overriding the accessor classmethods:\n  "
        + "\n  ".join(overriding)
    )
