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

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    ValidationInfo,
    model_serializer,
    model_validator,
)
from pydantic.alias_generators import to_camel

from vultron.core.models._helpers import (
    INBOUND_CONTEXT_KEY,
    absent_times_as_none,
    refuse_absent_id,
)
from vultron.core.models.base import (
    VULTRON_CONTEXT_URI,
    VULTRON_PROPERTY_KEY,
    JsonLdContext,
    PropertyValueKind,
    vultron_property,
)
from vultron.core.models.base.context import (
    ACTIVITY_STREAMS_NS,
    DEFAULT_JSONLD_CONTEXT,
    default_jsonld_context,
    is_default_jsonld_context,
    serialize_with_top_level_context,
)
from vultron.primitives import NonEmptyString
from vultron.wire.as2.vocab.base.enums import VocabNamespace
from vultron.wire.as2.vocab.base.registry import (
    VOCABULARY,
    WIRE_TYPE_MAP,
    declares_registrable_type,
    is_wire_type_alias,
    wire_type_value,
)
from vultron.wire.as2.vocab.base.utils import generate_new_id

#: The Vultron vocabulary namespace IRI, bound to the ``vultron:`` prefix in the
#: generated ``docs/ns/context.jsonld``. Distinct from ``VULTRON_CONTEXT_URI``,
#: which is the URL of the context *document*; this is the term namespace it
#: defines (VM-10-002). Single source of truth for the context generator.
VULTRON_NS_URI = "https://certcc.github.io/Vultron/ns#"

# Re-exported: this was the constants' original home, and wire-layer callers
# import them from here.  They now live in core, because core objects are what
# carry them under ADR-0099 and core cannot import wire (ARCH-01-001).
__all__ = [
    "ACTIVITY_STREAMS_NS",
    "DEFAULT_JSONLD_CONTEXT",
    "VULTRON_CONTEXT_URI",
    "VULTRON_NS_URI",
    "VULTRON_PROPERTY_KEY",
    "PropertyValueKind",
    "as_Base",
    "vultron_property",
]


