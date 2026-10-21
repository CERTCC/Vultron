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

"""Load a received activity from the body the receiver archived (ADR-0149).

A receiver holds a received activity as the body that arrived, as the parser
sealed it, and nothing derived from it (CLP-10-017, VM-08-002): intake's
``ReceivedActivityRecord``, or the ``DeferredInboxActivity`` that holds it
while the inbox waits on its case.  Both are keyed by the receiver
(DL-06-006).  Every reader loads that body, through one of two loads:

- :func:`load_received_view` is core's.  It runs the body through what the
  inbox ran at delivery: the parse, the staged rebuild that resolves its
  references, and the semantic extraction.  Core gets the extracted activity
  as a read-only view (``ReceivedActivityView``), through
  the ``ReceivedActivityLoader`` port.
- :func:`read_received_as_received` and :func:`read_held_as_received` are the
  reply seam's (DL-06-004).  They parse the body and return the parsed AS2
  activity, sealed with that body as its received evidence, so a reply
  embeds the activity as its sender sent it (``as_answered``).

Nothing here writes: the staged rebuild happens in a throwaway store, as at
delivery, and the archive is left as it was.
"""

import json
from typing import cast

from vultron.adapters.inbox_staging import (
    InlineObjectStaging,
)
from vultron.core.models.deferred_inbox_activity import DeferredInboxActivity
from vultron.core.models.protocols import PersistableModel
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.received_activity_view import ReceivedActivityView
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.errors import VultronNotFoundError
from vultron.semantic_registry import extract_received_activity
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

__all__ = [
    "load_received_view",
    "parse_received_body",
    "read_held_as_received",
    "read_received_as_received",
]


def parse_received_body(received_body: str) -> as_Activity:
    """The activity *received_body* holds, parsed as the inbox parsed it.

    The parse seals the body as the activity's received evidence, so the
    result carries exactly the archived text (VM-08-002).
    """
    return parse_activity(json.loads(received_body))


def _archive(
    dl: CasePersistence, activity_id: str
) -> ReceivedActivityRecord | DeferredInboxActivity | None:
    """The receiver-keyed record holding the received *activity_id*, if any.

    Intake's archive first, then the record that holds a deferred activity
    for its replay; never a row under the id the sender chose (DL-06-006).
    """
    record = dl.read(ReceivedActivityRecord.build_id(activity_id))
    if isinstance(record, ReceivedActivityRecord):
        return record
    deferred = dl.read(DeferredInboxActivity.build_id(activity_id))
    if isinstance(deferred, DeferredInboxActivity):
        return deferred
    return None


def _parsed(dl: CasePersistence, activity_id: str) -> as_Activity | None:
    """The held received *activity_id* as its body parses, if held.

    An activity deferred as a storage row has no body, so it is rebuilt from
    that row, carrying no received evidence (VM-08-002).
    """
    record = _archive(dl, activity_id)
    if record is None:
        return None
    if record.received_body is not None:
        return parse_received_body(record.received_body)
    return InlineObjectStaging(cast(DataLayer, dl)).rehydrate_held(activity_id)


def load_received_view(
    dl: CasePersistence, activity_id: str
) -> ReceivedActivityView | None:
    """Core's read-only view of the received *activity_id*, or ``None``.

    The held body is parsed, rebuilt with its inline objects staged in a
    throwaway store that reads through to *dl*, and extracted, as the inbox
    did at delivery (ADR-0149).  The view is built fresh on every call, so
    nothing a reader does to one reaches the next.
    """
    record = _archive(dl, activity_id)
    if record is None:
        return None
    staging = InlineObjectStaging(cast(DataLayer, dl))
    routed: as_Activity | None
    if record.received_body is not None:
        parsed = parse_received_body(record.received_body)
        routed = staging.rehydrate_parsed(parsed) or parsed
    else:
        routed = staging.rehydrate_held(activity_id)
    if routed is None:  # pragma: no cover - the record was just read
        return None
    return ReceivedActivityView(extract_received_activity(routed))


def read_received_as_received(
    dl: CasePersistence, activity_id: str, resource_type: str = "Activity"
) -> as_Activity:
    """The received *activity_id*, parsed from the body this receiver holds.

    For a reply that answers an activity the actor received (DL-06-004).

    Raises:
        VultronNotFoundError: When this store holds no such activity.
    """
    parsed = _parsed(dl, activity_id)
    if parsed is None:
        raise VultronNotFoundError(resource_type, activity_id)
    return parsed


def read_held_as_received(
    dl: CasePersistence, activity_id: str, resource_type: str = "Activity"
) -> as_Activity | PersistableModel:
    """The activity *activity_id* as this actor holds it, received or sent.

    A received activity is parsed from its body
    (:func:`read_received_as_received`).  Anything else is read under its own
    id: an activity this actor sent (DL-06-006).

    Raises:
        VultronNotFoundError: When this store holds no such activity.
    """
    parsed = _parsed(dl, activity_id)
    if parsed is not None:
        return parsed
    held = dl.read(activity_id)
    if held is None:
        raise VultronNotFoundError(resource_type, activity_id)
    return held
