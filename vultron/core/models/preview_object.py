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

"""Loose forms: what a preview reads its contents as (ADR-0217).

A preview is what its sender chose to show a recipient not yet entitled to the
whole object.  The recipient reads it as sent and decides on the invitation
that carries it, not on its shape.  So every object inside a preview is read in
a **loose form** of its class: the class's fields under the class's names,
every one optional, and any field or list item may hold a
:class:`~vultron.core.models.redacted.Redacted` marker.  A loose form keeps
none of its full class's invariants: a vul item shown with only its ``ids``,
with no ``id`` or ``published`` of its own, is read as shown.

The case preview itself is written by hand (:class:`~vultron.core.models.
case_preview.CasePreview`).  Every object nested in it takes a form derived
from its full class by :func:`loose_form`, all the way down, so no nested loose
form is maintained by hand and none falls behind its full class.

A loose form keeps its full class's wire ``type``, because the sender names the
object it shows.  The parse edge picks the loose form where a preview field
declares one (``slot`` classes in ``vultron/wire/as2/parser.py``), and a loose
form takes no type-registry slot, which would replace the full class a stored
row is read back as (:func:`~vultron.core.models.base.record.
shares_full_form_type`).
"""

import types
from collections.abc import Collection, Sequence
from datetime import datetime, timedelta
from typing import (
    Annotated,
    Any,
    ClassVar,
    TypeAliasType,
    Union,
    get_args,
    get_origin,
    overload,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    create_model,
    field_serializer,
    field_validator,
)
from pydantic.alias_generators import to_camel
from pydantic.fields import FieldInfo

from vultron.core.models._helpers.timestamps import as_utc, format_timestamp
from vultron.core.models.base import (
    CoreObject,
    NonEmptyString,
    ValidatedAssignmentMixin,
)
from vultron.core.models.base.core_object import CoreObjectOrIri
from vultron.core.models.base.language_map import (
    LanguageMap,
    language_map_field,
)
from vultron.core.models.redacted import Redactable, Redacted


def _utc_unless_marked(value: object) -> object:
    """A timestamp read as UTC; any other value, a marker included, as is."""
    return as_utc(value) if isinstance(value, datetime) else value


def _timestamp_or(
    value: object, handler: SerializerFunctionWrapHandler
) -> Any:
    """A timestamp in the fixed wire form, or *value* as *handler* writes it."""
    if isinstance(value, datetime):
        return format_timestamp(value)
    return handler(value)


class _LooseForm(ValidatedAssignmentMixin, BaseModel):
    """What every preview form shares: the full class it shows, and its
    timestamps read and written as the full class's are.

    The validator and serializer are named as ``CoreObject``'s, so they
    replace them.  They cover every field, not only the four AS2 times, so a
    ``datetime`` field a derived form takes from its full class
    (``rsvp_deadline``) is in the fixed form (CS-13-007), and a marker in
    any of them is kept as a marker.

    Class attributes:
        full_form: The full class a derived loose form reads; ``None`` on a
            preview type with a wire ``type`` of its own, such as the case
            preview.
    """

    full_form: ClassVar[type[BaseModel] | None] = None

    def __init_subclass__(
        cls, *, full_form: type[BaseModel] | None = None, **kwargs: Any
    ) -> None:
        # Set before the base hooks run, which read it to skip registering a
        # loose form under its full class's type.
        if full_form is not None:
            cls.full_form = full_form
        super().__init_subclass__(**kwargs)

    @field_validator("*")
    @classmethod
    def _normalise_datetime_to_utc(cls, value: Any) -> Any:
        """Read a naive timestamp as UTC, and any other value as itself."""
        return _utc_unless_marked(value)

    @field_serializer("*", mode="wrap", when_used="json")
    def _serialize_datetime(
        self, value: Any, handler: SerializerFunctionWrapHandler
    ) -> Any:
        """Write a timestamp in the fixed wire form, any other value as its
        field would be written."""
        return _timestamp_or(value, handler)


