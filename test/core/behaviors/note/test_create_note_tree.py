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

"""Tests for create_note_tree factory."""

import pytest
from py_trees.common import Status

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.addressee import (
    ActivityAddressedToReceiverNode,
)
from vultron.core.behaviors.case.nodes.intake import (
    IntakeReceivedActivityNode,
)
from vultron.core.behaviors.case.nodes.post_close import (
    CaseOpenToExternalWritesNode,
)
from vultron.core.behaviors.case.nodes.role_gates import CaseManagerGate
from vultron.core.behaviors.note.create_note_tree import create_note_tree
from vultron.core.behaviors.note.nodes import (
    AttachNoteToCaseNode,
    SaveNoteNode,
)
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.note import VultronNote
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.use_cases.received.note import CreateNoteReceivedUseCase
from vultron.semantic_registry import extract_event
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Create,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

ACTOR_ID = "https://example.org/actors/finder"
CASE_ID = "https://example.org/cases/case-01"
NOTE_ID = "https://example.org/notes/note-01"


@pytest.fixture
def dl():
    return SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id=ACTOR_ID,
    )


@pytest.fixture
def bridge(dl):
    # A note naming a case is committed at its CASE_MANAGER (CLP-07-013), so
    # the bridge carries the ports the commit needs.
    return BTBridge(
        datalayer=dl,
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    )


@pytest.fixture
def note():
    return VultronNote(
        id_=NOTE_ID,
        content="Test note content",
    )


@pytest.fixture
def note_with_case():
    return VultronNote(
        id_=NOTE_ID,
        content="Test note content",
        context=CASE_ID,
    )


def _create_note_event(note: VultronNote):
    """The extracted ``Create(Note)`` event that carries *note*'s activity."""
    return extract_event(
        as_Create(
            actor=ACTOR_ID,
            object_=as_Note(
                id_=note.id_, content=note.content, context=note.context
            ),
        )
    )


def _tree(note: VultronNote, case_id: str | None):
    """The ``Create(Note)`` tree for a note sent by ``ACTOR_ID``, under the
    use case's declared sender rule (HP-01-008)."""
    return create_note_tree(
        note_obj=note,
        case_id=case_id,
        sender_id=ACTOR_ID,
        sender_rule=CreateNoteReceivedUseCase.sender_entitlement,
    )


def _archived(dl, event) -> bool:
    return (
        dl.read(ReceivedActivityRecord.build_id(event.activity_id)) is not None
    )


@pytest.fixture
def case(dl):
    # RSH-08-003 (#3814): AttachNoteToCaseNode is CASE_MANAGER-gated, so the
    # executing actor (ACTOR_ID, the store owner) must hold the role for the
    # attach to run; attributed_to seeds the CLP-08 genesis anchor.
    obj = as_VulnerabilityCase(
        id_=CASE_ID, name="Test Case", attributed_to=ACTOR_ID
    )
    seed_case_manager_participant(dl, obj, ACTOR_ID)
    dl.create(obj)
    return obj


# ---------------------------------------------------------------------------
# create_note_tree tests
# ---------------------------------------------------------------------------