class as_Base(BaseModel):
    """Root of the wire vocabulary for AS2 types that have no core class.

    Under ARCH-25-004 (ADR-0099) this root inherits nothing from core: the core
    classes are the object model and AS2 is their serialization, so there is no
    shared ancestor to keep lenient for both.  What remains here is unpaired AS2
    vocabulary (``as_Link``, the generic activities) and it declares its own
    fields and configuration.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
    )

    _vocab_ns: ClassVar[VocabNamespace] = VocabNamespace.AS

    #: Set ``True`` on a class that shares another class's wire ``type`` value
    #: and is therefore not what that value should deserialize to. No
    #: production class declares it today; the case stub, its last user, became
    #: its own ``VulnerabilityCaseStub`` type in #4045 (CM-11-013). Such a
    #: class is still listed in ``VOCABULARY`` under its class name, but it
    #: claims no ``WIRE_TYPE_MAP`` key, so no wire ``type`` value resolves to it
    #: (VM-01-015, VM-01-016).
    _wire_type_alias: ClassVar[bool] = False

    #: ``False`` on a class whose instances are not ActivityStreams Objects
    #: (``as_Link`` and its subtypes): a received one may omit its ``id``, and
    #: keeps none rather than one minted for it (OID-01-013).
    _inbound_requires_id: ClassVar[bool] = True

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)  # type: ignore[arg-type]
        if not declares_registrable_type(cls):
            return  # No concrete type_ of its own → abstract base, skip
        if cls.__name__.startswith("as_"):
            VOCABULARY[cls.__name__] = cls
        # WIRE_TYPE_MAP answers "which class does this inbound `type` value
        # deserialize to?", so its key is the emitted `type` value — not the
        # class name, which diverges for the Vultron actor subtypes and would
        # register a key no payload ever carries (VM-01-012, issue #2982).
        if not is_wire_type_alias(cls):
            WIRE_TYPE_MAP[wire_type_value(cls)] = cls

    # Every outbound document cites AS2 and then the Vultron context
    # (VM-10-001): AS2 so a plain-JSON AS2 receiver recognizes it, Vultron so
    # ``VulnerabilityCase`` or ``EmbargoEvent`` expand.  The serializer emits
    # the default on the top-level document only.  An inbound body citing a
    # single string, or any other list (every signed body's is one, FEP-8b32),
    # still parses and keeps the context it arrived with (permissive receive).
    context_: JsonLdContext = Field(
        default_factory=default_jsonld_context,
        validation_alias="@context",
        serialization_alias="@context",
    )
    type_: str | None = Field(
        default=None,
        validation_alias="type",
        serialization_alias="type",
    )
    id_: NonEmptyString = Field(
        default_factory=generate_new_id,
        validation_alias="id",
        serialization_alias="id",
    )
    # "If present, then non-empty" (CS-08-001, CS-08-002): a blank value is
    # refused when the object is built, so no serialized object carries one
    # (VM-07-005).
    name: NonEmptyString | None = None
    preview: NonEmptyString | None = None
    media_type: NonEmptyString | None = None

    #: Validation-context key that marks a ``model_validate`` call as reading
    #: *inbound* data.  ``parse_activity`` sets it; nothing else should.
    INBOUND_CONTEXT_KEY: ClassVar[str] = INBOUND_CONTEXT_KEY

    @model_validator(mode="before")
    @classmethod
    def carry_absent_times_on_inbound(
        cls, data: Any, info: ValidationInfo
    ) -> Any:
        """Read an absent required timestamp as ``None`` when inbound.

        The same classes author outbound activities and validate inbound ones.
        An authored object states its time (ADR-0176); a received one may
        omit it, and the omission is the sender claiming no time, never the
        receiver's clock presented as the sender's claim (ISSUE-3257,
        CLP-15-007).  The two directions are told apart by
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

        The minted ``id`` default is the same fabrication, so it is gated the
        same way: a received Object without an ``id`` is refused, and a received
        Link (``_inbound_requires_id`` false) that omits one keeps none
        (OID-01-013, OID-01-014).
        """
        if not isinstance(data, dict):
            return data
        context = info.context
        if not isinstance(context, dict) or not context.get(
            cls.INBOUND_CONTEXT_KEY
        ):
            return data
        data = dict(data)
        if cls._inbound_requires_id:
            refuse_absent_id(cls, data)
        elif data.get("id") is None and data.get("id_") is None:
            # A received Link may omit its id; it keeps none (OID-01-013).
            data["id"] = None
        return absent_times_as_none(cls, data)

    @model_validator(mode="after")
    def set_type_from_class_name(self):
        if self.type_ is None:
            object.__setattr__(
                self, "type_", self.__class__.__name__.removeprefix("as_")
            )
        return self

    @model_serializer(mode="wrap")
    def _serialize_with_top_level_context(
        self,
        handler: SerializerFunctionWrapHandler,
        info: SerializationInfo,
    ) -> Any:
        """Emit ``@context`` on the top-level AS2 document only (VM-10-001)."""
        return self._as2_document(handler, info)

    def _as2_document(
        self,
        handler: SerializerFunctionWrapHandler,
        info: SerializationInfo,
    ) -> Any:
        """Dump this object, with ``@context`` placed per VM-10-001.

        A subclass that declares its own ``model_serializer`` replaces
        :meth:`_serialize_with_top_level_context`, so it calls this to keep the
        rule (``as_Activity``).
        """
        explicit = (
            None if is_default_jsonld_context(self.context_) else self.context_
        )
        return serialize_with_top_level_context(
            lambda: handler(self), info, explicit
        )

    def to_json(self, **kwargs):
        """Serialize the model to a JSON string, excluding None values and using aliases."""
        return self.model_dump_json(exclude_none=True, by_alias=True, **kwargs)

    def to_dict(self, **kwargs):
        """Serialize the model to a dictionary, excluding None values and using aliases."""
        return self.model_dump(exclude_none=True, by_alias=True, **kwargs)

    @classmethod
    def from_json(cls, data: str):
        """Deserialize a JSON string to an instance of the model."""
        return cls.model_validate_json(data)
