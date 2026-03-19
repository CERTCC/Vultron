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
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""
Wire-layer object rehydration utilities.

``rehydrate`` converts a loosely-typed ``as_Object`` (or a string ID reference)
into the correct wire-vocabulary subclass.  Callers that already hold a
``DataLayer`` instance SHOULD pass it via the *dl* parameter; when *dl* is
omitted the function falls back to ``get_datalayer()`` for backward
compatibility with code paths that do not have a DataLayer in scope.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import ValidationError

from vultron.adapters.driven.datalayer_tinydb import get_datalayer
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.base.registry import find_in_vocabulary

if TYPE_CHECKING:
    from vultron.core.ports.datalayer import DataLayer

logger = logging.getLogger(__name__)

MAX_REHYDRATION_DEPTH = 5


def rehydrate(
    obj: as_Object | str, dl: DataLayer | None = None, depth: int = 0
) -> as_Object | str:
    """Recursively rehydrate an object if needed.

    Performs depth-first rehydration up to ``MAX_REHYDRATION_DEPTH`` levels.

    Args:
        obj: The object (or string ID) to rehydrate.
        dl: Optional DataLayer used to resolve string ID references.  When
            *None* the function falls back to ``get_datalayer()``.
        depth: Current recursion depth (callers should not set this).

    Returns:
        The rehydrated object of the correct wire-vocabulary subclass.

    Raises:
        RecursionError: If the maximum rehydration depth is exceeded.
        ValueError: If the object cannot be found or has an invalid structure.
        KeyError: If the object type is unrecognised in the vocabulary.
        ValidationError: If Pydantic validation of the rehydrated object fails.
    """
    if depth > MAX_REHYDRATION_DEPTH:
        raise RecursionError(
            f"Maximum rehydration depth of {MAX_REHYDRATION_DEPTH} exceeded."
        )

    if isinstance(obj, str):
        if dl is not None:
            logger.debug(
                "Rehydrating string ID '%s' via provided DataLayer.", obj
            )
            resolved = dl.read(obj)
        else:
            logger.debug(
                "Rehydrating string ID '%s' via fallback get_datalayer().", obj
            )
            resolved = get_datalayer().get(id_=obj)

        if resolved is None:
            raise ValueError(f"Object '{obj}' not found in data layer")

        logger.debug("String ID '%s' resolved to %s.", obj, type(resolved))
        obj = resolved

    rehydrated_nested_object = None
    if hasattr(obj, "as_object"):
        if obj.as_object is not None:
            logger.debug("Rehydrating nested 'as_object' of %s.", obj.as_type)
            rehydrated_nested_object = rehydrate(
                obj.as_object, dl=dl, depth=depth + 1
            )
            obj.as_object = rehydrated_nested_object
        else:
            logger.error("'as_object' field is None in %s.", obj.as_type)
            raise ValueError(f"'as_object' field is None in {obj.as_type}")

    if not hasattr(obj, "as_type"):
        logger.error("Object %s has no 'as_type' attribute.", obj)
        raise ValueError(f"Object {obj} has no 'as_type' attribute.")

    cls = find_in_vocabulary(obj.as_type)
    if cls is None:
        logger.error("Unknown object type: %s.", obj.as_type)
        raise KeyError(f"Unknown object type: {obj.as_type}")

    if isinstance(obj, cls):
        logger.debug(
            "Object already rehydrated as '%s', skipping.",
            obj.__class__.__name__,
        )
        return obj

    logger.debug(
        "Rehydrating to class %s for type %s.", cls.__name__, obj.as_type
    )
    try:
        rehydrated = cls.model_validate(obj.model_dump())
    except ValidationError:
        logger.error("%s validation failed on %s.", cls.__name__, obj)
        raise

    if rehydrated_nested_object is not None and hasattr(
        rehydrated, "as_object"
    ):
        rehydrated.as_object = rehydrated_nested_object
        logger.debug(
            "Preserved rehydrated nested object of type %s.",
            rehydrated_nested_object.__class__.__name__,
        )

    return rehydrated
