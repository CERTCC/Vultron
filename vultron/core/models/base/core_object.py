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

"""The one AS2 object root of the core domain model, :class:`CoreObject`.

ARCH-25-004 (ADR-0099): the core classes *are* the AS2 objects.
"""

import inspect
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import (
    Annotated,
    Any,
    ClassVar,
    TypeAlias,
    get_args,
    get_origin,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainValidator,
    SerializationInfo,
    SerializeAsAny,
    SerializerFunctionWrapHandler,
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
    absent_times_as_none,
    as_utc,
    blank_times_as_none,
    format_timestamp,
    refuse_absent_id,
    refuse_absent_published,
)
from vultron.core.models.base._computed import (
    check_computed_field_inputs,
    computed_field_spellings,
    refuse_computed_field_serializers,
)
from vultron.core.models.base.context import (
    JsonLdContext,
    is_default_jsonld_context,
    serialize_with_top_level_context,
)
from vultron.core.models.base.language_map import (
    LanguageMap,
    language_map_field,
)
from vultron.core.models.base.record import (
    CoreRecord,
    concrete_type_annotation,
)
from vultron.core.models.registry import CORE_TYPE_MAP, CORE_VOCABULARY
from vultron.primitives import NonEmptyString


class CoreObject(CoreRecord):
    """The one AS2 object root of the Vultron core domain model.

    ARCH-25-004 (ADR-0099): under one object model the core classes *are* the AS2
    objects, so this root carries the AS2 object fields, the JSON-LD
    ``@context`` and the timestamps, on top of the identity from
    :class:`CoreRecord`.  Its ``by_alias`` dump is the AS2 wire form.

    The AS2 fields core does not use (``bto``, ``bcc``, ``generator``,
    ``icon``, ``image``, …) stay declared on purpose: a declared-but-unused
    field is a *recognised* field core ignores, whereas an undeclared one
    would be an unrecognised field rejected on every message carrying it
    (ARCH-25-007, ARCH-25-008; ADR-0099).

    A bare ``CoreObject(id_=..., type_=...)`` is the minimal reference the
    extractor wraps an otherwise-unmodelled object in; it keeps the ``type_``
    it was given, including ``None``.

    Subclasses that override ``type_`` with a concrete (non-union)
    annotation — e.g. ``type_: Literal["VulnerabilityCase"] = ...`` —
    register themselves in :data:`CORE_VOCABULARY` via
    ``__init_subclass__``.  Subclasses that leave ``type_`` abstract
    (omitted, or annotated as a union) are intentionally not registered.

    ``context_`` defaults to ``None`` (the default list) and is
    ``exclude=True``, so it never reaches a stored row: ARCH-25-001 (ADR-0099)
    keeps persistence on Python field names with no ``@context``.  It is
    emitted only on the AS2 path, on the top-level document — see
    :meth:`_serialize_with_jsonld_context`.
    """

    # The AS2 spelling of every field, derived rather than hand-maintained.
    #
    # ARCH-25-002 (ADR-0099) puts the AS2 spelling on the core class, because under one
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
    # empty baseline of `by_alias=True` calls (ARCH-12-013, ARCH-20-001).
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

    preview: NonEmptyString | None = None
    media_type: NonEmptyString | None = None
    # The AS2 reference properties hold an embedded object or a non-blank IRI,
    # one or many (``replies`` one only), as on the wire base.  Core names only
    # its own objects; a wire ``Link`` or case stub is held as the wire layer
    # built it (``UnmodelledObject``, ARCH-01-001).  A blank IRI is refused
    # when the object is built (CS-08-001, #3894).  The aliases are declared
    # below the class they name.
    replies: "CoreObjectOrIri | None" = None
    url: NonEmptyString | None = None
    generator: "CoreObjectOrIriValues" = None
    context: "CoreObjectOrIriValues" = None
    tag: "CoreObjectOrIriValues" = None
    in_reply_to: "CoreObjectOrIriValues" = None
    duration: timedelta | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None

    # Required, with no default: an object this process authors states the
    # instant of the act that made it (ADR-0176), and an object it *receives*
    # carries the sender's time, which AS2 lets the sender omit, so a received
    # omission is read as ``None`` (``_carry_absent_times_on_inbound``) rather
    # than becoming the receiver's clock (ISSUE-3257).  Decisions that need
    # the time refuse its absence at the wire edge, not here.
    published: datetime | None
    updated: datetime | None
    #: Set by a subclass whose received ``published`` a decision reads, so
    #: :meth:`_carry_absent_times_on_inbound` refuses its absence (CLP-15-010).
    _inbound_requires_published: ClassVar[bool] = False

    content: NonEmptyString | None = None
    summary: NonEmptyString | None = None
    icon: "CoreObjectOrIriValues" = None
    image: "CoreObjectOrIriValues" = None
    attachment: "CoreObjectOrIriValues" = None
    location: "CoreObjectOrIriValues" = None
    to: "CoreObjectOrIriValues" = None
    cc: "CoreObjectOrIriValues" = None
    bto: "CoreObjectOrIriValues" = None
    bcc: "CoreObjectOrIriValues" = None
    audience: "CoreObjectOrIriValues" = None
    attributed_to: NonEmptyString | None = None
    # The natural-language map forms of ``content``, ``name`` and ``summary``
    # (AS2 Core section 4.7), declared so the parse edge reads them rather
    # than setting them aside (ARCH-25-008).  Empty by default; an empty map
    # is left out of every dump.
    content_map: LanguageMap = language_map_field()
    name_map: LanguageMap = language_map_field()
    summary_map: LanguageMap = language_map_field()

    context_: JsonLdContext | None = Field(
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
        persistence dump omits it (CM-31-014,
        :meth:`_serialize_with_jsonld_context`).
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
        return check_computed_field_inputs(cls, data, handler)

    @classmethod
    def _computed_field_wire_key(cls, name: str) -> str:
        """The key computed field *name* is emitted under in the AS2 dump."""
        alias = getattr(cls.model_computed_fields[name], "alias", None)
        return alias if isinstance(alias, str) else to_camel(name)

    @classmethod
    def _computed_field_spellings(cls) -> dict[str, str]:
        """Map every key spelling a computed field can arrive under to its name."""
        return computed_field_spellings(cls)

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
        needed for the same reason (ISSUE-3257, ADR-0103): an object this
        process authors states its time (ADR-0176), and a received one that
        omits it claimed none, so the omission must read as ``None``.  Under
        ARCH-25-003 (ADR-0099) an inbound ``CaseParticipant``, ``EmbargoEvent`` or
        ``VulnerabilityCase`` validates straight into this class rather than a
        wire subclass of ``as_Base``, so without this the rule silently stops
        holding for every collapsed type.  Gated on the same validation-context
        key, which ``parse_activity`` sets and Pydantic propagates to nested
        models.

        A class whose ``published`` a decision reads sets
        ``_inbound_requires_published``, and a received instance without one
        is refused here with :class:`MissingClaimedTimeError` rather than
        read as ``None`` (CLP-15-007, CLP-15-010).  A received instance
        without an ``id`` is refused too, never given a minted one
        (OID-01-013, OID-01-014).
        """
        if not isinstance(data, dict):
            return data
        context = info.context
        if not isinstance(context, dict) or not context.get(
            INBOUND_CONTEXT_KEY
        ):
            return data
        if cls._inbound_requires_published:
            refuse_absent_published(cls, data)
        refuse_absent_id(cls, data)
        return absent_times_as_none(cls, blank_times_as_none(cls, dict(data)))

    @field_validator("context_")
    @classmethod
    def _default_context_as_absent(
        cls, value: JsonLdContext | None
    ) -> JsonLdContext | None:
        """Read the default ``@context`` list back as no override.

        The AS2 serializer emits ``self.context_`` or, on a top-level document,
        the default list (``DEFAULT_JSONLD_CONTEXT``), so ``None`` and that list
        dump identically.  Keeping the supplied default would make every
        ``by_alias`` dump validate into an object unequal to the one dumped
        (ARCH-23-005, CM-31-021).  A non-default context — a single string,
        another list, or the same entries in another order — is kept, so a
        document parsed from the wire still dumps with the context it arrived
        with.
        """
        return None if is_default_jsonld_context(value) else value

    @field_validator("start_time", "end_time", "published", "updated")
    @classmethod
    def _normalise_datetime_to_utc(
        cls, value: datetime | None
    ) -> datetime | None:
        """Read a naive timestamp as UTC; leave an absent one absent.

        The core twin of ``as_Object.validate_datetime`` (CS-13-001, CM-28-006,
        #3784).  Under ARCH-25-003 (ADR-0099) an inbound ``EmbargoEvent``,
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
        """Write timestamps in the one fixed form, as the wire classes do.

        Pydantic's default JSON form for an aware UTC datetime is ``...Z``,
        with a fraction only when the microseconds are not zero;
        :func:`format_timestamp` gives ``....000000+00:00``.  Both denote the
        same instant and both are valid ISO-8601, which is why swapping them
        is invisible in review — but they are different *bytes*, and
        ``CaseLedgerEntry.payloadSnapshot`` is compared across replicas, so two
        actors on different spellings disagree about the canonical snapshot of
        an identical event (CS-13-007, ADR-0167).

        Every timestamp in ``docs/reference/examples`` uses the fixed form,
        so that is the published contract.  Promoting a core class
        onto the wire must not quietly renegotiate it.
        """
        if value is None:
            return None
        return format_timestamp(value)

    @model_serializer(mode="wrap")
    def _serialize_with_jsonld_context(
        self,
        handler: SerializerFunctionWrapHandler,
        info: SerializationInfo,
    ) -> Any:
        """Add the JSON-LD ``@context`` on the AS2 path, and only there.

        ARCH-25-001 (ADR-0099) gives one class two serializations, chosen by where the
        object is going:

        ==========================  ==========================================
        inter-actor delivery        ``model_dump_json(by_alias=True)`` — AS2:
                                    camelCase **plus** ``@context``
        persistence                 ``model_dump(mode="json")`` — Python field
                                    names, no ``@context`` and no computed
                                    fields (CM-31-014); the adapter-layer
                                    ``_rekey_wire_identity()`` then renames
                                    ``id_``/``type_`` → ``id``/``type``
                                    (ARCH-23-005, #3546)
        ==========================  ==========================================

        ``by_alias`` is exactly that fork, so it is what selects the behaviour
        here rather than a flag a caller has to remember to pass.

        VM-10-001 (MUST) puts the two-entry ``@context`` list — AS2 first, then
        the Vultron context — on the top-level document, and an object nested
        inside it does not restate it
        (:func:`~vultron.core.models.base.context.serialize_with_top_level_context`).
        A core object dumped on its own is a top-level document, so it carries
        the list.

        An explicitly-supplied ``context_`` wins, so a document parsed from the
        wire round-trips with the context it arrived with instead of being
        silently relabelled.
        """
        if not info.by_alias:
            data = handler(self)
            if isinstance(data, dict):
                # A computed field is a derived view published on the AS2
                # path, never stored (CM-31-014): the persistence form
                # carries only the facts it is derived from.
                for name in type(self).model_computed_fields:
                    data.pop(name, None)
            return data
        return serialize_with_top_level_context(
            lambda: self._drop_unpublished(handler(self)), info, self.context_
        )

    def _drop_unpublished(self, data: Any) -> Any:
        """Remove the computed fields this object cannot publish exactly."""
        if not isinstance(data, dict):
            return data
        for name in self._as2_unpublished_fields():
            data.pop(name, None)
            data.pop(type(self)._computed_field_wire_key(name), None)
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

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        """Refuse a computed field that declares a field serializer.

        :meth:`_check_computed_field_inputs` derives a computed field's JSON
        form from its return type, because the persistence dump omits it
        (CM-31-014) and core does not render the AS2 dump itself
        (ARCH-20-001).  A field serializer would make the published form
        differ from that derivation, and the object would refuse its own
        dump (ARCH-23-005), so it is refused when the class is defined.
        """
        super().__pydantic_init_subclass__(**kwargs)
        refuse_computed_field_serializers(cls)

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
        # Kept symmetric with CoreRecord.__init_subclass__, which resolves the
        # same annotation through the same helper, so one hook cannot swallow
        # what the other crashes on (CS-23-001).  A union annotation (e.g.
        # ``str | None``) marks an intermediate abstract base, not a concrete
        # vocabulary entry.
        if concrete_type_annotation(cls) is None:
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


def _require_built_object(value: object) -> BaseModel:
    """Admit *value* only if it is an object another layer already built."""
    if isinstance(value, BaseModel):
        return value
    raise ValueError(
        "an AS2 reference must be an embedded object or a non-blank IRI"
    )


#: An embedded object of a class core does not model (an AS2 ``Link``, a case
#: stub, a case reference), held as the wire layer built it.  Core cannot name
#: those classes (ARCH-01-001), yet the parse edge must keep one in a core
#: object until its placement check names the fault (MV-10-002, AKM-03-004).
#: Only a built model passes; a raw mapping must validate as a ``CoreObject``.
#: ``SerializeAsAny`` dumps it by its own class, not as a bare ``BaseModel``.
UnmodelledObject: TypeAlias = Annotated[
    SerializeAsAny[BaseModel], PlainValidator(_require_built_object)
]

#: One value of an AS2 reference property as core holds it: an embedded
#: object or a non-blank IRI (CS-08-001).
CoreObjectOrIri: TypeAlias = CoreObject | UnmodelledObject | NonEmptyString

#: A non-functional AS2 reference property: one value or a list of them.
#: ``Sequence`` rather than ``list``, because ``list`` is invariant: a
#: subclass narrowing ``to`` to ``list[NonEmptyString]`` is then a valid
#: override.
CoreObjectOrIriValues: TypeAlias = (
    CoreObjectOrIri | Sequence[CoreObjectOrIri] | None
)

# The fields above name these aliases, which name the class, so the schema is
# completed here, before any subclass is declared.
CoreObject.model_rebuild()


def _holds_unmodelled_object(annotation: object) -> bool:
    """Return whether *annotation* admits an :data:`UnmodelledObject`."""
    if get_origin(annotation) is Annotated and any(
        isinstance(meta, PlainValidator) and meta.func is _require_built_object
        for meta in getattr(annotation, "__metadata__", ())
    ):
        return True
    return any(_holds_unmodelled_object(arg) for arg in get_args(annotation))


def unmodelled_object_fields(cls: type[BaseModel]) -> frozenset[str]:
    """Fields of *cls* that may hold an object core does not model.

    A reader that rebuilds a stored row must build such a value as its own
    class first: its stored mapping (a Link's ``href``, say) is not a
    ``CoreObject``, and the slot admits only a built model.
    """
    return frozenset(
        name
        for name, field in cls.model_fields.items()
        if _holds_unmodelled_object(field.annotation)
    )
