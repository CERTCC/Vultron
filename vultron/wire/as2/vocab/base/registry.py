#!/usr/bin/env python
"""
Provides a registry for the Vultron ActivityStreams Vocabulary.
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

import types as _types
import typing as _typing
from typing import Any

from pydantic import BaseModel

from vultron.core.models._helpers import own_annotations
from vultron.core.models.registry import (
    declared_type_value,
    find_in_core_type_map,
    type_value_of,
)

VOCABULARY: dict[str, type[BaseModel]] = {}

WIRE_TYPE_MAP: dict[str, type[BaseModel]] = {}

#: Sentinel distinguishing "the class declared no ``type_``" from "it declared
#: ``None``". Needed because ``as_Actor`` declares no concrete ``type_`` at all.
_UNDECLARED = object()


def declared_wire_type(cls: type) -> str | None:
    """Return *cls*'s declared wire ``type`` default, or ``None`` if abstract.

    Reads the raw class namespace first so this works from inside
    ``as_Base.__init_subclass__``, where ``model_fields`` has not been rebuilt
    yet and still reports the *parent's* ``type_`` default. Pydantic strips field
    definitions out of the namespace once the class is built, so after that only
    ``model_fields`` has the answer.

    Args:
        cls: A wire vocabulary class (built or mid-construction).
    Returns:
        The declared ``type`` value as a plain string, or ``None`` when *cls*
        declares no concrete default (an abstract or intermediate base).
    """
    declared = cls.__dict__.get("type_", _UNDECLARED)
    if declared is _UNDECLARED:
        return declared_type_value(cls)
    return type_value_of(declared)


def declares_registrable_type(cls: type) -> bool:
    """Return whether *cls* itself annotates a concrete (non-union) ``type_``.

    This is the gate ``as_Base.__init_subclass__`` applies before registering a
    class: an abstract base leaves ``type_`` unannotated or typed as a union
    (``str | None``), and a subclass that merely inherits ``type_`` is not a new
    wire type. Shared with the registry ratchet so both apply one rule.
    """
    annotations = own_annotations(cls)
    if "type_" not in annotations:
        return False
    annotation = annotations["type_"]
    if isinstance(annotation, _types.UnionType):
        return False
    return _typing.get_origin(annotation) is not _typing.Union


def wire_type_value(cls: type) -> str:
    """Return the wire ``type`` value instances of *cls* will carry.

    Mirrors ``as_Base.set_type_from_class_name`` (VM-03-001): the declared
    default when there is one, else the class name with the ``as_`` prefix
    removed. This is the key form ``WIRE_TYPE_MAP`` uses (VM-01-008).
    """
    return declared_wire_type(cls) or cls.__name__.removeprefix("as_")


def is_wire_type_alias(cls: type) -> bool:
    """Return whether *cls* declares itself an alias of another wire type.

    An alias shares another class's wire ``type`` value and therefore MUST NOT own a
    ``WIRE_TYPE_MAP`` key: exactly one class can be what a given ``type`` value
    deserializes to. Read off the class's own namespace rather than inherited,
    so a subclass that narrows ``type_`` to a distinct value still registers.
    """
    return bool(cls.__dict__.get("_wire_type_alias", False))


def find_in_vocabulary(
    item_name: str, *, include_core: bool = False
) -> type[BaseModel]:
    """Find the class the wire registry holds for the wire ``type`` *item_name*.

    Checks ``WIRE_TYPE_MAP``, keyed by wire ``type`` value (VM-01-008). It
    never consults ``VOCABULARY``, which is keyed by wire class name: a class
    name such as ``as_Activity`` is never an AS2 ``type`` value (VM-01-016),
    and ``as_Activity.type_`` is a bare ``str``, so a fallback to
    ``VOCABULARY`` resolved an inbound ``"type": "as_Activity"`` (#5738). By
    default the answer is therefore always a class the *wire* registry holds:
    an ``as_Base`` subclass, or a core class registered in ``WIRE_TYPE_MAP`` as
    its own wire form (ARCH-25-003, ADR-0099; e.g. ``VulnerabilityCase``). The
    discriminator is registry membership, not branch ancestry — an
    ``as_Base``-only rule would refuse the canonical case type.

    The core ``CORE_TYPE_MAP`` fallback (ARCH-12-010) is reached only when the
    caller passes ``include_core=True`` (VM-06-013). A hit there is a
    coincidence of naming rather than a wire counterpart (ARCH-23-002): while
    ``OrderedCollection`` was registered only in the core map, a wire caller
    resolving an inline actor's ``inbox`` got a core class that
    ``as_VultronOrganization.inbox`` refused, degrading the whole actor to a bare
    ``as_Link`` (ISSUE-3217), and the inbox adapter persisted a core object for
    an inbound ``{"type": "OrderedCollection"}`` (ISSUE-3565). Only a caller that
    reconstructs whatever was stored — the persistence read paths — may ask for
    the fallback, and it must say so in its call.

    Scope of the wire-only guarantee: it constrains what a *type lookup*
    returns, not what a wire tree may contain. ``as_ObjectRef`` unions do admit
    ``CoreObject``, so "wire trees contain only wire objects" is not true in
    general; the parent field annotation stays the authority on that.

    Args:
        item_name: The wire ``type`` value to find.
        include_core: Also consult ``CORE_TYPE_MAP`` when ``WIRE_TYPE_MAP``
            does not hold *item_name*. Wire-branch callers MUST leave this ``False``.
    Returns:
        The class registered under that name.
    Raises:
        KeyError: If no consulted registry holds *item_name*.
    """
    if item_name in WIRE_TYPE_MAP:
        return WIRE_TYPE_MAP[item_name]
    if include_core:
        try:
            return find_in_core_type_map(item_name)
        except KeyError:
            pass
    raise KeyError(f"Unknown vocabulary type: {item_name!r}")


class AmbiguousWireTypeError(KeyError):
    """A received ``type`` list names known types none of which is the most specific.

    A ``KeyError``, so every caller that already reads an unknown type from a
    lookup's ``KeyError`` reads this one as unknown too: neither class can be
    chosen, so the value names no class this receiver can build (ADR-0196).
    """


def _resolve_type_term(
    type_value: object, *, include_core: bool
) -> tuple[str, type[BaseModel]]:
    """Return the term of *type_value* that names its most specific known class.

    The one rule for a received ``type`` (ADR-0196): a string is looked up as it
    is; a list is narrowed to the known class that is a subclass of every other
    known class it names, in any order, and a term the vocabulary does not know
    is ignored, as AS2 expects of a receiver that meets an extension type.
    Anything else names no type.

    Raises:
        KeyError: When *type_value* names no known type.
        AmbiguousWireTypeError: When it names two known classes and neither is
            a subclass of the other.
    """
    if isinstance(type_value, str):
        return type_value, find_in_vocabulary(
            type_value, include_core=include_core
        )
    if not isinstance(type_value, list):
        raise KeyError(f"Unknown vocabulary type: {type_value!r}")
    known: dict[type[BaseModel], str] = {}
    for term in type_value:
        if not isinstance(term, str):
            continue
        try:
            cls = find_in_vocabulary(term, include_core=include_core)
        except KeyError:
            continue
        known.setdefault(cls, term)
    if not known:
        raise KeyError(f"Unknown vocabulary type: {type_value!r}")
    for cls, term in known.items():
        if all(issubclass(cls, other) for other in known):
            return term, cls
    raise AmbiguousWireTypeError(
        f"Type list {type_value!r} names the known types"
        f" {sorted(known.values())!r}, and none is a subtype of the others"
    )


def resolve_wire_type(
    type_value: object, *, include_core: bool = False
) -> type[BaseModel]:
    """Return the class a received ``type`` value names (ADR-0196).

    The shared resolver every reader of a received ``type`` goes through.
    *type_value* is a string or an AS2 type list: a list resolves to its most
    specific known class, in any order, and ignores terms the vocabulary does
    not know, so ``["Foo", "Reject"]`` is a ``Reject``.  Core holds the one
    class this returns, never the list.  Each term is looked up as
    :func:`find_in_vocabulary` looks it up, with the same *include_core* rule.

    Raises:
        KeyError: When *type_value* is not a string or a list, or names no
            known type.
        AmbiguousWireTypeError: When a list names two known classes and
            neither is a subclass of the other.
    """
    return _resolve_type_term(type_value, include_core=include_core)[1]


def resolved_wire_type_name(
    type_value: object, *, include_core: bool = False
) -> str | None:
    """Return the term of *type_value* that :func:`resolve_wire_type` resolves.

    For a reader that compares or reports a body's type by name: the name of
    the most specific known type in a list, the string itself when it names a
    known type, and ``None`` when *type_value* resolves to no class.
    """
    try:
        return _resolve_type_term(type_value, include_core=include_core)[0]
    except KeyError:
        return None


def narrow_type_list(
    data: dict[str, Any], *, include_core: bool = False
) -> dict[str, Any]:
    """Return *data* with a ``type`` list replaced by the term it resolves to.

    A class's ``type_`` field holds one string, so a received list is narrowed
    before the class validates it (ADR-0196).  *data* is returned unchanged
    when its ``type`` (or ``type_``) is not a list, and is never modified.

    Raises:
        KeyError: When the list names no known type.
        AmbiguousWireTypeError: When it names two unrelated known types.
    """
    narrowed = data
    for key in ("type", "type_"):
        value = data.get(key)
        if isinstance(value, list):
            term, _ = _resolve_type_term(value, include_core=include_core)
            narrowed = {**narrowed, key: term}
    return narrowed


def resolve_received_type(
    data: dict[str, Any], *, include_core: bool = False
) -> tuple[type[BaseModel], dict[str, Any]]:
    """Return the class *data*'s ``type`` names and *data* ready to validate.

    The two steps every reader of a received dict takes (ADR-0196): resolve
    its ``type`` with :func:`resolve_wire_type`, and narrow a list to the term
    it resolved to, so the class's one-string ``type_`` accepts it.  *data* is
    never modified.

    Raises:
        KeyError: When the ``type`` names no known type.
        AmbiguousWireTypeError: When it names two unrelated known types.
    """
    term, cls = _resolve_type_term(data.get("type"), include_core=include_core)
    if isinstance(data.get("type"), list):
        data = {**data, "type": term}
    return cls, data


def main():
    pass


if __name__ == "__main__":
    main()
