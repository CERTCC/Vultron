#!/usr/bin/env python
"""
Provides utilities for the ActivityStreams Vocabulary.
"""
#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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

import uuid
from typing import Any


def name_of(obj: Any) -> str:
    """Get the name of an object if it has one, otherwise return the object itself

    Args:
        obj: The object to get the name of

    Returns:
        Either the name of the object or the object itself
    """

    try:
        return str(obj.name)
    except AttributeError:
        return str(obj)


def exclude_if_none(value: Any) -> bool:
    """Exclude a field if it is None

    Args:
        value: The value to check

    Returns:
        True if the value is None, False otherwise
    """
    return value is None


def exclude_if_empty(value: Any) -> bool:
    """Exclude a field if it is empty

    Args:
        value: The value to check

    Returns:
        True if the value is empty, False otherwise
    """
    return len(value) == 0


def generate_new_id(prefix: str | None = None) -> str:
    """Generate a new ID for an object

    Returns:
        the new ID
    """
    _id = str(uuid.uuid4())
    if prefix is not None:
        _id = f"{prefix}/{_id}"

    return _id


def _print_examples(d) -> None:
    """Print out empty examples of the classes in the given dictionary"""

    for k, v in d.items():
        print(f"Example of {k}:")
        # instantiate the class and print it out
        print(v().to_json(indent=2))
        print()


def print_object_examples() -> None:
    """Print out empty examples of the classes in the given module"""
    from vultron.as_vocab import VOCABULARY

    object_types = VOCABULARY.objects
    _print_examples(object_types)


def print_activity_examples():
    """Print out empty examples of the classes in the given module"""
    from vultron.as_vocab import VOCABULARY

    activity_types = VOCABULARY.activities
    _print_examples(activity_types)


def print_link_examples():
    """Print out empty examples of the classes in the given module"""
    from vultron.as_vocab import VOCABULARY

    link_types = VOCABULARY.links
    _print_examples(link_types)