# The mixin's wrap serializer replaces CoreObject's plain one by name, on
# purpose, so mypy's signature check of the two bases does not apply.
class PreviewObject(_LooseForm, CoreObject):  # type: ignore[misc]
    """An object as a preview shows it: every field optional and redactable.

    The base of the hand-written case preview and of every loose form
    :func:`loose_form` derives from a ``CoreObject`` class.  It loosens the AS2
    properties every object carries.  The reference properties (``tag``,
    ``attachment``, ``context``, ...) already hold any embedded object, a
    marker included, so they keep their base type.

    A loose form shows what its sender chose, so it is received without an
    ``id`` or a ``published`` of its own when the sender showed none
    (OID-01-013, CLP-15-011), and every field it declares defaults to absent:
    a field the sender left out says nothing about the object's value.  The
    language maps keep the base's empty default, which no dump writes.
    """

    _received_without_published: ClassVar[bool] = True
    _received_without_id: ClassVar[bool] = True

    id_: Redactable[NonEmptyString] | None = Field(  # type: ignore[assignment]
        default=None,
        validation_alias="id",
        serialization_alias="id",
    )
    name: Redactable[NonEmptyString] | None = None  # type: ignore[assignment]
    preview: Redactable[NonEmptyString] | None = None  # type: ignore[assignment]
    media_type: Redactable[NonEmptyString] | None = None  # type: ignore[assignment]
    url: Redactable[NonEmptyString] | None = None  # type: ignore[assignment]
    replies: Redactable[CoreObjectOrIri] | None = None  # type: ignore[assignment]
    duration: Redactable[timedelta] | None = None  # type: ignore[assignment]
    start_time: Redactable[datetime] | None = None  # type: ignore[assignment]
    end_time: Redactable[datetime] | None = None  # type: ignore[assignment]
    published: Redactable[datetime] | None = None  # type: ignore[assignment]
    updated: Redactable[datetime] | None = None  # type: ignore[assignment]
    content: Redactable[NonEmptyString] | None = None  # type: ignore[assignment]
    summary: Redactable[NonEmptyString] | None = None  # type: ignore[assignment]
    attributed_to: Redactable[NonEmptyString] | None = None  # type: ignore[assignment]
    content_map: Redactable[LanguageMap] = language_map_field()  # type: ignore[assignment]
    name_map: Redactable[LanguageMap] = language_map_field()  # type: ignore[assignment]
    summary_map: Redactable[LanguageMap] = language_map_field()  # type: ignore[assignment]


class PreviewValue(_LooseForm):
    """A value object as a preview shows it, such as an embargo register
    entry or a vul item's identifier, or an AS2 object the wire vocabulary
    models.

    The base of every loose form :func:`loose_form` derives from a model that
    is not a ``CoreObject``.  Each derived field keeps its full class's
    aliases.
    """

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid"
    )


#: Classes a preview holds as they are: the marker, the bare ``CoreObject``
#: that stands for any embedded object, and preview types already loose.
_KEPT = (Redacted, PreviewObject, PreviewValue)


def _has_own_wire_shape(cls: type[BaseModel]) -> bool:
    """Whether *cls* writes itself as something other than its fields.

    A model serializer in ``plain`` mode replaces the field dump: a scalar
    dimension is written as its bare state (``"emState": "ACTIVE"``), so it
    has no fields on the wire to cut, and a preview shows it whole or
    withholds it, as it does a string.  A ``wrap`` serializer, such as the
    one every AS2 object adds its ``@context`` with, still writes the fields.
    """
    serializers = cls.__pydantic_decorators__.model_serializers.values()
    return any(serializer.info.mode == "plain" for serializer in serializers)


