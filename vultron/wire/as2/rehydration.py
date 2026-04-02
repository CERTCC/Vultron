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
into the correct wire-vocabulary subclass.  Callers MUST pass the active
``DataLayer`` instance via the *dl* parameter so that string ID references can
be resolved without importing a concrete adapter.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from pydantic import ValidationError

from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.base.registry import find_in_vocabulary

if TYPE_CHECKING:
    from vultron.core.ports.datalayer import DataLayer

logger = logging.getLogger(__name__)

MAX_REHYDRATION_DEPTH = 5


def rehydrate(
    obj: as_Object | str, dl: DataLayer, depth: int = 0
) -> as_Object:
    """Recursively rehydrate an object if needed.

    Performs depth-first rehydration up to ``MAX_REHYDRATION_DEPTH`` levels.

    Args:
        obj: The object (or string ID) to rehydrate.
        dl: DataLayer used to resolve string ID references.
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
        logger.debug("Rehydrating string ID '%s' via provided DataLayer.", obj)
        resolved = dl.read(obj)

        if resolved is None:
            raise ValueError(f"Object '{obj}' not found in data layer")

        if not isinstance(resolved, as_Object):
            raise ValueError(
                f"Object '{obj}' resolved to unsupported type "
                f"{type(resolved).__name__}"
            )

        logger.debug("String ID '%s' resolved to %s.", obj, type(resolved))
        obj = resolved

    rehydrated_nested_object = None
    if hasattr(obj, "object_"):
        obj_with_object = cast(Any, obj)
        if obj_with_object.object_ is not None:
            logger.debug("Rehydrating nested 'object_' of %s.", obj.type_)
            try:
                rehydrated_nested_object = rehydrate(
                    obj_with_object.object_, dl=dl, depth=depth + 1
                )
                obj_with_object.object_ = rehydrated_nested_object
            except ValueError:
                # Nested object not found in the local DataLayer — common in
                # federated scenarios where objects live on remote containers.
                # Keep the original ID string reference; pattern matching
                # treats string values as "conservatively allowed" (see
                # ActivityPattern._match_field), and use cases handle the
                # missing object gracefully.
                logger.debug(
                    "Could not rehydrate nested 'object_' of %s; "
                    "keeping original reference.",
                    obj.type_,
                )
        else:
            logger.error("'object_' field is None in %s.", obj.type_)
            raise ValueError(f"'object_' field is None in {obj.type_}")

    if not hasattr(obj, "type_"):
        logger.error("Object %s has no 'type_' attribute.", obj)
        raise ValueError(f"Object {obj} has no 'type_' attribute.")

    if obj.type_ is None:
        raise ValueError(f"Object {obj} has no 'type_' value.")

    cls = find_in_vocabulary(obj.type_)
    if cls is None:
        logger.error("Unknown object type: %s.", obj.type_)
        raise KeyError(f"Unknown object type: {obj.type_}")

    if isinstance(obj, cls):
        logger.debug(
            "Object already rehydrated as '%s', skipping.",
            obj.__class__.__name__,
        )
        return obj

    logger.debug(
        "Rehydrating to class %s for type %s.", cls.__name__, obj.type_
    )
    try:
        rehydrated = cls.model_validate(obj.model_dump())
    except ValidationError:
        logger.error("%s validation failed on %s.", cls.__name__, obj)
        raise

    if not isinstance(rehydrated, as_Object):
        raise ValueError(
            f"Rehydration of {obj.type_} produced unsupported type "
            f"{type(rehydrated).__name__}"
        )

    if rehydrated_nested_object is not None and hasattr(rehydrated, "object_"):
        cast(Any, rehydrated).object_ = rehydrated_nested_object
        logger.debug(
            "Preserved rehydrated nested object of type %s.",
            rehydrated_nested_object.__class__.__name__,
        )

    return cast(as_Object, rehydrated)
