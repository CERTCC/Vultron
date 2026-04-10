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

VOCABULARY: dict[str, type[BaseModel]] = {}


def find_in_vocabulary(item_name: str) -> type[BaseModel]:
    """Find a class in the vocabulary by type name.

    Args:
        item_name: The name of the type to find.
    Returns:
        The class registered under that name.
    Raises:
        KeyError: If the type name is not registered in the vocabulary.
    """
    if item_name not in VOCABULARY:
        raise KeyError(f"Unknown vocabulary type: {item_name!r}")
    return VOCABULARY[item_name]


def main():
    pass


if __name__ == "__main__":
    main()
