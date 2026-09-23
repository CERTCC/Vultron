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

from pydantic import BaseModel

from vultron.core.models.registry import find_in_core_type_map

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
        field = getattr(cls, "model_fields", {}).get("type_")
        declared = (
            getattr(field, "default", None) if field is not None else None
        )
    # A ``Field(...)`` assignment carries the default on the FieldInfo; a plain
    # ``type_: Literal["Foo"] = "Foo"`` assignment is the value itself.
    default = getattr(declared, "default", declared)
    value = getattr(default, "value", default)
    return value if isinstance(value, str) and value else None


def wire_type_value(cls: type) -> str:
    """Return the wire ``type`` value instances of *cls* will carry.

    Mirrors ``as_Base.set_type_from_class_name`` (VM-03-001): the declared
    default when there is one, else the class name with the ``as_`` prefix
    removed. This is the key form ``WIRE_TYPE_MAP`` uses (VM-01-007).
    """
    return declared_wire_type(cls) or cls.__name__.removeprefix("as_")


def is_wire_type_alias(cls: type) -> bool:
    """Return whether *cls* declares itself an alias of another wire type.

    An alias shares another class's wire ``type`` value (``as_VulnerabilityCaseStub``
    emits ``type: "VulnerabilityCase"``) and therefore MUST NOT own a
    ``WIRE_TYPE_MAP`` key: exactly one class can be what a given ``type`` value
    deserializes to. Read off the class's own namespace rather than inherited,
    so a subclass that narrows ``type_`` to a distinct value still registers.
    """
    return bool(cls.__dict__.get("_wire_type_alias", False))


def find_in_vocabulary(item_name: str) -> type[BaseModel]:
    """Find a class in the vocabulary by type name.

    Checks ``WIRE_TYPE_MAP`` (keyed by wire ``type_`` value) first, then
    ``VOCABULARY`` (keyed by full wire class name), then falls back to the
    core ``CORE_TYPE_MAP`` (via :func:`find_in_core_type_map`) for types
    that belong to the core domain layer (ARCH-12-003).

    Args:
        item_name: The name of the type to find.
    Returns:
        The class registered under that name.
    Raises:
        KeyError: If the type name is not registered in either vocabulary.
    """
    if item_name in WIRE_TYPE_MAP:
        return WIRE_TYPE_MAP[item_name]
    if item_name in VOCABULARY:
        return VOCABULARY[item_name]
    try:
        return find_in_core_type_map(item_name)
    except KeyError:
        pass
    raise KeyError(f"Unknown vocabulary type: {item_name!r}")


def main():
    pass


if __name__ == "__main__":
    main()
