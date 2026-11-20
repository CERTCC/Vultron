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

"""Which class reads an inline object at the parse edge (MV-11-001, ADR-0217).

The unknown-key partition (``unknown_keys.py``) and the parser's expansion
(``parser.py``) each meet every inline object of a received body, and each
must read it with the same class: the partition decides its keys against that
class's declared spellings, and the expansion validates it with that class.
This module is the one place both ask.

Outside a preview the object's ``type`` names the class
(:func:`resolve_inline_class`).  Inside a preview, what the sender shows is
read as sent (MV-12-006): an object takes the loose form its field declares,
or else the loose form of the class its ``type`` names, all the way down
(:func:`inline_class`).  An actor, a Link, a typed reference in a field that
declares no loose form, a marker and a preview are read whole.
"""

import types
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from types import MappingProxyType
from typing import (
    Any,
    Literal,
    TypeAliasType,
    Union,
    get_args,
    get_origin,
)

from pydantic import AliasChoices, AliasPath, BaseModel

from vultron.core.models._helpers import strip_annotated
from vultron.core.models.actor import CoreActor
from vultron.core.models.base import CoreObject
from vultron.core.models.preview_object import (
    PreviewObject,
    PreviewValue,
    loose_form,
)
from vultron.core.models.redacted import Redacted
from vultron.wire.as2.errors import VultronParseUnknownTypeError
from vultron.wire.as2.typed_reference import (
    as_TypedReference,
    reads_as_typed_reference,
    refuse_undefined_preview,
)
from vultron.wire.as2.vocab.base.links import as_Link
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.registry import (
    AmbiguousWireTypeError,
    resolve_wire_type,
    resolved_wire_type_name,
)

#: The JSON-LD context key every object may carry (MV-11-001).  It is the only
#: JSON-LD keyword that is a declared spelling: ``@id`` and ``@type`` are near
#: misses of ``id`` and ``type`` by design, because AS2 compacts them away (AS2
#: Core section 2.1), so they MUST NOT be declared or exempted (MV-11-007).
CONTEXT_KEY = "@context"


@dataclass(frozen=True)
class Spellings:
    """The declared spellings of one or more classes, indexed two ways."""

    #: Every declared spelling, mapped to the fields' annotations it can fill.
    annotations: Mapping[str, tuple[object, ...]]
    #: Normalised spelling → the declared spelling a refusal names.
    by_normalised: Mapping[str, str]


def normalise(key: str) -> str:
    """Lowercase *key* and remove every non-alphanumeric character (MV-11-002)."""
    return "".join(ch for ch in key.lower() if ch.isalnum())


def _alias_keys(alias: object) -> list[str]:
    """Return the top-level keys a validation alias reads."""
    if isinstance(alias, str):
        return [alias]
    if isinstance(alias, AliasPath):
        first = alias.path[0] if alias.path else None
        return [first] if isinstance(first, str) else []
    if isinstance(alias, AliasChoices):
        return [key for choice in alias.choices for key in _alias_keys(choice)]
    return []


@cache
def class_spellings(cls: type[BaseModel]) -> Spellings:
    """Enumerate every key *cls* accepts on input (MV-11-001).

    A declared spelling is a field name (both roots validate by name, CS-14-001
    and CS-14-002), the alias the class generates or declares for it, any
    explicit validation alias, a computed field's spellings (its value is
    checked against the derived one rather than refused, ARCH-23-005), and
    ``@context``.  A refusal names the alias ahead of the field name, because
    the alias is the AS2 spelling a sender reads.
    """
    by_name = bool(
        cls.model_config.get("validate_by_name")
        or cls.model_config.get("populate_by_name")
    )
    annotations: dict[str, tuple[object, ...]] = {CONTEXT_KEY: ()}
    preferred: list[str] = []
    fallback: list[str] = []
    for name, info in cls.model_fields.items():
        aliases = _alias_keys(info.validation_alias) + _alias_keys(info.alias)
        spellings = aliases + ([name] if by_name or not aliases else [])
        for spelling in spellings:
            annotations[spelling] = (info.annotation,)
        preferred.extend(aliases)
        fallback.append(name)
    generator = cls.model_config.get("alias_generator")
    for name, computed in cls.model_computed_fields.items():
        alias = getattr(computed, "alias", None)
        spellings = [name]
        if isinstance(alias, str):
            spellings.insert(0, alias)
        elif callable(generator):
            spellings.insert(0, generator(name))
        for spelling in spellings:
            annotations.setdefault(spelling, ())
        preferred.append(spellings[0])
    by_normalised: dict[str, str] = {}
    for spelling in [*preferred, *fallback, CONTEXT_KEY]:
        by_normalised.setdefault(normalise(spelling), spelling)
    return Spellings(
        annotations=MappingProxyType(annotations),
        by_normalised=MappingProxyType(by_normalised),
    )