def _is_loosenable(ann: object) -> bool:
    return (
        isinstance(ann, type)
        and issubclass(ann, BaseModel)
        and ann is not CoreObject
        and not issubclass(ann, _KEPT)
        and not _has_own_wire_shape(ann)
    )


# The helpers below build annotations at run time.  An annotation is a type
# form, which no static type describes, so they take and return ``Any``.


def _loose_inner(ann: Any) -> Any:
    """*ann* with each model class it names replaced by its loose form."""
    if isinstance(ann, TypeAliasType):
        return _loose_inner(ann.__value__)
    origin = get_origin(ann)
    if isinstance(origin, TypeAliasType) or origin is Annotated:
        # Already a ``Redactable[...]``, a constrained scalar
        # (``NonEmptyString``) or an already-built object
        # (``UnmodelledObject``): read as declared.
        return ann
    if ann is str:
        # A full class that checks its string by a validator a loose form
        # does not carry still has a value, if shown, that is not blank
        # (CS-08-001).
        return NonEmptyString
    if _is_loosenable(ann):
        # A class met again while its own form is being derived is held whole
        # at that depth: the form cannot name itself before it exists.
        return ann if ann in _DERIVING else loose_form(ann)
    if origin is Union or isinstance(ann, types.UnionType):
        members = [_loose_inner(arg) for arg in get_args(ann)]
        return Union[tuple(members)]  # noqa: UP007 - built from a tuple
    return _loose_container(origin, ann)


def _loose_container(origin: Any, ann: Any) -> Any:
    """A collection annotation *ann* with each item loosened."""
    args = get_args(ann)
    if origin in (list, Sequence):
        return list[_loose_value(args[0] if args else Any)]  # type: ignore[misc]
    if origin in (set, frozenset):
        return origin[_loose_value(args[0] if args else Any)]
    if origin is tuple and len(args) == 2 and args[1] is ...:
        return tuple[_loose_value(args[0]), ...]  # type: ignore[misc]
    if origin is dict:
        key, value = args or (Any, Any)
        return dict[key, _loose_value(value)]  # type: ignore[misc,valid-type]
    return ann


def _loose_value(ann: Any) -> Any:
    """*ann* loosened, with the marker admitted in its place."""
    if ann is type(None) or ann is Any:
        return ann
    return Redactable[_loose_inner(ann)]  # type: ignore[misc]


def _loose_field(name: str, info: FieldInfo) -> tuple[Any, Any]:
    """The loose definition of the full class's field *name*."""
    if name == "type_":
        # The object's own type, as its full class names it: never loosened,
        # so the parse edge can tell a loose form by it.
        return info.annotation, _aliased(info, default=info.default)
    annotation = _loose_value(info.annotation)
    return annotation | None, _aliased(info, default=None)


def _aliased(info: FieldInfo, *, default: object) -> Any:
    """A field with *default* under the aliases of the full field *info*, its
    description, so both name one Vultron property (VM-10-007), and its
    exclusion, so a loose form sends no field its full class keeps local."""
    return Field(
        default=default,
        alias=info.alias,
        validation_alias=info.validation_alias,
        serialization_alias=info.serialization_alias,
        description=info.description,
        json_schema_extra=info.json_schema_extra,
        exclude=info.exclude,
    )


def _declares_its_own(
    cls: type[BaseModel], name: str, base: type[BaseModel]
) -> bool:
    """Whether *cls*'s field *name* is its own declaration, not the base's.

    A field the loose base declares keeps the base's loose declaration, unless
    *cls* narrows it (``CaseReference.url`` holds a Link, not a string), when
    the narrowed declaration is the one loosened.  ``type_`` is always the
    class's own.
    """
    if name == "type_" or name not in base.model_fields:
        return True
    inherited = CoreObject.model_fields.get(name)
    return (
        inherited is None
        or cls.model_fields[name].annotation != inherited.annotation
    )


#: Each class's loose form, once derived.
_FORMS: dict[type[BaseModel], type[PreviewObject | PreviewValue]] = {}

