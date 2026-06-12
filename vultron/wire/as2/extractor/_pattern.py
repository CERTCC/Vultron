"""ActivityPattern class and field-matching helper for the Vultron wire layer.

Defines the pattern model used to match AS2 activities against semantic
dispatch entries. This is the primitive building block imported by both
``_instances.py`` (pattern objects) and ``vultron.semantic_registry``
(ordering guard and registry entries).
"""

from typing import Optional, Union

from pydantic import BaseModel

from vultron.core.models.actor import CoreActor
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
    """

    description: Optional[str] = None
    activity_: TAtype | IAtype

    to_: Optional[Union[AOtype, VOtype, "ActivityPattern"]] = None
    object_: Optional[Union[AOtype, VOtype, "ActivityPattern"]] = None
    target_: Optional[Union[AOtype, VOtype, "ActivityPattern"]] = None
    context_: Optional[Union[AOtype, VOtype, "ActivityPattern"]] = None
    in_reply_to_: Optional["ActivityPattern"] = None

    def match(self, activity: as_Activity) -> bool:
        """Return True if the given activity matches this pattern."""
        if self.activity_ != activity.type_:
            return False

        field_pairs = (
            (self.object_, getattr(activity, "object_", None)),
            (self.target_, getattr(activity, "target", None)),
            (self.context_, getattr(activity, "context", None)),
            (self.to_, getattr(activity, "to", None)),
            (self.in_reply_to_, getattr(activity, "in_reply_to", None)),
        )
        return all(
            _match_activity_field(pattern_field, activity_field)
            for pattern_field, activity_field in field_pairs
        )


def _match_activity_field(
    pattern_field: AOtype | VOtype | ActivityPattern | None,
    activity_field: object,
) -> bool:
    if pattern_field is None:
        return True
    if isinstance(pattern_field, ActivityPattern):
        return isinstance(activity_field, as_Activity) and pattern_field.match(
            activity_field
        )
    if isinstance(activity_field, str):
        return True
    if activity_field is None:
        return False
    if pattern_field == AOtype.ACTOR and isinstance(
        activity_field, (as_Actor, CoreActor)
    ):
        return True
    if pattern_field == AOtype.EVENT and isinstance(activity_field, as_Event):
        return True
    return bool(pattern_field == getattr(activity_field, "type_", None))
