#!/usr/bin/env python

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

"""
Provides Object Rehydration Utilities for Vultron.
"""

import logging

from pydantic import ValidationError

from vultron.api.v2.datalayer.tinydb_backend import get_datalayer
from vultron.as_vocab.base.objects.base import as_Object
from vultron.as_vocab.base.registry import find_in_vocabulary

logger = logging.getLogger(__name__)

MAX_REHYDRATION_DEPTH = 5


def rehydrate(obj: as_Object, depth: int = 0) -> as_Object | str:
    """Recursively rehydrate an object if needed. Performs depth-first rehydration to a maximum depth.

    Args:
        obj: The object to rehydrate.
        depth: The current recursion depth (default: 0).
    Returns:
        The rehydrated object of the correct subclass.
    Raises:
        KeyError: If the object type is unrecognized.
        RecursionError: If the maximum rehydration depth is exceeded.
        ValidationError: If the rehydrated object validation fails.
    """
    if depth > MAX_REHYDRATION_DEPTH:
        raise RecursionError(
            f"Maximum rehydration depth of {MAX_REHYDRATION_DEPTH} exceeded."
        )

    # short-circuit for strings
    if isinstance(obj, str):
        datalayer = get_datalayer()
        logger.debug(
            f"Attempting to rehydrate string object ID '{obj}' from data layer."
        )

        logger.debug(f"Reading object with ID '{obj}' from data layer.")
        obj = datalayer.get(id_=obj)

        if obj is None:
            raise ValueError("Object not found in data layer")

        logger.debug(f"Object rehydrated from data layer: {obj}")
        # Don't return early - continue to rehydrate nested objects

    # if object has an `as_object`, rehydrate that first
    # this is the depth-first part
    rehydrated_nested_object = None
    if hasattr(obj, "as_object"):
        if obj.as_object is not None:
            logger.debug(
                f"Rehydrating nested object in 'as_object' field of {obj.as_type}"
            )
            rehydrated_nested_object = rehydrate(
                obj=obj.as_object, depth=depth + 1
            )
            obj.as_object = rehydrated_nested_object
        else:
            logger.error(f"'as_object' field is None in {obj.as_type}")
            raise ValueError(f"'as_object' field is None in {obj.as_type}")

    # make sure the object has an as_type
    if not hasattr(obj, "as_type"):
        logger.error(f"Object {obj} has no 'as_type' attribute.")
        raise ValueError(f"Object {obj} has no 'as_type' attribute.")

    # now rehydrate the outer object if needed
    cls = find_in_vocabulary(obj.as_type)
    if cls is None:
        logger.error(f"Unknown object type: {obj.as_type}")
        raise KeyError(f"Unknown object type: {obj.as_type}")

    # short-circuit if already rehydrated
    if isinstance(obj, cls):
        logger.debug(
            f"Object already rehydrated as '{obj.__class__.__name__}', skipping rehydration step."
        )
        return obj

    # it's not the right class, re-validate to get the correct subclass
    logger.debug(f"Rehydrating to class {cls.__name__} for type {obj.as_type}")
    try:
        rehydrated = cls.model_validate(obj.model_dump())
    except ValidationError:
        logger.error(f"{cls.__name__} validation failed on {obj}")
        raise

    # Preserve the rehydrated nested object after validation
    if rehydrated_nested_object is not None and hasattr(
        rehydrated, "as_object"
    ):
        rehydrated.as_object = rehydrated_nested_object
        logger.debug(
            f"Preserved rehydrated nested object of type {rehydrated_nested_object.__class__.__name__}"
        )

    return rehydrated
