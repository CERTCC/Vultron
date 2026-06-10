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

"""Registry for the Vultron core domain object hierarchy.

This is the domain-layer analog of
:mod:`vultron.wire.as2.vocab.base.registry`.  Concrete subclasses of
:class:`vultron.core.models.base.CoreObject` register themselves here via
``__init_subclass__`` so that downstream code (e.g. discriminated-union
construction, future migrations) can discover the full set of domain
object types without per-type manual wiring.

The registry value type is ``type[BaseModel]`` rather than
``type[CoreObject]`` to keep this module import-cycle free —
``base.py`` imports from this module.
"""

from pydantic import BaseModel

CORE_VOCABULARY: dict[str, type[BaseModel]] = {}


def find_in_core_vocabulary(item_name: str) -> type[BaseModel]:
    """Find a class in the core vocabulary by type name.

    Args:
        item_name: The name of the type to find.
    Returns:
        The class registered under that name.
    Raises:
        KeyError: If the type name is not registered.
    """
    if item_name not in CORE_VOCABULARY:
        raise KeyError(f"Unknown core vocabulary type: {item_name!r}")
    return CORE_VOCABULARY[item_name]