def merged_spellings(classes: tuple[type[BaseModel], ...]) -> Spellings:
    """Merge the spellings of several candidate classes (an untyped dict)."""
    if len(classes) == 1:
        return class_spellings(classes[0])
    annotations: dict[str, tuple[object, ...]] = {}
    by_normalised: dict[str, str] = {}
    for cls in classes:
        spellings = class_spellings(cls)
        for key, found in spellings.annotations.items():
            annotations[key] = annotations.get(key, ()) + found
        for norm, spelling in spellings.by_normalised.items():
            by_normalised.setdefault(norm, spelling)
    return Spellings(annotations=annotations, by_normalised=by_normalised)


def _model_candidates(
    annotation: object,
) -> tuple[type[BaseModel], ...] | None:
    """Return the model classes a field annotation validates a dict into.

    Looks through ``Annotated``, unions, ``Optional`` and sequence containers.
    Returns ``None`` when the annotation also admits a plain dict or ``Any``:
    then no class decides what a key means, so the dict is carried unexamined.
    """
    found: list[type[BaseModel]] = []

    def visit(ann: object) -> bool:
        ann = strip_annotated(ann)
        if isinstance(ann, TypeAliasType):
            return visit(ann.__value__)
        alias = get_origin(ann)
        if isinstance(alias, TypeAliasType):
            # A generic alias applied, such as ``Redactable[CaseStatus]``: its
            # value names the alias's own classes, its arguments the rest.
            return visit(alias.__value__) and all(
                visit(arg) for arg in get_args(ann)
            )
        if ann is Any:
            return False
        if isinstance(ann, type) and issubclass(ann, BaseModel):
            found.append(ann)
            return True
        origin = get_origin(ann)
        if origin is Union or isinstance(ann, types.UnionType):
            return all(visit(arg) for arg in get_args(ann))
        if origin in (dict, Mapping) or ann is dict:
            return False
        if origin in (list, set, frozenset, tuple, Sequence):
            return all(visit(arg) for arg in get_args(ann) if arg is not ...)
        return True

    if not visit(annotation):
        return None
    return tuple(dict.fromkeys(found))


def candidates_for(
    annotations: tuple[object, ...],
) -> tuple[type[BaseModel], ...]:
    """Union the model candidates of every annotation a key can fill."""
    found: list[type[BaseModel]] = []
    for annotation in annotations:
        candidates = _model_candidates(annotation)
        if candidates is None:
            return ()
        found.extend(candidates)
    return tuple(dict.fromkeys(found))


def resolve_inline_class(
    value: dict[str, Any], path: str = ""
) -> type[BaseModel] | None:
    """Return the most specific *wire* class for an inline dict's ``type``.

    Returns ``None`` when the dict's ``type`` names no known type, which
    leaves the dict for its parent field to validate (MV-04-004).  The lookup
    is the shared resolver's wire-only default (VM-06-008, ISSUE-3217), so a
    ``type`` list resolves to its most specific known class (ADR-0196).
    Shared by this partition, which calls it on the raw dict, and the
    parser's expansion, which calls it on the partitioned one; both calls
    answer the same class.

    A list that names two unrelated known types names no class to leave the
    dict to either, so it refuses the activity as an unknown type at any
    depth, as it does at the top (ADR-0196).  *path* locates it.

    The ``type`` decides the class, the case's preview included: it names
    itself ``CasePreview`` (MV-10-012).  The one exception is a
    dict that carries only its ``id`` and ``type``: that is a typed
    reference, read as an :class:`as_TypedReference` (MV-10-011, ADR-0198),
    unless its class has a reference form of its own
    (:func:`~vultron.wire.as2.typed_reference.reads_as_typed_reference`).
    A ``VulnerabilityCase`` of that shape is the case reference a
    participant's act on a case names it by (AKM-03-004, ADR-0165), and a
    dict with any other key is a case.  The partition, on the raw dict,
    therefore decides a foreign key against the class's fields and sets it
    aside; the expansion, on the partitioned dict, then sees the reference
    that remains.  A key the class declares keeps the dict a whole object in
    both calls.
    A typed reference carrying a ``preview`` its type does not define is
    refused here, at its position (MV-10-012).
    """
    refuse_undefined_preview(value, path)
    try:
        cls = resolve_wire_type(value.get("type"))
    except AmbiguousWireTypeError as exc:
        where = f" at {path!r}" if path else ""
        raise VultronParseUnknownTypeError(
            f"Unrecognized inline object type{where}: {exc.args[0]}."
        ) from exc
    except KeyError:
        return None
    if reads_as_typed_reference(value, cls):
        return as_TypedReference
    return cls


def slot_classes(
    cls: type[BaseModel], key: str
) -> tuple[type[BaseModel], ...]:
    """The model classes *cls*'s field spelled *key* validates a dict into.

    Empty when *cls* declares no such spelling, or the field also admits a
    plain dict or ``Any``, so no class decides the dict's keys.
    """
    annotations = class_spellings(cls).annotations.get(key)
    return candidates_for(annotations) if annotations else ()


