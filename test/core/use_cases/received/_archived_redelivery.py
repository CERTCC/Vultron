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
"""The event the inbox routes for a redelivery of an archived activity.

A received act that fails keeps only intake's archive of the activity
(CLP-07-015).  The inbox routes a later delivery of the same id as the copy
intake archived, carrying the archived body as its received evidence
(IE-10-001, VM-08-002), never the resent bytes.  A test of "a redelivery
after a rollback commits" builds its redelivery here, so it cannot pass only
because the resend carries its own evidence.
"""

import inspect
from typing import Any, TypeVar

from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.adapters.inbox_staging import InlineObjectStaging
from vultron.core.models.events import AnyReceivedEvent
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.use_case_result import HandlerResult
from vultron.semantic_registry import extract_event, use_case_map


def archived_redelivery(
    dl: Any, activity_id: str, **update: Any
) -> AnyReceivedEvent:
    """The event the inbox dispatches for a redelivery of *activity_id*.

    The copy routed is the one intake archived in *dl*, rebuilt as the
    ingress adapter rebuilds it (``InlineObjectStaging.rehydrate_archived``).
    *update* overrides event fields, such as ``receiving_actor_id``.
    """
    record = dl.read(ReceivedActivityRecord.build_id(activity_id))
    assert isinstance(record, ReceivedActivityRecord), (
        f"intake archived no {activity_id!r}"
    )
    routed = InlineObjectStaging(dl).rehydrate_archived(activity_id)
    assert routed is not None, f"{activity_id!r} could not be rebuilt"
    event = extract_event(routed)
    assert event.received_evidence == record.received_body, (
        "the redelivery carries the archived body as its evidence"
    )
    return event.model_copy(update=update) if update else event


_E = TypeVar("_E")


def archived_redelivery_as(
    dl: Any, activity_id: str, event_type: type[_E], **update: Any
) -> _E:
    """:func:`archived_redelivery`, checked to be an *event_type* event."""
    event = archived_redelivery(dl, activity_id, **update)
    assert isinstance(event, event_type), type(event).__name__
    return event


def route_archived_redelivery(
    dl: Any, activity_id: str, *, receiving_actor_id: str
) -> HandlerResult:
    """Route the redelivery of *activity_id* to its use case, as the inbox does.

    The use case is looked up by the routed event's semantics; it gets the
    real ports, built over *dl*, that it declares.
    """
    event = archived_redelivery(
        dl, activity_id, receiving_actor_id=receiving_actor_id
    )
    use_case_class = use_case_map()[event.semantic_type]
    ports: dict[str, Any] = {
        "sync_port": SyncActivityAdapter(dl),
        "trigger_activity": TriggerActivityAdapter(dl),
        "wire_render_port": As2WireRenderAdapter(),
    }
    accepted = inspect.signature(use_case_class).parameters
    result = use_case_class(
        dl, event, **{k: v for k, v in ports.items() if k in accepted}
    ).execute()
    assert isinstance(result, HandlerResult)
    return result
