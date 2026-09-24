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

from typing import Any, ClassVar

from pydantic import Field, model_validator, ConfigDict, ValidationInfo
from pydantic.alias_generators import to_camel

from vultron.core.models._helpers import absent_times_as_none
from vultron.core.models.base import VULTRON_CONTEXT_URI, VultronBase
from vultron.wire.as2.vocab.base.enums import VocabNamespace
from vultron.wire.as2.vocab.base.registry import (
    VOCABULARY,
    WIRE_TYPE_MAP,
    declares_registrable_type,
    is_wire_type_alias,
    wire_type_value,
)
from vultron.wire.as2.vocab.base.utils import generate_new_id

ACTIVITY_STREAMS_NS = "https://www.w3.org/ns/activitystreams"
#: The Vultron vocabulary namespace IRI, bound to the ``vultron:`` prefix in the
#: generated ``docs/ns/context.jsonld``. Distinct from ``VULTRON_CONTEXT_URI``,
#: which is the URL of the context *document*; this is the term namespace it
#: defines (VM-10-002). Single source of truth for the context generator.
VULTRON_NS_URI = "https://certcc.github.io/Vultron/ns#"

# Re-exported: this was the constant's original home, and wire-layer callers
# import it from here.  It now lives in core, because core objects are what
# carry it under ADR-0099 and core cannot import wire (ARCH-01-001).
__all__ = [
    "ACTIVITY_STREAMS_NS",
    "VULTRON_CONTEXT_URI",
    "VULTRON_NS_URI",
    "as_Base",
]


class as_Base(VultronBase):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
    )

    _vocab_ns: ClassVar[VocabNamespace] = VocabNamespace.AS

    #: Set ``True`` on a class that shares another class's wire ``type`` value
    #: and is therefore not what that value should deserialize to
    #: (``as_VulnerabilityCaseStub`` emits ``type: "VulnerabilityCase"``). Such a
    #: class stays reachable by class name through ``VOCABULARY`` but claims no
    #: ``WIRE_TYPE_MAP`` key of its own (VM-01-008).
    _wire_type_alias: ClassVar[bool] = False

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)  # type: ignore[arg-type]
        if not declares_registrable_type(cls):
            return  # No concrete type_ of its own → abstract base, skip
        if cls.__name__.startswith("as_"):
            VOCABULARY[cls.__name__] = cls
        # WIRE_TYPE_MAP answers "which class does this inbound `type` value
        # deserialize to?", so its key is the emitted `type` value — not the
        # class name, which diverges for the Vultron actor subtypes and would
        # register a key no payload ever carries (VM-01-008, issue #2982).
        if not is_wire_type_alias(cls):
            WIRE_TYPE_MAP[wire_type_value(cls)] = cls

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

    #: Validation-context key that marks a ``model_validate`` call as reading
    #: *inbound* data.  ``parse_activity`` sets it; nothing else should.
    INBOUND_CONTEXT_KEY: ClassVar[str] = "inbound_wire"

    @model_validator(mode="before")
    @classmethod
    def carry_absent_times_on_inbound(
        cls, data: Any, info: ValidationInfo
    ) -> Any:
        """Read an absent clock-defaulted timestamp as ``None`` when inbound.

        The same classes author outbound activities and validate inbound ones,
        so the ``default_factory=now_utc`` that correctly stamps an object *this
        process* creates would, on inbound data, fabricate a time the sender
        never claimed and present it downstream as the sender's claim
        (ISSUE-3257, CLP-15-007).  The two directions are told apart by
        validation context rather than by a field default: ``parse_activity``
        passes ``INBOUND_CONTEXT_KEY``, and Pydantic propagates the context
        through every nested model in that call.

        Doing this here rather than in the parser is what makes the rule hold at
        *every* depth.  The parser can only pre-treat a dict whose ``type`` it
        resolved; an inline object that omits ``type`` stays a raw dict for the
        parent field to validate, and that validation lands here, on the class
        the field actually chose.  Each class sees only its own
        ``model_fields``, so a class without timestamps (``as_Link``) is
        untouched rather than handed a key it would refuse.
        """
        if not isinstance(data, dict):
            return data
        context = info.context
        if not isinstance(context, dict) or not context.get(
            cls.INBOUND_CONTEXT_KEY
        ):
            return data
        return absent_times_as_none(cls, dict(data))

    @model_validator(mode="after")
    def set_type_from_class_name(self):
        if self.type_ is None:
            object.__setattr__(
                self, "type_", self.__class__.__name__.removeprefix("as_")
            )
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
