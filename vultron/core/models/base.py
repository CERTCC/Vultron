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

"""Base class for Vultron Protocol core domain object models."""

import inspect
import types as _types
import typing as _typing
from datetime import datetime, timedelta
from functools import cache
from typing import Any, ClassVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    TypeAdapter,
    ValidationInfo,
    field_serializer,
    field_validator,
    model_serializer,
    model_validator,
)
from pydantic.alias_generators import to_camel
from pydantic.functional_validators import ModelWrapValidatorHandler

from vultron.core.models._helpers import (
    INBOUND_CONTEXT_KEY,
    _new_urn,
    absent_times_as_none,
    as_utc,
    blank_times_as_none,
    now_utc,
)
from vultron.core.models.registry import CORE_TYPE_MAP, CORE_VOCABULARY
from vultron.errors import Violation, VultronProtocolViolationError
from vultron.primitives import NonEmptyString, UriString  # noqa: F401

#: The Vultron JSON-LD ``@context``.  VM-10-001 (MUST) requires it on every
#: Vultron-specific object on the wire; the ActivityStreams namespace alone "is
#: not sufficient" for types AS2 does not define.
#:
#: It lives in core rather than beside ``ACTIVITY_STREAMS_NS`` in the wire layer
#: because under ADR-0099 the core classes *are* the objects that carry it, and
#: core MUST NOT import wire (ARCH-01-001 — the one boundary rule ADR-0099 leaves
#: fully in force).  Wire imports it from here, which detail 6 permits.
VULTRON_CONTEXT_URI = "https://certcc.github.io/Vultron/ns/context.jsonld"


class ValidatedAssignmentMixin(BaseModel):
    """Mixin that enables Pydantic post-construction field validation on core models.

    Applied by :class:`CoreRecord`, so every core root and everything below it
    validates assignment to the same standard as construction (ARCH-21-001).
    Also composed directly onto the core ``BaseModel`` subclasses that are not
    records — dimensions, the hash-chain ledger record, dispatch events.
    Pydantic v2 merges ``model_config`` across the MRO, so the flag composes
    with each class's own configuration.
    """

    model_config = ConfigDict(validate_assignment=True)


@cache
def _type_adapter(return_type: Any) -> TypeAdapter[Any]:
    """One ``TypeAdapter`` per computed-field return type, built once."""
    return TypeAdapter(return_type)


def _json_form(return_type: Any, value: Any) -> Any:
    """Return *value*'s ``mode="json"`` form under its declared *return_type*.

    Exact only while the computed field declares no ``@field_serializer``,
    which :meth:`CoreObject.__pydantic_init_subclass__` enforces.
    """
    return _type_adapter(return_type).dump_python(value, mode="json")


