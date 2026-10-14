"""Tests for the shared intake-only received tree (#3871, CLP-10-005).

Every intake-only received handler builds this tree, so its outcome is pinned
here once: intake archives the activity, and nothing else is written.
"""

import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.store_only_received_tree import (
    create_store_only_received_tree,
)
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.semantic_registry import extract_event
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Create,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

_RECEIVER = "https://example.org/actors/receiver"
_SENDER = "https://example.org/actors/sender"
_CASE_ID = "https://example.org/cases/store-only"


@pytest.fixture
def dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER)


def _create_note():
    note = as_Note(
        id_=f"{_CASE_ID}/notes/n1",
        name="store-only",
        content="a note",
        context=_CASE_ID,
    )
    activity = as_Create(actor=_SENDER, object_=note, context=_CASE_ID)
    return note, activity, extract_event(activity)


@pytest.mark.spec("CLP-10-018")
@pytest.mark.spec("CLP-07-013")
def test_archives_the_activity_and_stores_nothing_else(dl):
    """Intake archives the delivery; the object it carries is not stored.

    A ``Create(X)`` of a case record is a change to the case file, which needs
    its own committed entry (CLP-07-013), so the intake-only tree never stores
    it (#4598).
    """
    note, activity, event = _create_note()

    tree = create_store_only_received_tree("StoreOnlyTest")
    result = BTBridge(datalayer=dl).execute_with_setup(
        tree=tree, actor_id=_RECEIVER, activity=event
    )

    assert result.status == Status.SUCCESS
    assert dl.read(ReceivedActivityRecord.build_id(activity.id_)) is not None
    assert dl.read(note.id_) is None
    assert dl.list_objects("CaseLedgerEntry") == []
