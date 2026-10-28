"""ActivityPattern class and field-matching helper for the Vultron wire layer.

Defines the pattern model used to match AS2 activities against semantic
dispatch entries. This is the primitive building block imported by both
``_instances.py`` (pattern objects) and ``vultron.semantic_registry``
(ordering guard and registry entries).
"""

from typing import Union

from pydantic import BaseModel, Field

from vultron.core.models.actor import CoreActor
from vultron.core.models.embargo_event import EmbargoEvent as CoreEmbargoEvent
from vultron.core.models.enums import VultronObjectType as VOtype
from vultron.wire.as2.enums import (
    as_IntransitiveActivityType as IAtype,
    as_ObjectType as AOtype,
    as_TransitiveActivityType as TAtype,
)
from vultron.wire.as2.ledger_reject_envelope import is_genesis_replay_reject
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.object_types import as_Event


class ActivityPattern(BaseModel):
    """Represents a pattern to match against an AS2 activity for semantic dispatch.

    Supports nested patterns for activities whose object is itself an activity.

    ``strict``: when True, a bare string in ``object_`` (an unresolved URI
    reference) will NOT match a scalar VOtype/AOtype pattern.  Use this when
    the activity type has competing scalar and nested-activity patterns for
    ``object_`` so that an unresolved reference cannot be wrongly dispatched.
    Defaults to False for backward compatibility with patterns that rely on
    URI-string ``object_`` values (e.g. ``Reject(CaseLedgerEntry)``).
    """

    description: str | None = None
    activity_: TAtype | IAtype
    strict: bool = False

    to_: Union[AOtype, VOtype, "ActivityPattern"] | None = None
    object_: Union[AOtype, VOtype, "ActivityPattern"] | None = None
    target_: Union[AOtype, VOtype, "ActivityPattern"] | None = None
    context_: Union[AOtype, VOtype, "ActivityPattern"] | None = None

    def match(self, activity: as_Activity) -> bool:
        """Return True if the given activity matches this pattern."""
        if self.activity_ != activity.type_:
            return False

        # object_ strictness is per-pattern (self.strict).  Strict patterns
        # reject bare string refs; permissive patterns (default) accept them.
        # context_ and to_ are always permissive: string URIs (e.g. case
        # context URIs) are intentional and accepted as valid matches.
        # target_ follows self.strict (permissive by default).
        return _match_activity_field(
            self.object_, getattr(activity, "object_", None), self.strict
        ) and self._match_qualifiers(activity)

    def _match_qualifiers(self, activity: as_Activity) -> bool:
        """Match ``target_``, ``context_`` and ``to_`` against *activity*."""
        field_pairs = (
            (self.target_, getattr(activity, "target", None), self.strict),
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
    """A pattern whose object is an inline activity of any verb but a few.

    ``ActivityPattern`` nests one verb per pattern; this matches an activity
    whose ``object_`` is an inline activity of *any* verb outside
    ``excluded_object_verbs``.  ``object_`` is fixed to ``Activity`` so the
    pattern renders as ``Verb(Activity)``.  A bare URI, a non-activity
    object, or an activity of an excluded verb does not match.  ``target_``,
    ``context_`` and ``to_`` match as on the base class.

    It is the most general pattern for its verb, so its registry entry comes
    after every pattern that nests a specific activity (SE-03-002).
    """

    object_: Union[AOtype, VOtype, "ActivityPattern"] | None = AOtype.ACTIVITY
    excluded_object_verbs: frozenset[TAtype | IAtype] = Field(
        default_factory=frozenset
    )

    def match(self, activity: as_Activity) -> bool:
        """True if *activity* carries an inline activity of an included verb."""
        if self.activity_ != activity.type_:
            return False
        obj = getattr(activity, "object_", None)
        if not isinstance(obj, as_Activity):
            return False
        verb = str(obj.type_)
        excluded = {str(v) for v in self.excluded_object_verbs}
        if verb not in ACTIVITY_VERBS or verb in excluded:
            return False
        return self._match_qualifiers(activity)


class LedgerEntryRejectPattern(ActivityPattern):
    """``Reject(CaseLedgerEntry)``, or the objectless genesis-replay form.

    Matches what the base pattern matches, and also a plain ``Reject`` that
    names no entry, states the empty chain's position and names the case
    as its ``target``: a replica with no stored entry asking for a replay
    from genesis (SYNC-16-007).  The parser refuses any other ``Reject``
    without an object, so nothing else reaches the second branch.
    """

    def match(self, activity: as_Activity) -> bool:
        if super().match(activity):
            return True
        return is_genesis_replay_reject(activity)


class LedgerPositionReadPattern(ActivityPattern):
    """``Read(CaseLedgerEntry)``: a participant's stated ledger position.

    The entry goes by reference (SYNC-17-001), and the receiver may not hold
    it, so a bare id in ``object_`` matches as the base pattern lets it.
    What makes the ``Read`` a position statement is the ``ledgerPosition``
    it carries: a ``Read`` without one is not matched here, so an
    acknowledgment ``Read`` whose object did not resolve is never read as a
    ledger position.
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
    # In strict mode (object_ field): a bare string means the reference was
    # not rehydrated — we cannot confirm the type, so the pattern must NOT
    # match.  find_matching_semantics() returns UNKNOWN_UNRESOLVABLE_OBJECT.
    # In permissive mode (context_, to_, target_): string URIs are intentional
    # (e.g. a case context URI) and are accepted as matching the pattern.
    if activity_field is None:
        return False
    if isinstance(activity_field, str):
        return not strict
    if pattern_field == AOtype.ACTOR and isinstance(
        activity_field, (as_Actor, CoreActor)
    ):
        return True
    if pattern_field == AOtype.EVENT and isinstance(
        activity_field, (as_Event, CoreEmbargoEvent)
    ):
        return True
    return bool(pattern_field == getattr(activity_field, "type_", None))