class CoreRecord(ValidatedAssignmentMixin):
    """Minimal core root: a stored record that is not an AS2 object.

    ADR-0099 detail 4 gives core two roots.  This one carries only the
    identity every stored record needs — ``id_``, ``type_``, ``name`` — for
    records that never go on the wire in their own right: dead letters,
    offer bookkeeping, replication state.  It has no ``@context``, no alias
    generator and no AS2 object fields, so it has no AS2 spelling, which is
    why the rendering port refuses it (ARCH-20-003).

    The AS2-shaped root is :class:`CoreObject`, which extends this one.

    Every concrete subclass that declares a ``Literal`` ``type_`` registers in
    :data:`CORE_TYPE_MAP` so a stored row can be reconstructed by its type
    string (ARCH-12-010).  Wire classes do not inherit this root, so nothing
    here has to guard against them (#2416).
    """

    # A stored record refuses any key it does not declare: a row written before
    # a field rename fails loudly at read time instead of silently losing the
    # renamed field (#4186, ARCH-12-003).  ``id`` and ``type`` are the stored
    # spelling (``_rekey_wire_identity``); ``id_`` and ``type_`` the Python one.
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id_: NonEmptyString = Field(
        default_factory=_new_urn,
        validation_alias="id",
        serialization_alias="id",
    )
    type_: NonEmptyString | None = Field(
        default=None,
        validation_alias="type",
        serialization_alias="type",
    )
    name: NonEmptyString | None = None

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)  # type: ignore[arg-type]
        # Register every concrete core subclass in CORE_TYPE_MAP so that
        # find_in_vocabulary(..., include_core=True) can locate it without
        # placing it in the wire VOCABULARY dict. Only subclasses that declare
        # their own concrete type_ annotation are registered; abstract bases that inherit or omit
        # type_ are skipped (same guard as CoreObject).
        own_annotations = inspect.get_annotations(cls)
        if "type_" not in own_annotations:
            return
        try:
            hints = _typing.get_type_hints(cls)
        except (NameError, TypeError):
            # Forward references cannot be resolved yet (NameError) or an
            # annotation is not a valid type (TypeError) — do not register.
            # A half-constructed entry is worse than a missing one, which
            # surfaces immediately at lookup time (CS-23-001).
            return
        annotation = hints.get("type_")
        if isinstance(annotation, _types.UnionType):
            return
        if _typing.get_origin(annotation) is _typing.Union:
            return
        # Register by class name (covers classes where _set_type_from_class_name
        # sets type_ = cls.__name__, e.g. CoreActor stored as "CoreActor").
        CORE_TYPE_MAP[cls.__name__] = cls
        # Also register by the Literal value itself when it differs from the
        # class name (e.g. VultronOfferRecord → "OfferRecord"). Extract from
        # the annotation directly; model_fields is not yet populated at
        # __init_subclass__ time.
        literal_args = _typing.get_args(annotation)
        if (
            literal_args
            and len(literal_args) == 1
            and isinstance(literal_args[0], str)
        ):
            CORE_TYPE_MAP[literal_args[0]] = cls


def with_record_id(data: dict[str, Any], record_id: str) -> dict[str, Any]:
    """Return a copy of *data* whose record id is *record_id*.

    For a record that derives its id from its other fields.  The id is stated
    under the one spelling *data* already uses: ``id_`` for a dump or an
    assignment check (which validates by field name), ``id`` otherwise.  Stating
    the other spelling beside it would leave one of the two an unrecognised key,
    which ``extra="forbid"`` refuses.
    """
    out = dict(data)
    if "id_" in out and "id" not in out:
        out["id_"] = record_id
    else:
        out.pop("id_", None)
        out["id"] = record_id
    return out


