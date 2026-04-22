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

import types as _types
import typing as _typing
from typing import ClassVar

from pydantic import BaseModel, Field, model_validator, ConfigDict
from pydantic.alias_generators import to_camel

from vultron.wire.as2.vocab.base.enums import VocabNamespace
from vultron.wire.as2.vocab.base.registry import VOCABULARY
from vultron.wire.as2.vocab.base.utils import generate_new_id

ACTIVITY_STREAMS_NS = "https://www.w3.org/ns/activitystreams"


class as_Base(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
    )

    _vocab_ns: ClassVar[VocabNamespace] = VocabNamespace.AS

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)  # type: ignore[arg-type]
        annotations = cls.__dict__.get("__annotations__", {})
        if "type_" not in annotations:
            return  # No type_ override → abstract base, skip
        annotation = annotations["type_"]
        # Skip if annotation is a union type (e.g., str | None = abstract base)
        if isinstance(annotation, _types.UnionType):
            return
        if _typing.get_origin(annotation) is _typing.Union:
            return
        key = cls.__name__.removeprefix("as_")
        VOCABULARY[key] = cls

    context_: str = Field(
        default=ACTIVITY_STREAMS_NS,
        validation_alias="@context",
        serialization_alias="@context",
    )
    type_: str | None = Field(
        default=None,
        validation_alias="type",
        serialization_alias="type",
    )
    id_: str = Field(
        default_factory=generate_new_id,
        validation_alias="id",
        serialization_alias="id",
    )
    name: str | None = None
    preview: str | None = None
    media_type: str | None = None

    @model_validator(mode="after")
    def set_type_from_class_name(self):
        if self.type_ is None:
            self.type_ = self.__class__.__name__.lstrip("as_")
        return self

    def to_json(self, **kwargs):
        """Serialize the model to a JSON string, excluding None values and using aliases."""
        return self.model_dump_json(exclude_none=True, by_alias=True, **kwargs)

    def to_dict(self, **kwargs):
        """Serialize the model to a dictionary, excluding None values and using aliases."""
        return self.model_dump(exclude_none=True, **kwargs)

    @classmethod
    def from_json(cls, data: str):
        """Deserialize a JSON string to an instance of the model."""
        return cls.model_validate_json(data)
