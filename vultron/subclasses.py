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

"""Walk a class's subclass tree.

One implementation for every enumeration of a root's subclasses — the
architecture ratchets and the JSON-LD context generator (CS-22-001) — so each
walk visits a class once however many paths reach it.
"""


def all_subclasses[T](cls: type[T]) -> set[type[T]]:
    """Every direct and indirect subclass of *cls*, excluding *cls* itself."""
    found: set[type[T]] = set()
    pending: list[type[T]] = [cls]
    while pending:
        for sub in pending.pop().__subclasses__():
            if sub not in found:
                found.add(sub)
                pending.append(sub)
    return found