class CoreObject(CoreRecord):
    """The one AS2 object root of the Vultron core domain model.

    ADR-0099 detail 4: under one object model the core classes *are* the AS2
    objects, so this root carries the AS2 object fields, the JSON-LD
    ``@context`` and the timestamps, on top of the identity from
    :class:`CoreRecord`.  Its ``by_alias`` dump is the AS2 wire form.

    The AS2 fields core does not use (``bto``, ``bcc``, ``generator``,
    ``icon``, ``image``, …) stay declared on purpose: a declared-but-unused
    field is a *recognised* field core ignores, whereas an undeclared one
    would be an unrecognised field rejected on every message carrying it
    (ADR-0099 details 7 and 8).

    A bare ``CoreObject(id_=..., type_=...)`` is the minimal reference the
    extractor wraps an otherwise-unmodelled object in; it keeps the ``type_``
    it was given, including ``None``.

    Subclasses that override ``type_`` with a concrete (non-union)
    annotation — e.g. ``type_: Literal["VulnerabilityCase"] = ...`` —
    register themselves in :data:`CORE_VOCABULARY` via
    ``__init_subclass__``.  Subclasses that leave ``type_`` abstract
    (omitted, or annotated as a union) are intentionally not registered.

    ``context_`` defaults to ``None`` and is ``exclude=True``, so it never
    reaches a stored row: ADR-0099 detail 1 keeps persistence on Python field
    names with no ``@context``.  It is emitted only on the AS2 path — see
    :meth:`_serialize_with_jsonld_context`.
    """

    # The AS2 spelling of every field, derived rather than hand-maintained.
    #
    # ADR-0099 detail 2 puts the AS2 spelling on the core class, because under one
    # object model there is no second class left to hold it.  `to_camel` derives
    # it correctly for all but three fields — `id_`, `type_` and `context_`, whose
    # trailing underscores exist to dodge Python keyword/shadowing collisions and
    # which therefore carry explicit aliases (`id`, `type`, `@context`).  `@context`
    # could not come from a generator at all.
    #
    # Deriving beats enumerating here: a hand-written alias per field silently
    # omits the ones nobody remembered, which is precisely how `attributedTo`
    # became `attributed_to` on the wire for four object types.  What keeps the
    # derivation honest is a closed-world test on the projected key set
    # (test_core_object_projection_keys), not the declaration site.
    #
    # This is the mechanism behind the rendering port, not a licence for core
    # code to dump its own objects: core logic hands rendering to the port, and
    # test/architecture/test_core_by_alias_dumps.py holds `vultron/core/` to an
    # empty baseline of `by_alias=True` calls (ARCH-12-003, ARCH-20-001).
    #
    # No unknown key may enter a core object: a wire-shaped payload handed to a
    # core type is rejected loudly rather than silently dropping every
    # snake_case-only key (the #2232 defect).  This subsumes the retired
    # per-class camelCase reject-guards and the wire→core normalisation gate
    # (ARCH-12-003, ADR-0082; closes the strong form of #2262).  The generator is
    # what makes the two compatible: every AS2 spelling is a declared alias, so
    # ``extra="forbid"`` refuses only keys that match no field at all.  Merged
    # with CoreRecord.populate_by_name and ValidatedAssignmentMixin
    # validate_assignment across the MRO.
    model_config = ConfigDict(alias_generator=to_camel, extra="forbid")

    #: Fields that are local bookkeeping, not AS2 properties: kept in the stored
    #: row, dropped from the delivery payload.
    #:
    #: ADR-0099 detail 3 makes a class that can appear in a message slot exactly
    #: AS2-representable and forbids it carrying "a field that cannot go on the
    #: wire".  ``exclude=True`` is the obvious way to express that and is the
    #: wrong one: it removes the field from *every* dump, including the
    #: persistence dump, so the value stops being stored at all.  That is a data
    #: loss rather than a wire-format fix — an invite RSVP deadline the local
    #: actor set would simply vanish on the next read.
    #:
    #: Declared as a ClassVar so a subclass names its own local fields where they
    #: are defined, rather than in a registry somewhere else that can fall behind.
    local_only_fields: ClassVar[frozenset[str]] = frozenset()

    preview: NonEmptyString | None = None
    media_type: NonEmptyString | None = None
    replies: Any | None = None
    url: NonEmptyString | None = None
    generator: Any | None = None
    context: Any | None = None
    tag: Any | None = None
    in_reply_to: Any | None = None
    duration: timedelta | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None

    # An object this process authors takes the local clock (default_factory);
    # an object it *receives* carries the sender's time, which AS2 lets the
    # sender omit, so an explicit ``None`` stays ``None`` rather than becoming
    # the receiver's clock (ISSUE-3257).  Decisions that need the time refuse
    # its absence at the wire edge, not here.
    published: datetime | None = Field(default_factory=now_utc)
    updated: datetime | None = Field(default_factory=now_utc)

    content: Any | None = None
    summary: NonEmptyString | None = None
    icon: Any | None = None
    image: Any | None = None
    attachment: Any | None = None
    location: Any | None = None
    to: Any | None = None
    cc: Any | None = None
    bto: Any | None = None
    bcc: Any | None = None
    audience: Any | None = None
    attributed_to: NonEmptyString | None = None

    context_: NonEmptyString | None = Field(
        default=None,
        validation_alias="@context",
        serialization_alias="@context",
        exclude=True,
    )

    @model_validator(mode="wrap")
    @classmethod
    def _check_computed_field_inputs(
        cls, data: Any, handler: ModelWrapValidatorHandler["CoreObject"]
    ) -> "CoreObject":
        """Strip or refuse supplied computed-field values (ARCH-23-005).

        A ``@computed_field`` (``VulnerabilityCase.active_participants``,
        CM-31-003) appears in the ``by_alias`` dump but is not settable; the
        persistence dump omits it (:meth:`_serialize_with_jsonld_context`).
        A value that matches the derived value is stripped so a dump
        round-trips; a value that contradicts the object's own derived state
        raises ``VultronProtocolViolationError`` carrying every contradiction
        as a structured ``Violation``, not only the first (EH-07-001,
        EH-07-003).  Every supplied *spelling* is checked on its own, so two
        spellings that disagree cannot hide one another.  A supplied value
        matches when it equals the derived Python value **or** that value's
        ``mode="json"`` serialization, so a JSON-mode dump round-trips for a
        computed field of any type.  See ``notes/wire-core-boundary.md``
        § "``extra="forbid"`` Is the Boundary Contract".
        """
        computed = cls.model_computed_fields
        if not isinstance(data, dict) or not computed:
            return handler(data)

        spellings = cls._computed_field_spellings()

        # Record every supplied computed-field value under the spelling it
        # arrived with, so that disagreeing duplicate spellings are each seen.
        supplied: list[tuple[str, str, Any]] = [
            (spelling, field_name, data[spelling])
            for spelling, field_name in spellings.items()
            if spelling in data
        ]
        if not supplied:
            return handler(data)

        # Strip every spelling before passing to the wrapped handler so that
        # extra="forbid" does not reject them.
        obj = handler({k: v for k, v in data.items() if k not in spellings})

        # Each derived value's JSON form comes from its declared return type:
        # the persistence dump omits computed fields (CM-31-003), and core
        # does not render the AS2 dump itself (ARCH-20-001).  A computed field
        # may not declare a field serializer, so the two forms agree
        # (:meth:`__pydantic_init_subclass__`).
        derived_json = {
            field_name: _json_form(
                computed[field_name].return_type, getattr(obj, field_name)
            )
            for field_name in {name for _spelling, name, _value in supplied}
        }
        violations = [
            Violation(
                message=(
                    f"{field_name!r} (as {spelling!r}): supplied"
                    f" {supplied_val!r}, derived {getattr(obj, field_name)!r}"
                ),
                dimensions=(field_name,),
            )
            for spelling, field_name, supplied_val in supplied
            if supplied_val != getattr(obj, field_name)
            and supplied_val != derived_json[field_name]
        ]
        if violations:
            raise VultronProtocolViolationError(
                "Supplied computed-field value(s) contradict derived state"
                " (ARCH-23-005)",
                violations=violations,
            )
        return obj

    @classmethod
    def _computed_field_wire_key(cls, name: str) -> str:
        """The key computed field *name* is emitted under in the AS2 dump."""
        alias = getattr(cls.model_computed_fields[name], "alias", None)
        return alias if isinstance(alias, str) else to_camel(name)

    @classmethod
    def _computed_field_spellings(cls) -> dict[str, str]:
        """Map every key spelling a computed field can arrive under to its name."""
        spellings: dict[str, str] = {}
        for name, info in cls.model_computed_fields.items():
            spellings[name] = name
            # CoreObject carries alias_generator=to_camel (ADR-0099 detail 2), so
            # dump(by_alias=True) emits `embargoAdherence`.
            spellings[to_camel(name)] = name
            alias = getattr(info, "alias", None)
            if isinstance(alias, str):
                spellings[alias] = name
        return spellings

    @model_validator(mode="before")
    @classmethod
    def _drop_alias_shadowed_field_names(cls, data: Any) -> Any:
        """Drop a field-name key when its validation alias is also present.

        An earlier ``mode="before"`` validator may derive a field and write it
        under the alias — ``_set_id_from_case`` writes ``"id"`` — beside the
        serialized field-name key (``"id_"``) already in the payload.  Under
        ``extra="forbid"`` the un-consumed twin is an unknown key.  The alias
        (wire-canonical, and the key carrying the freshly derived value) wins.
        This runs after subclass ``mode="before"`` validators, so it cleans up
        every such injection in one place rather than each site guarding
        itself (see ``notes/wire-core-boundary.md`` § "The ``id_`` Failures Are
        an Alias-Injection Bug").

        The alias wins even when the two values *differ*, which is deliberate
        rather than a silent pick: thirteen core types derive a canonical id in
        a ``mode="before"`` validator and write it under the alias — a ledger
        entry is addressed ``{case_id}/log/{log_index}`` (and several types mint
        a fresh urn), so a caller-supplied ``id_`` is meant to be superseded,
        not honoured.  Raising on disagreement was tried during #3531 triage and
        breaks exactly those paths (e.g. the extractor passes the wire activity
        id to ``CaseLedgerEntry`` alongside ``case_id``).  Only the *external*
        both-spellings-supplied case is genuinely ambiguous, and no live path
        reaches it — the wire layer supplies ``id`` alone.
        """
        if not isinstance(data, dict):
            return data
        drop = [
            name
            for name, field in cls.model_fields.items()
            if isinstance(field.validation_alias, str)
            and field.validation_alias != name
            and field.validation_alias in data
            and name in data
        ]
        if drop:
            data = {k: v for k, v in data.items() if k not in drop}
        return data

    @model_validator(mode="before")
    @classmethod
    def _carry_absent_times_on_inbound(
        cls, data: Any, info: ValidationInfo
    ) -> Any:
        """Read an absent or blank timestamp as ``None`` when inbound.

        The core-class twin of ``as_Base.carry_absent_times_on_inbound``, and
        needed for the same reason (ISSUE-3257, ADR-0103): ``default_factory=
        now_utc`` correctly stamps an object this process authors, but on
        inbound data it would fabricate a time the sender never claimed.  Under
        ADR-0099 detail 3 an inbound ``CaseParticipant``, ``EmbargoEvent`` or
        ``VulnerabilityCase`` validates straight into this class rather than a
        wire subclass of ``as_Base``, so without this the rule silently stops
        holding for every collapsed type.  Gated on the same validation-context
        key, which ``parse_activity`` sets and Pydantic propagates to nested
        models.
        """
        if not isinstance(data, dict):
            return data
        context = info.context
        if not isinstance(context, dict) or not context.get(
            INBOUND_CONTEXT_KEY
        ):
            return data
        return absent_times_as_none(cls, blank_times_as_none(cls, dict(data)))

    @field_validator("context_")
    @classmethod
    def _default_context_as_absent(cls, value: str | None) -> str | None:
        """Read the default Vultron ``@context`` back as no override.

        The AS2 serializer emits ``self.context_ or VULTRON_CONTEXT_URI``, so
        ``None`` and the default URI dump identically.  Keeping the supplied
        default would make every ``by_alias`` dump validate into an object
        unequal to the one dumped (ARCH-23-005, CM-31-003).  A non-default
        context is kept, so a document parsed from the wire still dumps
        with the context it arrived with.
        """
        return None if value == VULTRON_CONTEXT_URI else value

    @field_validator("start_time", "end_time", "published", "updated")
    @classmethod
    def _normalise_datetime_to_utc(
        cls, value: datetime | None
    ) -> datetime | None:
        """Read a naive timestamp as UTC; leave an absent one absent.

        The core twin of ``as_Object.validate_datetime`` (CS-13-001, CM-28-006,
        #3784).  Under ADR-0099 detail 3 an inbound ``EmbargoEvent``,
        ``CaseParticipant`` or ``VulnerabilityCase`` validates straight into
        this class, so the wire validator never sees their fields and a naive
        ``endTime`` on a nested object would otherwise reach core unchanged —
        and raise ``TypeError`` at the first comparison with an aware value.

        Runs after parsing, so it applies to a subclass that redeclares one of
        these fields (``EmbargoEvent.end_time``) as well as to the inherited
        ones.  It never fabricates a time: ``None`` stays ``None``
        (CLP-15-007, ADR-0103), and an aware value keeps its offset — the
        sender's claim is carried as received.
        """
        return as_utc(value)

    @field_serializer(
        "start_time", "end_time", "published", "updated", when_used="json"
    )
    def _serialize_datetime(self, value: datetime | None) -> str | None:
        """Write timestamps with an explicit offset, as the wire classes did.

        Pydantic's default JSON form for an aware UTC datetime is ``...Z``;
        ``isoformat()`` gives ``...+00:00``.  Both denote the same instant and
        both are valid ISO-8601, which is why swapping them is invisible in
        review — but they are different *bytes*, and
        ``CaseLedgerEntry.payloadSnapshot`` is compared across replicas, so two
        actors on different spellings disagree about the canonical snapshot of an
        identical event.

        Every timestamp in ``docs/reference/examples`` uses the offset form,
        so that is the published contract.  Promoting a core class
        onto the wire must not quietly renegotiate it.
        """
        if value is None:
            return None
        return value.isoformat()

    @model_serializer(mode="wrap")
    def _serialize_with_jsonld_context(
        self,
        handler: SerializerFunctionWrapHandler,
        info: SerializationInfo,
    ) -> Any:
        """Add the JSON-LD ``@context`` on the AS2 path, and only there.

        ADR-0099 detail 1 gives one class two serializations, chosen by where the
        object is going:

        ==========================  ==========================================
        inter-actor delivery        ``model_dump_json(by_alias=True)`` — AS2:
                                    camelCase **plus** ``@context``
        persistence                 ``model_dump(mode="json")`` — Python field
                                    names, no ``@context`` and no computed
                                    fields (CM-31-003); the adapter-layer
                                    ``_rekey_wire_identity()`` then renames
                                    ``id_``/``type_`` → ``id``/``type``
                                    (ARCH-23-005, #3546)
        ==========================  ==========================================

        ``by_alias`` is exactly that fork, so it is what selects the behaviour
        here rather than a flag a caller has to remember to pass.

        VM-10-001 (MUST) requires the Vultron context on Vultron-specific objects;
        the ActivityStreams namespace alone "is not sufficient".  Before ADR-0099
        the paired ``as_*`` class supplied it from ``as_Base``; deleting those
        classes removed it from every promoted type, including nested ones such as
        ``caseParticipants[]``, which is not a change any peer asked for.

        An explicitly-supplied ``context_`` wins, so a document parsed from the
        wire round-trips with the context it arrived with instead of being
        silently relabelled.

        The same fork drops :attr:`local_only_fields` — see that attribute for
        why those cannot simply use ``exclude=True``.
        """
        data = handler(self)
        if not isinstance(data, dict):
            return data
        if not info.by_alias:
            # A computed field is a derived view published on the AS2 path,
            # never stored (CM-31-003): the persistence form carries only the
            # facts it is derived from.
            for name in type(self).model_computed_fields:
                data.pop(name, None)
            return data
        for name in self.local_only_fields:
            data.pop(name, None)
            field = type(self).model_fields.get(name)
            alias = (
                getattr(field, "serialization_alias", None) if field else None
            )
            if alias:
                data.pop(alias, None)
            data.pop(to_camel(name), None)
        for name in self._as2_unpublished_fields():
            data.pop(name, None)
            data.pop(type(self)._computed_field_wire_key(name), None)
        data.update(self._as2_derived_fields())
        data["@context"] = self.context_ or VULTRON_CONTEXT_URI
        return data

    def _as2_unpublished_fields(self) -> frozenset[str]:
        """Return the computed fields this object cannot publish exactly.

        A computed field is a claim about the object.  When the object does
        not carry every input the derivation needs, the AS2 form leaves the
        field out rather than publish a partial value as if it were exact
        (``VulnerabilityCase.active_participants``, CM-31-003).  The default
        publishes every computed field.
        """
        return frozenset()

    def _as2_derived_fields(self) -> dict[str, Any]:
        """Return AS2 keys derived from this object for the delivery form.

        The counterpart of :attr:`local_only_fields`: a subclass whose AS2 form
        carries a value core does not store (``CaseActor``'s collection URIs)
        supplies it here, so the derivation lives on the class it describes.
        """
        return {}

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        """Refuse a computed field that declares a field serializer.

        :meth:`_check_computed_field_inputs` derives a computed field's JSON
        form from its return type, because the persistence dump omits it
        (CM-31-003) and core does not render the AS2 dump itself
        (ARCH-20-001).  A field serializer would make the published form
        differ from that derivation, and the object would refuse its own
        dump (ARCH-23-005), so it is refused when the class is defined.
        """
        super().__pydantic_init_subclass__(**kwargs)
        computed = set(cls.model_computed_fields)
        serialized = {
            field
            for decorator in cls.__pydantic_decorators__.field_serializers.values()
            for field in decorator.info.fields
        }
        if clash := sorted(computed & serialized):
            raise TypeError(
                f"{cls.__name__}: computed field(s) {clash} declare a field"
                " serializer; derive the published value in the property"
                " instead (ARCH-23-005)"
            )

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)  # type: ignore[arg-type]
        # Register only subclasses that override ``type_`` with a concrete
        # (non-union) annotation — e.g. ``type_: Literal["FooBar"] = "FooBar"``.
        # We inspect the subclass's *own* ``__annotations__`` so an inheriting
        # class that does not redeclare ``type_`` (e.g. a behavioral mixin)
        # is not registered. We then resolve the annotation through
        # ``typing.get_type_hints`` so the check is robust under
        # ``from __future__ import annotations`` (PEP 563), where raw
        # annotations are stringified and ``isinstance(..., UnionType)``
        # would silently fall through and register abstract bases.
        own_annotations = inspect.get_annotations(cls)
        if "type_" not in own_annotations:
            # No explicit type_ annotation: _set_type_from_class_name will set
            # type_ = cls.__name__ at construction time, so register by class
            # name so that find_in_vocabulary can reconstruct from DB storage.
            # This fires for abstract intermediate subclasses too — any
            # CoreObject subclass that never overrides type_ registers here,
            # making find_in_vocabulary('ClassName') succeed even for abstract
            # bases.  Intentional: _set_type_from_class_name runs on all such
            # subclasses, so every registered name is a valid stored type_.
            CORE_TYPE_MAP[cls.__name__] = cls
            return  # Skip CORE_VOCABULARY — not a concrete vocab entry
        try:
            hints = _typing.get_type_hints(cls)
        except (NameError, TypeError):
            # Forward references cannot be resolved yet (NameError) or an
            # annotation is not a valid type (TypeError) — do not register.
            # Silent registration of a half-constructed class is worse than a
            # missing entry, which surfaces immediately at lookup time.  Kept
            # symmetric with CoreRecord.__init_subclass__, which runs the
            # same get_type_hints(cls) call for every CoreObject subclass; a
            # divergent catch here would let one handler swallow what the other
            # crashes on (CS-23-001).
            return
        annotation = hints.get("type_")
        # Skip union annotations (e.g. ``str | None``) — these mark
        # intermediate abstract bases, not concrete vocabulary entries.
        if isinstance(annotation, _types.UnionType):
            return
        if _typing.get_origin(annotation) is _typing.Union:
            return
        CORE_VOCABULARY[cls.__name__] = cls

    @model_validator(mode="before")
    @classmethod
    def _set_type_from_class_name(cls, data: Any) -> Any:
        # The bare root is the extractor's minimal reference wrapper: its type is
        # whatever the referenced object's was, and "CoreObject" is never one.
        if cls is CoreObject:
            return data
        if (
            isinstance(data, dict)
            and not data.get("type")
            and not data.get("type_")
        ):
            field_info = cls.model_fields.get("type_")
            if field_info is not None and field_info.default is None:
                data = dict(data)
                data["type"] = cls.__name__
        return data
