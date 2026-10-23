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

"""Tests for case.nodes.carried_object_case."""

import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.carried_object_case import (
    CarriedObjectInTargetCaseNode,
)
from vultron.core.models.note import VultronNote

ACTOR_ID = "https://example.org/actors/case-manager"
CASE_ID = "https://example.org/cases/case-a"
OTHER_CASE_ID = "https://example.org/cases/case-b"
NOTE_ID = "https://example.org/notes/note-01"


@pytest.fixture
def dl():
    return SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR_ID)


def _run(dl, carried):
    node = CarriedObjectInTargetCaseNode(
        object_id=NOTE_ID, carried=carried, case_id=CASE_ID
    )
    result = BTBridge(datalayer=dl).execute_with_setup(
        tree=node, actor_id=ACTOR_ID
    )
    return node, result.status


@pytest.mark.spec("HP-08-007")
def test_a_carried_object_of_the_target_case_passes(dl):
    _, status = _run(
        dl, VultronNote(id_=NOTE_ID, content="x", context=CASE_ID)
    )
    assert status == Status.SUCCESS


@pytest.mark.spec("HP-08-007")
@pytest.mark.parametrize("context", [OTHER_CASE_ID, None])
def test_a_carried_object_of_another_case_or_none_is_refused(dl, context):
    node, status = _run(
        dl, VultronNote(id_=NOTE_ID, content="x", context=context)
    )
    assert status == Status.FAILURE
    assert "REFUSED" in node.feedback_message


@pytest.mark.spec("HP-08-007")
def test_the_stored_record_is_checked_over_the_carried_copy(dl):
    """The check reads the object the tree attaches: a stored record wins
    over the carried copy, as the inbox rebuild's does (IO-03-004)."""
    dl.create(VultronNote(id_=NOTE_ID, content="x", context=OTHER_CASE_ID))
    node, status = _run(
        dl, VultronNote(id_=NOTE_ID, content="x", context=CASE_ID)
    )
    assert status == Status.FAILURE
    assert OTHER_CASE_ID in node.feedback_message
