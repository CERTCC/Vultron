#!/usr/bin/env python
"""
Vultron API Backend Helpers
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

from fastapi import HTTPException
from pydantic import BaseModel, ValidationError

from vultron.as_vocab.base.base import as_Base
from vultron.as_vocab.base.registry import find_in_vocabulary


def obj_from_item(item: dict) -> as_Base:
    """Create an object from a dictionary item based on its "type" field.
    Args:
        item: The dictionary representing the item.
    Returns:
        An instance of the corresponding class.
    Raises:
        HTTPException: If the item type is unknown or if validation fails.
    """

    if "type" not in item:
        raise HTTPException(
            status_code=400, detail="Item must have a 'type' field."
        )

    cls: BaseModel | None = find_in_vocabulary(item["type"])

    if cls is None:
        raise HTTPException(
            status_code=400, detail=f"Unknown item type: {item['type']}"
        )

    try:
        obj = cls.model_validate(item)
    except ValidationError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid item data: {e.errors()}"
        )

    return obj