#: The classes whose loose forms are being derived, for a class whose fields
#: name it again (``as_Object.tag`` holds ``as_Object``s).
_DERIVING: set[type[BaseModel]] = set()


@overload
def loose_form(cls: type[CoreObject]) -> type[PreviewObject]: ...  # type: ignore[overload-overlap]


@overload
def loose_form(cls: type[BaseModel]) -> type[PreviewValue]: ...


def loose_form(
    cls: type[BaseModel],
) -> type[PreviewObject | PreviewValue]:
    """The loose form a preview reads an object of *cls* as (ADR-0217).

    Derived field by field: each of *cls*'s fields under its own name and
    aliases, optional, and admitting a marker; each model class a field
    names, at any depth, replaced by its own loose form.  ``type_`` keeps its
    full declaration.  A ``CoreObject`` class's form is a
    :class:`PreviewObject`, any other model's a :class:`PreviewValue`; the
    fields the base already declares loosely keep the base's declaration.
    The same form is returned for every call with the same class.

    Raises:
        TypeError: When *cls* is not a model class or is already loose.
    """
    if not _is_loosenable(cls):
        raise TypeError(f"{cls!r} has no loose form (ADR-0217)")
    if cls not in _FORMS:
        _DERIVING.add(cls)
        try:
            _FORMS[cls] = _derive(cls)
        finally:
            _DERIVING.discard(cls)
    return _FORMS[cls]


def _derive(cls: type[BaseModel]) -> type[PreviewObject | PreviewValue]:
    """Build the loose form :func:`loose_form` returns for *cls*."""
    base: type[PreviewObject | PreviewValue] = (
        PreviewObject if issubclass(cls, CoreObject) else PreviewValue
    )
    fields = {
        name: _loose_field(name, info)
        for name, info in cls.model_fields.items()
        if _declares_its_own(cls, name, base)
    }
    return create_model(  # type: ignore[call-overload,no-any-return]
        f"{cls.__name__}Preview",
        __base__=base,
        __module__=__name__,
        __doc__=(
            f"A {cls.__name__} as a preview shows it: every field optional"
            " and redactable (ADR-0217)."
        ),
        __cls_kwargs__={"full_form": cls},
        **fields,
    )


@overload
def to_loose(  # type: ignore[overload-overlap]
    obj: CoreObject, fields: Collection[str] | None = None
) -> PreviewObject: ...


@overload
def to_loose(
    obj: BaseModel, fields: Collection[str] | None = None
) -> PreviewValue: ...


def to_loose(
    obj: BaseModel, fields: Collection[str] | None = None
) -> PreviewObject | PreviewValue:
    """*obj* as a preview shows it: in its class's loose form (ADR-0217).

    Every field *obj* holds is shown as held, nested objects in their own
    loose forms, unless *fields* names the ones to keep, by Python field
    name; a field left out is not shown.  A derived value (a computed field)
    is not a field, so it is not shown.

    Raises:
        TypeError: When *obj*'s class has no loose form.
        ValueError: When *fields* names a field *obj*'s class does not
            declare, which would otherwise be shown as nothing.
    """
    form = loose_form(type(obj))
    unknown = set(fields or ()) - set(type(obj).model_fields)
    if unknown:
        raise ValueError(
            f"{type(obj).__name__} has no field {sorted(unknown)} to show"
            " (ADR-0217)"
        )
    data = obj.model_dump(
        include=set(fields) if fields is not None else None,
        exclude_computed_fields=True,
    )
    return form.model_validate(data)


def is_loose_form_of(value: object, cls: type[BaseModel]) -> bool:
    """Whether *value* is a loose form of *cls*, as a preview holds it."""
    return getattr(type(value), "full_form", None) is cls


__all__ = [
    "PreviewObject",
    "PreviewValue",
    "is_loose_form_of",
    "loose_form",
    "to_loose",
]
