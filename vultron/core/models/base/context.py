#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
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

"""The JSON-LD ``@context`` Vultron emits, and the Vultron-property field marker.

These live in core rather than in the wire layer because under ADR-0099 the
core classes *are* the objects that carry them, and core MUST NOT import wire
(ARCH-01-001 — the one boundary rule ADR-0099 leaves fully in force).  Wire
imports them from here, which ARCH-25-006 permits.
"""

from collections.abc import Callable
from contextvars import ContextVar
from enum import StrEnum
from typing import Annotated, Any

from pydantic import (
    ConfigDict,
    Field,
    SerializationInfo,
    model_validator,
)
from pydantic.config import JsonDict
from pydantic.fields import FieldInfo

from vultron.core.models.base.record import ValidatedAssignmentMixin
from vultron.primitives import NonEmptyString

#: The ActivityStreams 2.0 namespace.  AS2 Core §2.1 asks every producer to cite
#: it in ``@context``, and an AS2 receiver that does not process JSON-LD looks
#: for this exact string (VM-10-001).
ACTIVITY_STREAMS_NS = "https://www.w3.org/ns/activitystreams"

#: The Vultron JSON-LD context document, which declares the Vultron terms AS2
#: does not define (``VulnerabilityCase``, ``EmbargoEvent``, …).
VULTRON_CONTEXT_URI = "https://certcc.github.io/Vultron/ns/context.jsonld"

#: The ``@context`` every outbound top-level document carries: AS2 first, then
#: the Vultron context (VM-10-001).  Citing the Vultron URI alone is not
#: enough, because a receiver need not dereference it (VM-10-003) and so cannot
#: learn that it imports AS2.  A tuple, so no caller can mutate the default;
#: :func:`default_jsonld_context` gives the list form a document carries.
DEFAULT_JSONLD_CONTEXT: tuple[str, ...] = (
    ACTIVITY_STREAMS_NS,
    VULTRON_CONTEXT_URI,
)

#: The type of an object's JSON-LD ``@context``: one context IRI, or a
#: non-empty list of them in order.  A signed body's context is a list: the
#: signing module appends the data-integrity context to the activity's own
#: (FEP-8b32, ``vultron.wire.as2.signing``), so a single context becomes
#: two.  Each entry, and the list itself, is "if present, then non-empty"
#: (CS-08-002).  An inline context object (a JSON-LD term map) is not
#: accepted: nothing Vultron sends or reads defines terms inline.
JsonLdContext = (
    NonEmptyString | Annotated[list[NonEmptyString], Field(min_length=1)]
)


def default_jsonld_context() -> list[str]:
    """A fresh list holding :data:`DEFAULT_JSONLD_CONTEXT`."""
    return list(DEFAULT_JSONLD_CONTEXT)


def is_default_jsonld_context(value: object) -> bool:
    """Whether *value* is the default ``@context`` (the list, in its order)."""
    return isinstance(value, list) and tuple(value) == DEFAULT_JSONLD_CONTEXT


#: ``True`` while an AS2 (``by_alias``) dump is serializing an enclosing
#: document, so an object serialized inside it knows it is nested.
_INSIDE_AS2_DOCUMENT: ContextVar[bool] = ContextVar(
    "_inside_as2_document", default=False
)


def serialize_with_top_level_context(
    serialize: Callable[[], Any],
    info: SerializationInfo,
    explicit_context: JsonLdContext | None,
) -> Any:
    """Run *serialize* and place ``@context`` on the top-level document only.

    The top-level document of an AS2 dump carries *explicit_context*, or the
    default list when it is ``None`` (VM-10-001).  An object nested inside it
    does not restate the default: the enclosing context already applies to
    it, as JSON-LD scopes a context to the whole tree below it (VM-10-001).  A
    nested object that holds a non-default *explicit_context*, such as one
    received from a peer with its own, keeps it, because dropping it could
    change how that object's terms expand.

    ``@context`` is written first, where a reader looks for it.  The
    persistence dump (``by_alias`` false) is passed through untouched.
    """
    if not info.by_alias:
        return serialize()
    nested = _INSIDE_AS2_DOCUMENT.get()
    token = _INSIDE_AS2_DOCUMENT.set(True)
    try:
        data = serialize()
    finally:
        _INSIDE_AS2_DOCUMENT.reset(token)
    if not isinstance(data, dict):
        return data
    rest = {key: value for key, value in data.items() if key != "@context"}
    if explicit_context is not None:
        return {"@context": explicit_context, **rest}
    if nested:
        return rest
    return {"@context": default_jsonld_context(), **rest}


#: Key of the ``json_schema_extra`` marker that declares a wire field a
#: Vultron-namespace property, such as a termination ``Remove``'s
#: ``terminationCause`` (EMB-13-005) or a case's ``ledgerPosition``
#: (SYNC-16-005).  The context generator maps each marked field's wire name to
#: ``vultron:<name>``, typed by its value kind, so a receiver can resolve it.
#: In core for the reason :data:`VULTRON_CONTEXT_URI` is: core classes carry it
#: (ADR-0099).  Build the marker with :func:`vultron_property`, never by hand.
VULTRON_PROPERTY_KEY = "vultron_property"


