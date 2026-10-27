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

"""``CaseOpenToExternalWritesNode``: the post-close write boundary (CM-23-013)."""

from unittest.mock import patch

import py_trees
import pytest
from py_trees.common import Status

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
)
from test.support.case_owner import CASE_OWNER_ID
from test.support.ledger import commit_case_manager_closure
from test.support.received import extract_stamped
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.post_close import (
    CaseOpenToExternalWritesNode,
    case_is_fully_closed,
)
from vultron.wire.as2.factories import add_note_to_case_activity
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

MANAGER = "https://example.org/actors/pc-manager"
OTHER = "https://example.org/actors/pc-participant"
CASE_ID = "https://example.org/cases/pc-case"


def _store(actor_id: str, closed: bool) -> SqliteDataLayer:
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
    case = as_VulnerabilityCase(
        attributed_to=CASE_OWNER_ID, id_=CASE_ID, name="post-close"
    )
    seed_case_manager_participant(dl, case, MANAGER)
    dl.create(case)
    if closed:
        commit_case_manager_closure(dl, CASE_ID)
    return dl


def _late_note_event():
    note = as_Note(id_="https://example.org/notes/pc", content="late")
    activity = add_note_to_case_activity(
        note,
        target=as_VulnerabilityCase(attributed_to=CASE_OWNER_ID, id_=CASE_ID),
        actor=OTHER,
    )
    return extract_stamped(activity)


def _run(dl: SqliteDataLayer, actor_id: str, case_id: str | None = None):
    node = CaseOpenToExternalWritesNode(case_id=case_id)
    tree = py_trees.composites.Sequence(
        name="Probe", memory=False, children=[node]
    )
    result = BTBridge(datalayer=dl).execute_with_setup(
        tree=tree, actor_id=actor_id, activity=_late_note_event()
    )
    return node, result


@pytest.mark.spec("CM-23-013")
def test_refuses_at_the_case_manager_of_a_closed_case() -> None:
    """The tree names its case, as every tree with a commit stage does."""
    node, _ = _run(_store(MANAGER, closed=True), MANAGER, case_id=CASE_ID)
    assert node.status == Status.FAILURE
    assert node.refused_case_id == CASE_ID
    assert "CM-23-013" in node.feedback_message


@pytest.mark.spec("CM-23-013")
def test_resolves_the_case_from_the_activity_when_the_tree_names_none() -> (
    None
):
    """``Add(Note, target=Case)`` names its case only as the target."""
    node, _ = _run(_store(MANAGER, closed=True), MANAGER, case_id=None)
    assert node.status == Status.FAILURE


@pytest.mark.spec("CM-23-013")
def test_passes_on_an_open_case() -> None:
    node, _ = _run(_store(MANAGER, closed=False), MANAGER, case_id=CASE_ID)
    assert node.status == Status.SUCCESS


@pytest.mark.spec("CM-23-013")
def test_passes_on_a_replica_of_a_closed_case() -> None:
    node, _ = _run(_store(OTHER, closed=True), OTHER, case_id=CASE_ID)
    assert node.status == Status.SUCCESS


@pytest.mark.spec("CM-23-013")
def test_passes_when_the_store_holds_no_such_case() -> None:
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=MANAGER)
    node, _ = _run(dl, MANAGER)
    assert node.status == Status.SUCCESS


@pytest.mark.spec("CM-23-013")
def test_a_store_error_does_not_admit() -> None:
    """ "Could not tell" fails the whole tree; it never returns SUCCESS."""
    dl = _store(MANAGER, closed=True)
    with patch.object(
        SqliteDataLayer, "list_objects", side_effect=RuntimeError("boom")
    ):
        node, result = _run(dl, MANAGER)
    assert node.status != Status.SUCCESS
    assert result.status == Status.FAILURE


@pytest.mark.spec("CM-23-013")
def test_case_is_fully_closed_reads_only_the_named_case() -> None:
    dl = _store(MANAGER, closed=True)
    case = dl.read_case(CASE_ID)
    assert case is not None
    assert case_is_fully_closed(dl, case)
    other = as_VulnerabilityCase(
        attributed_to=CASE_OWNER_ID,
        id_="https://example.org/cases/other",
        name="other",
    )
    seed_case_manager_participant(dl, other, MANAGER)
    dl.create(other)
    assert not case_is_fully_closed(dl, other)


@pytest.mark.spec("CM-23-013")
def test_a_case_naming_no_case_manager_records_no_closure() -> None:
    """The ledger holds a CASE_MANAGER closure entry, but the case read no
    longer names a CASE_MANAGER, so there is no one to key the boundary on."""
    dl = _store(MANAGER, closed=True)
    held = dl.read_case(CASE_ID)
    assert held is not None and case_is_fully_closed(dl, held)
    unmanaged = held.model_copy(
        update={"case_participants": [], "actor_participant_index": {}}
    )
    assert not case_is_fully_closed(dl, unmanaged)
