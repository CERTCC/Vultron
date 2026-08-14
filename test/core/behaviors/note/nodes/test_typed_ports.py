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

"""Typed-Ports isolation tests for note domain nodes (AC-4, issue #1883).

Covers BTND-03-011 (NoDataAvailable on missing required port) and happy-path
execution via BTTestScenario for one representative node per note sub-module.
"""

import pytest
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.note.nodes.creation import (
    CreateNoteNode,
)
from vultron.core.behaviors.note.nodes.storage import (
    AttachNoteToCaseNode,
    SaveNoteNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.note import VultronNote
from test.core.behaviors.bt_harness import BTTestScenario

ACTOR_ID = "https://example.org/actors/vendor"
CASE_ID = "https://example.org/cases/case-001"
NOTE_ID = "https://example.org/notes/note-001"


# ---------------------------------------------------------------------------
# storage.py — SaveNoteNode (isolated-port: BTND-03-011)
# ---------------------------------------------------------------------------


class TestSaveNoteNodePorts:
    def test_missing_datalayer_raises_no_data_available(self) -> None:
        note = VultronNote(
            id_=NOTE_ID,
            name="Test Note",
            content="test content",
            context=CASE_ID,
            attributed_to=ACTOR_ID,
        )
        node = SaveNoteNode(note_obj=note)
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_saves_note_via_bt_scenario(
        self, bt_scenario: BTTestScenario
    ) -> None:
        note = VultronNote(
            id_=NOTE_ID,
            name="Test Note",
            content="test content",
            context=CASE_ID,
            attributed_to=ACTOR_ID,
        )
        result = bt_scenario.run(
            SaveNoteNode(note_obj=note), actor_id=ACTOR_ID
        )
        bt_scenario.assert_success(result)


# ---------------------------------------------------------------------------
# creation.py — CreateNoteNode (isolated-port: BTND-03-011)
# ---------------------------------------------------------------------------


class TestCreateNoteNodePorts:
    def test_missing_datalayer_raises_no_data_available(self) -> None:
        result_out: dict = {}
        node = CreateNoteNode(
            note_name="N",
            note_content="c",
            case_id=CASE_ID,
            result_out=result_out,
        )
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")


# ---------------------------------------------------------------------------
# storage.py — AttachNoteToCaseNode (isolated-port: BTND-03-011)
# ---------------------------------------------------------------------------


class TestAttachNoteToCaseNodePorts:
    def test_missing_datalayer_raises_no_data_available(self) -> None:
        node = AttachNoteToCaseNode(note_id=NOTE_ID, case_id=CASE_ID)
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_skips_when_case_id_none(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Skips silently (SUCCESS) when case_id is None."""
        result = bt_scenario.run(
            AttachNoteToCaseNode(note_id=NOTE_ID, case_id=None),
            actor_id=ACTOR_ID,
        )
        bt_scenario.assert_success(result)

    def test_attaches_note_to_case(self, bt_scenario: BTTestScenario) -> None:
        case = VulnerabilityCase(
            id_=CASE_ID,
            name="Test Case",
            attributed_to=ACTOR_ID,
        )
        note = VultronNote(
            id_=NOTE_ID,
            name="Test Note",
            content="test content",
            context=CASE_ID,
            attributed_to=ACTOR_ID,
        )
        bt_scenario.seed(case, note)
        result = bt_scenario.run(
            AttachNoteToCaseNode(note_id=NOTE_ID, case_id=CASE_ID),
            actor_id=ACTOR_ID,
        )
        bt_scenario.assert_success(result)
