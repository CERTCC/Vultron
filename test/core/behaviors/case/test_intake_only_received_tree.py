"""Tests for the shared intake-only received tree (#3871, CLP-10-005).

Every intake-only received handler builds this tree, so its outcome is pinned
here once: intake archives the activity, and nothing else is written.
"""

import pytest
from py_trees.common import Status

from test.core.behaviors.case.note_delivery import create_note_delivery
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.intake_only_received_tree import (
    create_intake_only_received_tree,
)
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)


@pytest.mark.spec("CLP-10-018")
@pytest.mark.spec("CLP-07-013")
def test_archives_the_activity_and_stores_nothing_else(datalayer, actor_id):
    """Intake archives the delivery; the object it carries is not stored.

    A ``Create(X)`` of a case record is a change to the case file, which needs
    its own committed entry (CLP-07-013), so the intake-only tree never stores
    it (#4598).
    """
    note, activity, event = create_note_delivery()

    tree = create_intake_only_received_tree("IntakeOnlyTest")
    result = BTBridge(datalayer=datalayer).execute_with_setup(
        tree=tree, actor_id=actor_id, activity=event
    )

    assert result.status == Status.SUCCESS
    assert (
        datalayer.read(ReceivedActivityRecord.build_id(activity.id_))
        is not None
    )
    assert datalayer.read(note.id_) is None
    assert datalayer.list_objects("CaseLedgerEntry") == []
