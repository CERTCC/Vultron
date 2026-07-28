"""ActivityPattern class and field-matching helper for the Vultron wire layer.

Defines the pattern model used to match AS2 activities against semantic
dispatch entries. This is the primitive building block imported by both
``_instances.py`` (pattern objects) and ``vultron.semantic_registry``
(ordering guard and registry entries).
"""

from typing import Optional, Union

from pydantic import BaseModel

from vultron.core.models.actor import CoreActor
from vultron.core.models.embargo_event import EmbargoEvent as CoreEmbargoEvent
from vultron.core.models.enums import VultronObjectType as VOtype
from vultron.wire.as2.enums import (
    as_IntransitiveActivityType as IAtype,
    as_ObjectType as AOtype,
    as_TransitiveActivityType as TAtype,
)
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

    description: Optional[str] = None
    activity_: TAtype | IAtype
    strict: bool = False

    to_: Optional[Union[AOtype, VOtype, "ActivityPattern"]] = None
    object_: Optional[Union[AOtype, VOtype, "ActivityPattern"]] = None
    target_: Optional[Union[AOtype, VOtype, "ActivityPattern"]] = None
    context_: Optional[Union[AOtype, VOtype, "ActivityPattern"]] = None
    in_reply_to_: Optional["ActivityPattern"] = None

    def match(self, activity: as_Activity) -> bool:
        """Return True if the given activity matches this pattern."""
        if self.activity_ != activity.type_:
            return False

        # object_ strictness is per-pattern (self.strict).  Strict patterns
        # reject bare string refs; permissive patterns (default) accept them.
        # context_, to_, target_ are always permissive: string URIs (e.g.
        # case context URIs) are intentional and accepted as valid matches.
        field_pairs = (
            (self.object_, getattr(activity, "object_", None), self.strict),
            (self.target_, getattr(activity, "target", None), False),
            (self.context_, getattr(activity, "context", None), False),
            (self.to_, getattr(activity, "to", None), False),
            (
                self.in_reply_to_,
                getattr(activity, "in_reply_to", None),
                self.strict,
            ),
        )
        return all(
            _match_activity_field(pattern_field, activity_field, strict)
            for pattern_field, activity_field, strict in field_pairs
        )


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
