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

"""Name-level source scans for the "no wire counterpart lookup" ratchets.

Shared by the render-adapter and trigger-adapter ratchets, so the set of names
that constitute a class-name counterpart lookup lives in one place (ARCH-23-001,
ISSUE-3694).

The scan sees direct name references only: a registry reached by string
(``getattr(reg, "VOCABULARY")``), through ``import *``, or through a helper
outside the scanned modules is not caught.
"""

import ast
import importlib
import inspect
import pkgutil
from types import ModuleType

#: Every name a class-name counterpart lookup needs: the four type registries,
#: their lookup functions, and the wire base whose ``from_core`` the removed
#: fallback called.
REGISTRY_LOOKUP_NAMES: frozenset[str] = frozenset(
    {
        "VOCABULARY",
        "WIRE_TYPE_MAP",
        "CORE_VOCABULARY",
        "CORE_TYPE_MAP",
        "find_in_vocabulary",
        "find_in_core_vocabulary",
        "find_in_core_type_map",
        "as_VultronObject",
    }
)


def referenced_names(module: ModuleType) -> set[str]:
    """Return every name, attribute, and imported name in *module*'s source.

    Import aliases contribute the imported name, so ``import x as y`` is
    reported as ``x``.
    """
    names: set[str] = set()
    for node in ast.walk(ast.parse(inspect.getsource(module))):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.alias):
            names.add(node.name.rsplit(".", 1)[-1])
    return names


def package_modules(package: ModuleType) -> list[ModuleType]:
    """Return *package* and every module beneath it, recursively."""
    return [package] + [
        importlib.import_module(info.name)
        for info in pkgutil.walk_packages(
            package.__path__, package.__name__ + "."
        )
    ]