class TestCreateNoteTree:
    @pytest.mark.spec("CM-02-007")
    def test_saves_note_and_attaches_to_case(
        self, bridge, dl, note_with_case, case
    ):
        event = _create_note_event(note_with_case)
        tree = _tree(note_with_case, CASE_ID)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID, activity=event
        )
        assert result.status == Status.SUCCESS

        stored_note = dl.read(NOTE_ID)
        assert stored_note is not None
        assert _archived(dl, event)

        refreshed_case = dl.read(CASE_ID)
        assert refreshed_case is not None
        assert NOTE_ID in refreshed_case.notes

    @pytest.mark.spec("HP-01-008")
    @pytest.mark.spec("CLP-10-018")
    def test_note_naming_no_case_is_refused(self, bridge, dl, note):
        """No sender has standing outside a case, so a note naming none is
        refused and not stored; the Create is still archived."""
        event = _create_note_event(note)
        tree = _tree(note, None)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID, activity=event
        )
        assert result.status == Status.FAILURE
        assert dl.read(NOTE_ID) is None
        assert _archived(dl, event)

    @pytest.mark.spec("CM-13-007")
    def test_idempotent_replay(self, bridge, dl, note_with_case, case):
        """Running the same tree twice produces the same outcome."""
        event = _create_note_event(note_with_case)
        for _ in range(2):
            tree = _tree(note_with_case, CASE_ID)
            result = bridge.execute_with_setup(
                tree=tree, actor_id=ACTOR_ID, activity=event
            )
            assert result.status == Status.SUCCESS

        refreshed = dl.read(CASE_ID)
        assert refreshed is not None
        assert refreshed.notes.count(NOTE_ID) == 1

    def test_tree_name_is_create_note_bt(self, note, dl):
        tree = _tree(note, None)
        assert tree.name == "CreateNoteBT"

    @pytest.mark.spec("CLP-07-013")
    @pytest.mark.spec("CLP-10-025")
    def test_tree_runs_intake_then_guards_then_commit_then_save_then_attach(
        self, note
    ):
        # RSH-08-003 (#3814): the attach is wrapped in the factory's
        # CASE_MANAGER gate as the last child; the Note object is still saved
        # ungated.  CLP-07-013 (#4441): the attachment is a case-file change,
        # so the CASE_MANAGER commits the Create(Note) first.  The addressee
        # door guard and the sender guard come before both, and with them the
        # embargo end-time check (HP-01-005, HP-01-008, CLP-10-025).
        tree = _tree(note, CASE_ID)
        names = [c.name for c in tree.children]
        assert len(tree.children) == 8
        assert isinstance(tree.children[0], IntakeReceivedActivityNode)
        assert isinstance(tree.children[1], CaseOpenToExternalWritesNode)
        assert isinstance(tree.children[2], ActivityAddressedToReceiverNode)
        assert names[3] == "SenderRuleGuard"
        assert names[4] == "ClockDecisionsIfCaseManager"
        commit = tree.children[5]
        assert isinstance(commit, CaseManagerGate)
        assert commit.name == "GuardedCommitCaseLedgerEntryBT"
        assert isinstance(tree.children[6], SaveNoteNode)
        gate = tree.children[7]
        assert isinstance(gate, CaseManagerGate)
        assert isinstance(gate.gated_branch, AttachNoteToCaseNode)

    def test_note_naming_no_case_has_no_commit(self, note):
        """A note that names no case has no case to commit to: the sender
        guard refuses it (``case_manager_required``), and the tree has no
        commit stage."""
        tree = _tree(note, None)
        assert not any(isinstance(c, CaseManagerGate) for c in tree.children)

    @pytest.mark.spec("CLP-07-013")
    def test_case_manager_commits_the_attachment(
        self, bridge, dl, note_with_case, case
    ):
        """The CASE_MANAGER commits one ``create_note`` entry carrying the
        note, and attaches the note (CLP-07-013, #4441)."""
        event = _create_note_event(note_with_case)
        tree = _tree(note_with_case, CASE_ID)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID, activity=event
        )
        assert result.status == Status.SUCCESS

        entries = [
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry) and e.case_id == CASE_ID
        ]
        assert [e.event_type for e in entries] == ["create_note"]
        snapshot_object = entries[0].payload_snapshot["object"]
        assert isinstance(snapshot_object, dict)
        assert snapshot_object["id"] == NOTE_ID

    @pytest.mark.spec("CLP-10-018")
    @pytest.mark.spec("PCR-03-001")
    def test_unheld_case_refuses_and_archives_the_activity(
        self, bridge, dl, note_with_case
    ):
        """The case is not held, so this store cannot tell the sender is its
        CASE_MANAGER: the Create is refused, archived, and nothing is stored,
        attached or committed (PCR-03-001, CLP-10-018)."""
        event = _create_note_event(note_with_case)
        tree = _tree(note_with_case, CASE_ID)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID, activity=event
        )
        assert result.status == Status.FAILURE
        assert _archived(dl, event)
        assert dl.read(NOTE_ID) is None
        assert dl.read(CASE_ID) is None
        assert dl.list_objects("CaseLedgerEntry") == []
