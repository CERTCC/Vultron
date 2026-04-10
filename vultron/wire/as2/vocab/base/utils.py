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

URN_UUID_PREFIX = "urn:uuid:"


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
    """Generate a new URI-form ID for an object.

    Returns a ``urn:uuid:`` URI by default, which is a valid AS2 identifier
    and requires no HTTP server configuration. When a *prefix* is supplied the
    UUID is appended to it with a ``/`` separator, allowing callers to produce
    HTTPS-style identifiers (e.g. ``https://example.org/reports/{uuid}``).

    Returns:
        a URI-form ID string
    """
    _uuid = str(uuid.uuid4())
    if prefix is not None:
        _id = f"{prefix}/{_uuid}"
    else:
        _id = f"{URN_UUID_PREFIX}{_uuid}"

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
    from vultron.wire.as2.vocab import VOCABULARY

    _print_examples(VOCABULARY)


def print_activity_examples():
    """Print out empty examples of the classes in the given module"""
    from vultron.wire.as2.vocab import VOCABULARY

    _print_examples(VOCABULARY)


def print_link_examples():
    """Print out empty examples of the classes in the given module"""
    from vultron.wire.as2.vocab import VOCABULARY

    _print_examples(VOCABULARY)
