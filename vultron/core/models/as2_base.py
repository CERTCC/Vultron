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

"""The registry of core's AS2 base classes (ADR-0208).

Core owns the AS2 base vocabulary: a class registered here is an AS2 type as
the Activity Vocabulary defines it, with no Vultron field and nothing
required that AS2 does not require, so core and the wire can both build on
it.  The conformance check reads this registry, so a base class added later
is checked without a list to update.
"""

from pydantic import BaseModel

#: Every core class that is an AS2 base type, in definition order.
AS2_BASE_CLASSES: list[type[BaseModel]] = []


def as2_base_class[M: type[BaseModel]](cls: M) -> M:
    """Register *cls* as one of core's AS2 base classes (ADR-0208)."""
    AS2_BASE_CLASSES.append(cls)
    return cls


__all__ = ["AS2_BASE_CLASSES", "as2_base_class"]