class PropertyValueKind(StrEnum):
    """The shape of a Vultron property's value (VM-10-008, VM-10-010).

    The context generator types the property's JSON-LD term from it, as the
    AS2 context types its own terms (ADR-0194).  A scalar kind says what one
    value is; a container kind says how an array or map of values is read,
    and its declaration's ``items`` says what each value in it is.
    """

    #: A literal (string, number, boolean, date) or an embedded object.  The
    #: term is a bare ``vultron:<name>``.
    PLAIN = "plain"
    #: An IRI, or an object that has one: ``"@type": "@id"``, so a JSON-LD
    #: reader resolves a string value as a link, not as text.
    IRI = "iri"
    #: A received JSON document kept verbatim: ``"@type": "@json"``, so a
    #: JSON-LD reader expands none of its keys.
    JSON = "json"
    #: An array whose order matters: ``"@container": "@list"``.
    LIST = "list"
    #: An array whose order does not matter: ``"@container": "@set"``.
    SET = "set"
    #: A map keyed by IRIs: ``"@container": "@index"``, so a JSON-LD reader
    #: does not read its keys as properties.
    INDEX = "index"


#: The kinds that hold several values, each of the declaration's ``items`` kind.
CONTAINER_KINDS = frozenset(
    {PropertyValueKind.LIST, PropertyValueKind.SET, PropertyValueKind.INDEX}
)

#: The kinds one value in a container may have.
ITEM_KINDS = frozenset({PropertyValueKind.PLAIN, PropertyValueKind.IRI})


class VultronPropertyDeclaration(ValidatedAssignmentMixin):
    """What a field's marker declares about its Vultron property (VM-10-008).

    ``definition`` is the one-line meaning that two declarations of one wire
    name share (VM-10-012); ``kind`` and ``items`` are what the context
    document's term is typed from (VM-10-010).  Construction refuses a blank,
    padded or multi-line definition, an ``items`` kind on a scalar kind, and
    an ``items`` kind no container holds.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    definition: NonEmptyString
    kind: PropertyValueKind
    items: PropertyValueKind = PropertyValueKind.PLAIN

    @model_validator(mode="after")
    def _one_line_and_items_fit_kind(self) -> VultronPropertyDeclaration:
        """Refuse a padded or multi-line definition and a misplaced ``items``."""
        if self.definition != self.definition.strip():
            raise ValueError(
                "a Vultron property definition has no surrounding whitespace, "
                f"got {self.definition!r}"
            )
        if "\n" in self.definition:
            raise ValueError(
                "a Vultron property definition is one line, got "
                f"{self.definition!r}"
            )
        if self.items not in ITEM_KINDS:
            raise ValueError(
                f"a container's items are {sorted(ITEM_KINDS)}, got {self.items}"
            )
        if (
            self.kind not in CONTAINER_KINDS
            and self.items is not PropertyValueKind.PLAIN
        ):
            raise ValueError(
                f"only a container kind declares its items; {self.kind} is a "
                f"scalar kind, got items={self.items}"
            )
        return self

    def as_json(self) -> JsonDict:
        """The declaration as the JSON value the marker stores."""
        value: JsonDict = {
            "definition": self.definition,
            "kind": self.kind.value,
        }
        if self.items is not PropertyValueKind.PLAIN:
            value["items"] = self.items.value
        return value


def vultron_property(
    definition: str,
    kind: PropertyValueKind,
    *,
    items: PropertyValueKind = PropertyValueKind.PLAIN,
) -> JsonDict:
    """The marker that declares a field a Vultron property: pass it as the
    field's ``json_schema_extra`` (VM-10-007, VM-10-008).

    *definition* is the property's meaning in one line; *kind* is its value's
    shape, and *items*, for a container kind, the shape of each value in it.
    Raises ``ValueError`` (a ``pydantic.ValidationError``) on a declaration
    :class:`VultronPropertyDeclaration` refuses.
    """
    declaration = VultronPropertyDeclaration(
        definition=definition, kind=kind, items=items
    )
    return {VULTRON_PROPERTY_KEY: declaration.as_json()}


def declared_vultron_property(
    info: FieldInfo,
) -> VultronPropertyDeclaration | None:
    """The Vultron property *info*'s marker declares, or ``None`` if unmarked.

    Raises ``TypeError`` when the marker is present but is not the mapping
    :func:`vultron_property` builds, such as the former bare ``True`` flag, so
    a malformed marker cannot pass as a declared property, and ``ValueError``
    when the mapping holds a declaration
    :class:`VultronPropertyDeclaration` refuses or an unknown kind.
    """
    extra = info.json_schema_extra
    if not isinstance(extra, dict) or VULTRON_PROPERTY_KEY not in extra:
        return None
    value = extra[VULTRON_PROPERTY_KEY]
    fields = value if isinstance(value, dict) else {}
    definition = fields.get("definition")
    kind = fields.get("kind")
    items = fields.get("items", PropertyValueKind.PLAIN.value)
    if (
        not fields
        or set(fields) - {"definition", "kind", "items"}
        or not isinstance(definition, str)
        or not isinstance(kind, str)
        or not isinstance(items, str)
    ):
        raise TypeError(
            "a Vultron property marker is the mapping vultron_property() "
            f"builds, with a string definition and kind, got {value!r}"
        )
    return VultronPropertyDeclaration(
        definition=definition,
        kind=PropertyValueKind(kind),
        items=PropertyValueKind(items),
    )
