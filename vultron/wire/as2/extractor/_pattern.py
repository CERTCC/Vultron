"""ActivityPattern class and field-matching helper for the Vultron wire layer.

Defines the pattern model used to match AS2 activities against semantic
dispatch entries. This is the primitive building block imported by both
``_instances.py`` (pattern objects) and ``vultron.semantic_registry``
(ordering guard and registry entries).
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator

from vultron.core.models.actor import CoreActor
from vultron.core.models.enums import VultronObjectType as VOtype
from vultron.wire.as2.enums import (
    as_IntransitiveActivityType as IAtype,
    as_ObjectType as AOtype,
    as_TransitiveActivityType as TAtype,
)
from vultron.wire.as2.typed_reference import (
    as_TypedReference,
    class_named_by,
    is_case_reference,
    is_of_kind,
    is_previewed_reference,
    referenced_class,
)
from vultron.wire.as2.vocab.base.links import as_Link
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.base.objects.collections import as_Collection
from vultron.wire.as2.vocab.base.objects.object_types import as_Event


class ObjectForm(StrEnum):
    """The form an ``ActivityPattern`` may require of its ``object`` (SE-01-009).

    ADR-0198 gives an object slot three forms; ADR-0205 tells two activities
    with objects of the same type apart by form, as received:

    - ``PREVIEWED_REFERENCE``: a typed reference that carries a preview
      (:func:`~vultron.wire.as2.typed_reference.is_previewed_reference`).
    - ``WHOLE_OBJECT``: an inline object that is not a typed reference, a
      case, actor or collection reference, a ``Link`` or a bare URI.
    """

    PREVIEWED_REFERENCE = "previewedReference"
    WHOLE_OBJECT = "wholeObject"


#: The keys an actor or collection reference carries (AKM-05-017, AKM-02-006).
_IDENTITY_FIELDS = frozenset({"id_", "type_", "context_"})


def _names_only_its_identity(value: BaseModel) -> bool:
    """Whether *value* was given no field with a value but its identity."""
    return {
        name
        for name in value.model_fields_set
        if getattr(value, name, None) is not None
    } <= _IDENTITY_FIELDS


def _is_whole_object(value: object) -> bool:
    """Whether *value* is an inline whole object (ADR-0198).

    Not a typed reference (a case reference is one) or a ``Link``, nor an actor or
    collection named by its identity alone: the actor reference
    (AKM-05-017) and an endpoint's address (AKM-02-006) are references too.
    """
    if not isinstance(value, BaseModel) or isinstance(
        value, (as_TypedReference, as_Link)
    ):
        return False
    if isinstance(value, (as_Actor, CoreActor, as_Collection)):
        return not _names_only_its_identity(value)
    return True


def matches_object_form(form: ObjectForm | None, value: object) -> bool:
    """Whether *value*, an activity's ``object``, has the form *form* asks.

    With no form asked, any object but a previewed reference has it: a
    preview is not the object (ADR-0205), so only a pattern that asks for a
    previewed reference routes one, and no other pattern reads it as the
    object (SE-01-009).
    """
    if form is ObjectForm.PREVIEWED_REFERENCE:
        return is_previewed_reference(value)
    if form is ObjectForm.WHOLE_OBJECT:
        return _is_whole_object(value)
    return not is_previewed_reference(value)


class ActivityPattern(BaseModel):
    """Represents a pattern to match against an AS2 activity for semantic dispatch.

    Supports nested patterns for activities whose object is itself an activity.

    ``object_`` is strict: a bare string there (a URI still unresolved
    after rehydration) names an object the receiver does not hold, so its
    type is unknown and it satisfies no scalar ``object_`` constraint
    (SE-01-006).  ``find_matching_semantics()`` then returns
    ``UNKNOWN_UNRESOLVABLE_OBJECT``, which the inbox answers by fetching the
    object (AKM-05-007).  A typed reference, by contrast, carries its type,
    and satisfies a type constraint as the whole object would (MV-10-011).
    No pattern opts out of the bare-URI rule (SE-01-006).

    ``object_form`` constrains the object's form, as received (SE-01-009,
    ADR-0205): a typed reference that carries a preview, or a whole object.
    Two patterns that differ only in it each match only their own form.
    Unset, it admits every form but a previewed reference, which only a
    pattern that asks for one matches: a preview is not the object.

    ``origin_`` matches the activity's ``origin``: where the object comes
    from or leaves, as ``target_`` matches where it goes (a ``Remove`` names
    the collection it takes the object from in ``origin``).  The two are
    matched alike.

    ``strict`` governs ``target_`` and ``origin_`` alone: when True, a bare
    string in ``target`` or ``origin`` does NOT match a scalar constraint on
    that field.  Set it on a pattern whose ``target_`` or ``origin_`` is the
    sole field that tells it apart from a competing pattern (SE-08-004).
    Otherwise ``target_`` and ``origin_``, like ``context_`` and ``to_``,
    accept a bare URI: a case there travels as its URI or a stub by rule
    (SE-01-007).
    """

    # A field no pattern declares is refused, not ignored, so a pattern
    # cannot ask for a rule that does not exist (SE-01-006).
    model_config = ConfigDict(extra="forbid")

    description: str | None = None
    activity_: TAtype | IAtype
    strict: bool = False
    object_form: ObjectForm | None = None

    to_: AOtype | VOtype | ActivityPattern | None = None
    object_: AOtype | VOtype | ActivityPattern | None = None
    target_: AOtype | VOtype | ActivityPattern | None = None
    origin_: AOtype | VOtype | ActivityPattern | None = None
    context_: AOtype | VOtype | ActivityPattern | None = None

    @model_validator(mode="after")
    def _strict_needs_target(self) -> ActivityPattern:
        """Refuse ``strict`` on a pattern with no ``target_`` or ``origin_``."""
        if self.strict and self.target_ is None and self.origin_ is None:
            raise ValueError(
                "strict governs target_ and origin_ alone (SE-08-004); a"
                " pattern with neither has nothing for it to tighten"
            )
        return self

    @model_validator(mode="after")
    def _object_form_needs_an_object_type(self) -> ActivityPattern:
        """Refuse an ``object_form`` no object it could match has.

        A form is a form of a non-activity object (SE-01-009): an inline
        activity is neither a previewed reference nor read by form.
        """
        if self.object_form is None:
            return self
        if isinstance(self.object_, ActivityPattern):
            # Pydantic reports a ValueError raised here as a validation error.
            raise ValueError(  # noqa: TRY004 - Pydantic reports only ValueError
                "object_form constrains a non-activity object (SE-01-009):"
                " a nested activity pattern sets its own"
            )
        return self

    def match(self, activity: as_Activity) -> bool:
        """Return True if the given activity matches this pattern."""
        if self.activity_ != activity.type_:
            return False

        return self.matches_object(
            getattr(activity, "object_", None)
        ) and self._match_qualifiers(activity)

    def matches_object(self, value: object) -> bool:
        """True if *value*, an activity's ``object``, satisfies ``object_``.

        A bare string satisfies no scalar ``object_`` (SE-01-006), and
        *value* must have the form ``object_form`` asks (SE-01-009).
        """
        if not matches_object_form(self.object_form, value):
            return False
        return _match_activity_field(self.object_, value, strict=True)

    def _match_qualifiers(self, activity: as_Activity) -> bool:
        """Match ``target_``, ``origin_``, ``context_`` and ``to_``."""
        field_pairs = (
            (self.target_, getattr(activity, "target", None), self.strict),
            (self.origin_, getattr(activity, "origin", None), self.strict),
            (self.context_, getattr(activity, "context", None), False),
            (self.to_, getattr(activity, "to", None), False),
        )
        return all(
            _match_activity_field(pattern_field, activity_field, strict)
            for pattern_field, activity_field, strict in field_pairs
        )


#: Every activity verb an ``as_Activity`` ``type`` may name.
ACTIVITY_VERBS: frozenset[str] = frozenset(
    str(verb) for verb in (*TAtype, *IAtype)
)


class InlineActivityObjectPattern(ActivityPattern):
    """A pattern whose object is an inline activity of any verb.

    ``ActivityPattern`` nests one verb per pattern; this matches an activity
    whose ``object_`` is an inline activity of *any* verb.  ``object_`` is
    fixed to ``Activity`` so the pattern renders as ``Verb(Activity)``.  A
    bare URI or a non-activity object does not match.  ``target_``,
    ``origin_``, ``context_`` and ``to_`` match as on the base class.

    It is the most general pattern for its verb, so its registry entry comes
    after every pattern that nests a specific activity (SE-03-002).
    """

    object_: AOtype | VOtype | ActivityPattern | None = AOtype.ACTIVITY

    def match(self, activity: as_Activity) -> bool:
        """True if *activity* carries an inline activity."""
        if self.activity_ != activity.type_:
            return False
        obj = getattr(activity, "object_", None)
        if not isinstance(obj, as_Activity):
            return False
        if str(obj.type_) not in ACTIVITY_VERBS:
            return False
        return self._match_qualifiers(activity)


class LedgerPositionReadPattern(ActivityPattern):
    """``Read(<case>/ledger)``: a participant's stated ledger position.

    The object is the case's ledger, an ``OrderedCollection`` named by its
    id and type (ADR-0204).  What makes the ``Read`` a position statement is
    the ``ledgerPosition`` it carries (SYNC-17-001): a ``Read`` without one
    is not matched here.
    """

    def match(self, activity: as_Activity) -> bool:
        if getattr(activity, "ledger_position", None) is None:
            return False
        return super().match(activity)


def _match_activity_field(
    pattern_field: AOtype | VOtype | ActivityPattern | None,
    activity_field: object,
    strict: bool = False,
) -> bool:
    if pattern_field is None:
        return True
    if isinstance(pattern_field, ActivityPattern):
        # Nested Activity patterns (e.g. Accept(Invite(...))): a non-Activity
        # value (including unresolved string refs) cannot structurally match.
        return isinstance(activity_field, as_Activity) and pattern_field.match(
            activity_field
        )
    # Scalar type patterns (VOtype / AOtype).
    # Strict (object_, and target_/origin_ on a strict pattern): a bare string means
    # the reference was not rehydrated, so its type cannot be confirmed and
    # the pattern must NOT match; find_matching_semantics() returns
    # UNKNOWN_UNRESOLVABLE_OBJECT for an unmatched bare object_.
    # Permissive (context_, to_, a lenient target_/origin_): string URIs are
    # intentional (e.g. a case context URI) and match the pattern.
    if activity_field is None:
        return False
    if isinstance(activity_field, str):
        return not strict
    # A typed reference routes by the class its ``type`` names, as a whole
    # object routes by its own (MV-10-011, ADR-0198).  So does an object
    # held only as the generic ``as_Object``, as a nested slot of a plain
    # activity is: an actor in an embargo Invite's ``target`` (ADR-0205)
    # still routes as an actor.
    kind: type | None
    if isinstance(activity_field, as_TypedReference):
        kind = referenced_class(activity_field)
    elif type(activity_field) is as_Object:
        kind = class_named_by(activity_field.type_)
    else:
        kind = type(activity_field)
    if (
        pattern_field == AOtype.ACTOR
        and kind is not None
        and is_of_kind(kind, as_Actor)
    ):
        return True
    if (
        pattern_field == AOtype.EVENT
        and kind is not None
        and is_of_kind(kind, as_Event)
    ):
        return True
    return bool(pattern_field == getattr(activity_field, "type_", None))


def bare_object_id(activity: as_Activity) -> str | None:
    """The bare id that ends *activity*'s ``object`` chain, or ``None``.

    The chain follows ``object`` through each inline activity it holds, so
    ``Undo(Accept(Invite(<id>)))`` ends in the Invite's bare object.  A
    nested pattern's ``object_`` refuses a bare id as the outer one does
    (SE-01-006), so the activity is unresolvable at any depth, and this id is
    the one the receiver lacks (VAM-01-009, AKM-05-007).  A typed reference
    ending the chain names its id the same way: no pattern matched it, so the
    object must be read before the activity can be.  ``None`` when the chain
    ends in an inline whole object, in a case reference, in a typed reference
    that carries a preview, or in no object at all: a case is read from the
    receiver's own store and never fetched (AKM-03-006, ADR-0165), and a
    previewed reference is read as received, and the receiver fetches nothing
    for it (MV-10-011, ADR-0205).
    """
    obj: object = getattr(activity, "object_", None)
    while isinstance(obj, as_Activity):
        obj = getattr(obj, "object_", None)
    if is_case_reference(obj) or is_previewed_reference(obj):
        return None
    if isinstance(obj, as_TypedReference):
        # A reference no pattern matched names an object the receiver must
        # fetch before it can read it, as a bare id does (MV-10-011).
        return obj.id_
    return obj if isinstance(obj, str) and obj else None
