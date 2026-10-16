"""Tests for the shared intake-only received tree (#3871, CLP-10-005).

Every intake-only received handler builds this tree, so its outcome is pinned
here once: intake archives the activity, and nothing else is written.
"""

import pytest
from py_trees.common import Status

from test.core.behaviors.case.note_delivery import add_note_delivery
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.intake_only_received_tree import (
    create_incomplete_activity_received_tree,
    create_intake_only_received_tree,
)
from vultron.core.behaviors.case.nodes.incomplete_activity import (
    ActivityIncompleteNode,
)
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)


@pytest.mark.spec("CLP-10-018")
@pytest.mark.spec("CLP-07-013")
def test_archives_the_activity_and_stores_nothing_else(datalayer, actor_id):
    """Intake archives the delivery; the object it carries is not stored.

    Storing a case record is a change to the case file, which needs its own
    committed entry (CLP-07-013), so the intake-only tree never stores the
    inline object it is handed (#4598).
    """
    note, activity, event = add_note_delivery()

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


@pytest.mark.spec("CLP-10-005")
@pytest.mark.spec("CLP-10-018")
def test_incomplete_activity_tree_archives_then_refuses(datalayer, actor_id):
    """The refusal of an incomplete activity is a guard after intake (#4643).

    The tree fails on ``ActivityIncompleteNode`` with its reason, after intake
    archived the activity, and commits or stores nothing else.
    """
    note, activity, event = add_note_delivery()

    tree = create_incomplete_activity_received_tree(
        "IncompleteTest", "Add(Note) carries no note object"
    )
    result = BTBridge(datalayer=datalayer).execute_with_setup(
        tree=tree, actor_id=actor_id, activity=event
    )

    assert result.status == Status.FAILURE
    guard = tree.children[-1]
    assert isinstance(guard, ActivityIncompleteNode)
    assert guard.status == Status.FAILURE
    assert guard.feedback_message == "Add(Note) carries no note object"
    assert (
        datalayer.read(ReceivedActivityRecord.build_id(activity.id_))
        is not None
    )
    assert datalayer.read(note.id_) is None
    assert datalayer.list_objects("CaseLedgerEntry") == []
