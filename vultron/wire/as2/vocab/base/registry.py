#!/usr/bin/env python
"""
Provides a registry for the Vultron ActivityStreams Vocabulary.
"""

#  Copyright (c) 2025 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

from pydantic import BaseModel

from vultron.core.models.registry import find_in_core_type_map

VOCABULARY: dict[str, type[BaseModel]] = {}

WIRE_TYPE_MAP: dict[str, type[BaseModel]] = {}


def find_in_vocabulary(item_name: str) -> type[BaseModel]:
    """Find a class in the vocabulary by type name.

    Checks ``WIRE_TYPE_MAP`` (keyed by wire ``type_`` value) first, then
    ``VOCABULARY`` (keyed by full wire class name), then falls back to the
    core ``CORE_TYPE_MAP`` (via :func:`find_in_core_type_map`) for types
    that belong to the core domain layer (ARCH-12-003).

    Args:
        item_name: The name of the type to find.
    Returns:
        The class registered under that name.
    Raises:
        KeyError: If the type name is not registered in either vocabulary.
    """
    if item_name in WIRE_TYPE_MAP:
        return WIRE_TYPE_MAP[item_name]
    if item_name in VOCABULARY:
        return VOCABULARY[item_name]
    try:
        return find_in_core_type_map(item_name)
    except KeyError:
        pass
    raise KeyError(f"Unknown vocabulary type: {item_name!r}")


def main():
    pass


if __name__ == "__main__":
    main()
