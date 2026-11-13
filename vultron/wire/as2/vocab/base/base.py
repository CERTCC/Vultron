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
    VULTRON_PROPERTY_EXTRA,
    VULTRON_PROPERTY_KEY,
    JsonLdContext,
)
from vultron.core.models.base.context import (
    ACTIVITY_STREAMS_NS,
    DEFAULT_JSONLD_CONTEXT,
    default_jsonld_context,
    is_default_jsonld_context,
    serialize_with_top_level_context,
)
from vultron.core.models.type_terms import type_terms
from vultron.primitives import NonEmptyString
from vultron.wire.as2.vocab.base.enums import VocabNamespace
from vultron.wire.as2.vocab.base.registry import (
    VOCABULARY,
    WIRE_TYPE_MAP,
    AmbiguousWireTypeError,
    declared_wire_type,
    declares_registrable_type,
    is_wire_type_alias,
    narrow_type_list,
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
    "VULTRON_PROPERTY_EXTRA",
    "VULTRON_PROPERTY_KEY",
    "as_Base",
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

    #: Set on an extension class whose type overlaps an AS2 core type: the
    #: AS2 class it refines, which must be an ancestor.  AS2 requires such an
    #: extension type to carry the core type too, so the class serializes its
    #: ``type`` as the list ``[own type, core type]`` (``["Refuse",
    #: "Reject"]``), while ``type_`` stays its own one string; a receiver
    #: resolves the list back to the most specific class it knows (ADR-0196).
    #: Declared on the class body, ``_as2_core_supertype = as_Reject``, and
    #: checked when the class is defined (:func:`_check_as2_core_supertype`).
    _as2_core_supertype: ClassVar[type[as_Base] | None] = None

    #: ``False`` on a class whose instances are not ActivityStreams Objects
    #: (``as_Link`` and its subtypes): a received one may omit its ``id``, and
    #: keeps none rather than one minted for it (OID-01-013).
    _inbound_requires_id: ClassVar[bool] = True

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)  # type: ignore[arg-type]
        if not declares_registrable_type(cls):
            return  # No concrete type_ of its own → abstract base, skip
        # Before registering: a refused declaration leaves no registry entry.
        _check_as2_core_supertype(cls)
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

    @model_validator(mode="before")
    @classmethod
    def narrow_received_type_list(cls, data: Any) -> Any:
        """Read a ``type`` list as the one term it resolves to (ADR-0196).

        ``type_`` holds one string, so the list an extension class serializes
        (``_as2_core_supertype``), or any list a peer sends, is narrowed to the
        term of its most specific known class before the field validates it.
        A class whose own declared type is in the list reads it as that type:
        a list names each of its terms, so ``as_Reject`` reads
        ``["Refuse", "Reject"]`` as a ``Reject``, and a subclass that inherits
        ``type_`` reads it the same way.  A list that names no wire type is
        read as the core-only type it names (VM-06-008), else as its first
        term, as a string naming no known type is kept (an unknown inline
        object stays an ``as_Object``, MV-04-004, VM-03-006).  A list of two
        unrelated known types, or one with no string term, is refused.
        """
        if not isinstance(data, dict):
            return data
        try:
            narrowed = _narrow_known(data)
        except AmbiguousWireTypeError as exc:
            raise ValueError(exc.args[0]) from exc
        own = declared_wire_type(cls)
        own_read = None if own is None else _read_as_own_type(data, own)
        if own_read is None:
            return narrowed if narrowed is not None else _first_type_term(data)
        # A second key (``type`` beside ``type_``) may still hold a list.
        return _narrow_known(own_read) or _first_type_term(own_read)

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
            lambda: self._with_type_list(handler(self)), info, explicit
        )

    def _with_type_list(self, data: Any) -> Any:
        """*data* with ``type`` as ``[own type, core type]`` when the class has one.

        Only the wire dump (``by_alias``) gets the list: the persistence dump
        keys the field ``type_`` and keeps its one string, so a stored row
        reads back as it was written.  ``serialize_with_top_level_context``
        runs this only for the wire dump.
        """
        supertype = type(self)._as2_core_supertype
        if supertype is None or not isinstance(data, dict):
            return data
        if "type" not in data:
            return data
        own = wire_type_value(type(self))
        return {**data, "type": [own, wire_type_value(supertype)]}

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


