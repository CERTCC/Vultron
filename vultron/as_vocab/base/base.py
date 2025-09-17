#!/usr/bin/env python
"""This module provides a base class for Vultron Activity Stream classes."""
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


from typing import Optional

from pydantic import BaseModel, Field

from vultron.as_vocab.base.utils import exclude_if_none, generate_new_id


class as_Base(BaseModel):
    as_context: str = Field(
        default="https://www.w3.org/ns/activitystreams",
        alias="@context",
        exclude=True,
    )
    as_type: str = Field(default=None, alias="type", exclude=True)
    as_id: str = Field(default_factory=generate_new_id, alias="id")
    name: Optional[str] = Field(default=None, exclude=exclude_if_none)
    preview: Optional[str] = Field(default=None, exclude=exclude_if_none)
    mediaType: Optional[str] = Field(default=None, exclude=exclude_if_none)

    def __init__(self, **data):
        super().__init__(**data)
        if self.as_type is None:
            self.as_type = self.__class__.__name__.lstrip("as_")

    class Config:
        validate_by_name = True
        alias_generator = None
        json_encoders = {}


if __name__ == "__main__":
    obj = as_Base(
        name="example",
        preview="example preview",
        mediaType="text/plain",
        as_type="Test",
    )
    print(obj.model_dump_json(indent=2))