def declared_slot_class(
    value: dict[str, Any],
    candidates: tuple[type[BaseModel], ...],
    resolved: type[BaseModel] | None,
) -> type[BaseModel] | None:
    """The class a slot declares for *value*'s ``type`` in place of
    *resolved*, the wire class its ``type`` names, or ``None`` to keep that.

    The partition and the parser's expansion read a slot-declared class the
    same way (:func:`declared_for_type`), so one class decides a nested
    object's keys and validates it.
    """
    declared = declared_for_type(value, candidates, resolved)
    return declared[0] if len(declared) == 1 else None


def _type_literal_values(cls: type[BaseModel]) -> tuple[object, ...]:
    """The values a class's ``type_`` ``Literal`` admits, or ``()``."""
    field = cls.model_fields.get("type_")
    if field is None:
        return ()
    annotation = strip_annotated(field.annotation)
    if get_origin(annotation) is not Literal:
        return ()
    return get_args(annotation)


def declared_for_type(
    value: dict[str, Any],
    candidates: tuple[type[BaseModel], ...],
    resolved: type[BaseModel] | None,
) -> tuple[type[BaseModel], ...]:
    """The slot's declared classes that name *value*'s ``type``, when the wire
    class its ``type`` resolves to is another class.

    A slot may declare its own model for a shared AS2 type: a case
    reference's ``url`` is a ``CaseReferenceLink``, while ``type: Link``
    resolves to the wire ``as_Link``.  The class that validates the slot then
    decides its keys, so a Link property the reference does not hold is set
    aside and reported here, not read by a class that never keeps it.  A
    resolved subclass of a declared class keeps its own, wider, fields.
    """
    obj_type = resolved_wire_type_name(value.get("type"))
    if resolved is None or obj_type is None:
        return ()
    matches = tuple(
        cls for cls in candidates if obj_type in _type_literal_values(cls)
    )
    if any(issubclass(resolved, cls) for cls in matches):
        return ()
    return matches


def is_preview_form(cls: type[BaseModel] | None) -> bool:
    """Whether *cls* is a preview or a loose form a preview holds (ADR-0217)."""
    return cls is not None and issubclass(cls, (PreviewObject, PreviewValue))


#: Classes a preview's free-form field reads whole: an actor is named by its
#: own profile (AKM-05-017), a Link and a typed reference are not objects, and
#: a marker and a preview have no other form.
_READ_WHOLE: tuple[type[BaseModel], ...] = (
    CoreActor,
    as_Actor,
    as_Link,
    as_TypedReference,
    Redacted,
    PreviewObject,
    PreviewValue,
)


def _shown_form(resolved: type[BaseModel]) -> type[BaseModel]:
    """The form a preview shows an object of *resolved* in."""
    if resolved is CoreObject or issubclass(resolved, _READ_WHOLE):
        return resolved
    try:
        return loose_form(resolved)
    except TypeError:
        # A class with a wire shape of its own (a scalar dimension) has no
        # fields to cut, so it is read whole.
        return resolved


def inline_class(
    value: Mapping[str, Any],
    path: str = "",
    slots: tuple[type[BaseModel], ...] = (),
    in_preview: bool = False,
) -> type[BaseModel] | None:
    """The class that reads the inline object *value*, or ``None``.

    ``None`` leaves *value* for its parent field to validate (MV-04-004).
    *slots* are the model classes the field holding *value* declares, and
    *in_preview* says *value* sits inside a preview.  Inside one, a field's
    declared loose form wins; a dict with no ``type`` in a field that declares
    one loose form takes it, as does one whose ``type`` names nothing known,
    and in a field that declares none it is read as the loose object
    (:class:`PreviewObject`); any other typed object takes the loose form of
    the class its ``type`` names (MV-12-006, ADR-0217).

    Raises:
        VultronParseValidationError: For a typed reference carrying a preview
            its type does not define (MV-10-012).
        VultronParseUnknownTypeError: For a ``type`` list naming two
            unrelated known types (ADR-0196).
    """
    resolved = resolve_inline_class(dict(value), path)
    if not in_preview:
        return resolved
    loose = tuple(cls for cls in slots if is_preview_form(cls))
    if resolved is None:
        # No ``type``, or one naming nothing known: a field that declares one
        # loose form reads it, so a key that form lacks is set aside.  A
        # field that declares none reads it as the loose object, as a bare
        # ``CoreObject`` stands for it outside a preview, so a marker in it
        # and a missing ``id`` are read as sent.
        if not loose:
            return PreviewObject
        return loose[0] if len(loose) == 1 else None
    declared = declared_slot_class(dict(value), loose, resolved)
    if declared is not None:
        return declared
    return _shown_form(resolved)


def reads_inside_preview(
    classes: tuple[type[BaseModel], ...], in_preview: bool
) -> bool:
    """Whether the fields of an object read by *classes* sit inside a preview."""
    return in_preview or any(is_preview_form(cls) for cls in classes)
