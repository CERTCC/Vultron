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
"""Read which scenario modules a source tree imports by name.

Shared by the two ratchets that forbid a hand-written scenario import list:
the registry's (DEMOCI-11-038) and the CLI's (DEMOCI-11-044).  One predicate,
so a scenario that is a ``<name_>_demo/`` package (DEMOCI-11-003) is named by
an import of any of its submodules in both places.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable

from vultron.demo.scenario.registry import MODULE_SUFFIX, SCENARIO_PACKAGE


def imported_names(nodes: Iterable[ast.AST]) -> list[str]:
    """Every dotted name *nodes* import.

    ``from <pkg> import <name>`` yields both ``<pkg>`` and ``<pkg>.<name>``,
    so ``from vultron.demo.scenario import rv_demo`` names ``rv_demo``.
    """
    imported: list[str] = []
    for node in nodes:
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
            imported.extend(
                f"{node.module}.{alias.name}" for alias in node.names
            )
    return imported


def names_a_scenario(name: str) -> bool:
    """Whether the dotted *name* is a scenario module or one of its submodules.

    Importing ``<pkg>.rcvcv_demo.cli`` names the scenario as surely as
    ``<pkg>.rcvcv_demo``; a ``*_demo`` module outside the scenario package,
    such as an exchange demo, is not a scenario.
    """
    prefix = f"{SCENARIO_PACKAGE}."
    if not name.startswith(prefix):
        return False
    return any(
        part.endswith(MODULE_SUFFIX)
        for part in name.removeprefix(prefix).split(".")
    )
