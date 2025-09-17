#!/usr/bin/env python
"""This module provides
# TODO replace me
"""
#  Copyright (c) 2023 Carnegie Mellon University and Contributors.
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


from enum import Enum
from typing import Iterable


def enum_list_to_string_list(enum_iter: Iterable) -> list:
    """Converts an iterator of enums to a list of strings

    Args:
        enum_iter: an iterator of enums

    Returns:
        a list of strings
    """
    return [str(x) for x in enum_iter]


def enum_item_in_list(item: Enum, enum_iter: Iterable) -> bool:
    """Checks if an enum item is in a list of enum items
    Avoids the problem of comparing enums from different enums

    Args:
        item: an enum item
        enum_iter: a list of enum items

    Returns:

    """
    # the lists may contain the same integer value from different enums
    # so we can't use the in operator

    # the lists may also contain the same string value from different enums
    # so we cant compare the name attributes either

    # instead we can convert them to strings and compare the strings
    # this is a helper function to do that
    return str(item) in enum_list_to_string_list(enum_iter)


def uniq_enum_iter(enum_iter: Iterable) -> Iterable:
    """Returns an iterator of unique enums from an iterator of enums

    Args:
        enum_iter: an iterator of enums, can be from different enums

    Returns:
        an iterator of unique enums
    """
    seen = set()
    for item in enum_iter:
        item_str = str(item)
        if item_str not in seen:
            yield item
            seen.add(item_str)


def unique_enum_list(enum_iter: Iterable) -> list:
    """Returns a list of unique enums from a list of enums

    Args:
        enum_iter: a list of enums, can be from different enums

    Returns:
        a list of unique enums
    """
    return list(uniq_enum_iter(enum_iter))


def enum2title(enum_item: Enum) -> str:
    """Converts an enum item to a title string

    Args:
        enum_item: an enum item

    Returns:
        a title string
    """
    return enum_item.name.replace("_", " ").title()