def _narrow_known(data: dict[str, Any]) -> dict[str, Any] | None:
    """*data* with each ``type`` list narrowed to its known term, or ``None``.

    The wire vocabulary is asked first, then core-only types too, as the
    string lookup a union's core member sees (VM-06-008).  ``None`` when a
    list names no known type at all.

    Raises:
        AmbiguousWireTypeError: When a list names two unrelated known types.
    """
    try:
        return narrow_type_list(data)
    except AmbiguousWireTypeError:
        raise
    except KeyError:
        pass
    try:
        return narrow_type_list(data, include_core=True)
    except AmbiguousWireTypeError:
        raise
    except KeyError:
        return None


def _read_as_own_type(data: dict[str, Any], own: str) -> dict[str, Any] | None:
    """*data* with a ``type`` list naming *own* read as *own*, or ``None``."""
    narrowed = data
    for key in ("type", "type_"):
        value = data.get(key)
        if isinstance(value, list) and own in type_terms(value):
            narrowed = {**narrowed, key: own}
    return None if narrowed is data else narrowed


def _first_type_term(data: dict[str, Any]) -> dict[str, Any]:
    """*data* with each unresolved ``type`` list read as its first string term.

    Raises:
        ValueError: When a list holds no string term, so names no type at all.
    """
    narrowed = data
    for key in ("type", "type_"):
        value = data.get(key)
        if not isinstance(value, list):
            continue
        terms = type_terms(value)
        if not terms:
            raise ValueError(f"type list {value!r} names no type")
        narrowed = {**narrowed, key: terms[0]}
    return narrowed


def _check_as2_core_supertype(cls: type[as_Base]) -> None:
    """Refuse a malformed ``_as2_core_supertype`` declaration on *cls*.

    Checked when the class is defined, so a wrong declaration fails at import,
    not when the first message is sent.  The supertype must be an AS2 class
    (``VocabNamespace.AS``) that *cls* inherits from and whose wire ``type``
    differs from *cls*'s, and *cls* must be a Vultron extension class
    (``VocabNamespace.VULTRON``): AS2 asks only an extension type to carry
    the core type it overlaps (ADR-0196).  A subclass that inherits the
    declaration is checked the same way.

    Raises:
        TypeError: When the declaration breaks any of these rules.
    """
    supertype = cls._as2_core_supertype
    if supertype is None:
        return
    name = cls.__name__
    if not isinstance(supertype, type) or not issubclass(supertype, as_Base):
        raise TypeError(
            f"{name}._as2_core_supertype must be a wire class, not"
            f" {supertype!r}"
        )
    if supertype is cls or supertype not in cls.__mro__:
        raise TypeError(
            f"{name}._as2_core_supertype {supertype.__name__} must be a"
            f" superclass of {name}"
        )
    if supertype._vocab_ns is not VocabNamespace.AS:
        raise TypeError(
            f"{name}._as2_core_supertype {supertype.__name__} must be an AS2"
            " core class (VocabNamespace.AS)"
        )
    if cls._vocab_ns is not VocabNamespace.VULTRON:
        raise TypeError(
            f"{name} declares an AS2 core supertype, so it must be a Vultron"
            " extension class (_vocab_ns = VocabNamespace.VULTRON)"
        )
    if wire_type_value(cls) == wire_type_value(supertype):
        raise TypeError(
            f"{name} shares the wire type {wire_type_value(cls)!r} of its"
            f" AS2 core supertype {supertype.__name__}; an extension type"
            " names its own type"
        )
