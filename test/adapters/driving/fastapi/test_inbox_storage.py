#!/usr/bin/env python
"""
Unit tests for vultron.adapters.driving.fastapi.inbox_storage.

Tests the ingress storage helpers in isolation from the HTTP layer. They were
tested under ``routers/actors/test_inbox.py`` until #3705 moved them out of
the router package.
"""

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

import pytest

from vultron.adapters.driving.fastapi.inbox_storage import (
    _store_inbox_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Create,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

_ACTOR_URI = "https://example.org/actors/alice"


# ---------------------------------------------------------------------------
# _store_inbox_activity
# ---------------------------------------------------------------------------


def test_store_inbox_activity_persists_activity(datalayer):
    note = as_Note(content="test")
    activity = as_Create(actor=_ACTOR_URI, object_=note)
    _store_inbox_activity(datalayer, activity)
    stored = datalayer.read(activity.id_)
    assert stored is not None


@pytest.mark.spec("IE-10-001")
def test_store_inbox_activity_is_idempotent(datalayer):
    """Ingress storage is where a redelivery is detected (IE-10-001).

    The second call must not raise, must report that it wrote nothing, and must
    leave the first delivery in place rather than overwriting it.
    """
    note = as_Note(content="test")
    activity = as_Create(actor=_ACTOR_URI, object_=note, summary="first")
    assert _store_inbox_activity(datalayer, activity) is True

    redelivered = activity.model_copy(update={"summary": "second"})
    assert _store_inbox_activity(datalayer, redelivered) is False
    stored = datalayer.read(activity.id_)
    assert getattr(stored, "summary", None) == "first"
