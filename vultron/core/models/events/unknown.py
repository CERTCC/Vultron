"""Per-semantic inbound domain event types for unrecognized activities."""

# pyright: reportGeneralTypeIssues=false
# Rationale: UnresolvableObjectReceivedEvent intentionally narrows the
# optional ``activity`` field from the base class to required.  This is the
# documented pattern for subclasses that always carry an activity.

from typing import Literal

from vultron.core.models.activity import VultronActivity
from vultron.core.models.events.base import MessageSemantics, VultronEvent
from vultron.primitives import NonEmptyString


class UnknownReceivedEvent(VultronEvent):
    """Activity did not match any known semantic pattern."""

    semantic_type: Literal[MessageSemantics.UNKNOWN] = MessageSemantics.UNKNOWN


class UnresolvableObjectReceivedEvent(VultronEvent):
    """Activity matched a known type but object_ URI could not be resolved.

    The ``activity`` field is required (narrowed from the optional base field)
    because the dead-letter use case needs the full activity snapshot to
    build the dead-letter record.

    ``unresolved_object_id`` is the bare id that ends the activity's
    ``object`` chain, at whatever depth: the object the receiver lacks and
    fetches (VAM-01-009, AKM-05-007).
    """

    semantic_type: Literal[MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT] = (
        MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT
    )
    activity: VultronActivity  # required: narrowed from Optional
    unresolved_object_id: NonEmptyString
