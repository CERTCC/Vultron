#!/usr/bin/env python
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
"""Provides Utility functions for the as_vocab.base.objects module"""

import logging

from vultron.as_vocab.base import VOCABULARY
from vultron.as_vocab.base.base import as_Base
from vultron.as_vocab.base.errors import (
    MissingTypeError,
    UnrecognizedTypeError,
)

logger = logging.getLogger(__name__)


def simple_object_from_dict(data: dict) -> as_Base:
    """
    Get the object from the given json data

    Args:
        data: the json data

    Returns:
        the object

    Raises:
        MissingTypeError: if the type is missing
        UnrecognizedTypeError: if the type is not recognized
    """
    try:
        obj_type = data["type"]
    except KeyError:
        logger.warning("Object type is missing in message")
        raise MissingTypeError("Missing type")

    # find the class that matches the type
    obj_cls = None

    for kind, classes in VOCABULARY.items():
        # ensure classes is not empty
        assert classes, f"Empty {kind} in vocabulary"

        logger.debug(f"Looking for {obj_type} in {kind}: {classes}")
        if obj_type in classes:
            obj_cls = classes[obj_type]
            # found it, we're done
            break

    if obj_cls is None:
        logger.warning(f"Unknown type: {obj_type}")
        raise UnrecognizedTypeError(f"Unrecognized object type")

    obj = obj_cls.from_dict(data, infer_missing=True)

    return obj


def object_from_dict(data: dict) -> as_Base:
    """Create an object from the given json data.
    Figures out the type and creates the appropriate object.

    Args:
        data: the json data

    Returns:
        an object that is a subclass of as_Base

    Raises:
        MissingTypeError: if the type is missing
        UnrecognizedTypeError: if the type is not recognized
        UnrecognizedTypeError: if the type of any sub-object is not
            recognized
    """
    obj = simple_object_from_dict(data)

    # todo should this be recursive instead?
    for attrib in ["actor", "as_object", "target", "origin"]:
        if hasattr(obj, attrib):
            data = getattr(obj, attrib)
            parsed = parse_sub_object(data)
            setattr(obj, attrib, parsed)

    return obj


def parse_sub_object(data) -> as_Base | str:
    if isinstance(data, dict):
        # we need to convert this to an object
        return simple_object_from_dict(data)

    if isinstance(data, str) or data is None:
        # we can live with this
        # it's either a string or None, which is fine
        return data

    # we don't know what this is
    logger.warning(f"Unknown type for as_object: {type(data)}")
    raise UnrecognizedTypeError("Unknown type for as_object")
