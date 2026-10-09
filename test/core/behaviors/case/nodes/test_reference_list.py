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
"""Case reference-list nodes and the note-author sender guard (#3873)."""

from typing import cast

import pytest
from py_trees.common import Status

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_participant,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.reference_list import (
    AttachReportToCaseNode,
    CaseReferenceEditPendingNode,
)
from vultron.core.behaviors.note.nodes.storage import (
    AttachNoteToCaseNode,
    DetachNoteFromCaseNode,
)
from vultron.core.behaviors.sender_entitlement import SenderIsNoteAuthorNode
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

ACTOR = "https://example.org/actors/manager"
CASE_ID = "https://example.org/cases/ref-list"
REF = "https://example.org/notes/n1"


@pytest.fixture
def dl() -> SqliteDataLayer:
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR)
    case = as_VulnerabilityCase(id_=CASE_ID, name="Refs")
    seed_case_manager_participant(store, case, ACTOR)
    store.create(case)
    return store


def _run(dl, node):
    return BTBridge(
        datalayer=dl, wire_render_port=As2WireRenderAdapter()
    ).execute_with_setup(tree=node, actor_id=ACTOR)


def _case(dl) -> as_VulnerabilityCase:
    return cast(as_VulnerabilityCase, dl.read(CASE_ID))


def test_attach_and_detach_note_are_idempotent(dl):
    for _ in range(2):
        assert (
            _run(dl, AttachNoteToCaseNode(REF, CASE_ID)).status
            == Status.SUCCESS
        )
    assert list(_case(dl).notes) == [REF]
    for _ in range(2):
        assert (
            _run(dl, DetachNoteFromCaseNode(REF, CASE_ID)).status
            == Status.SUCCESS
        )
    assert list(_case(dl).notes) == []


def test_attach_report_adds_to_vulnerability_reports(dl):
    report = "https://example.org/reports/r1"

    assert (
        _run(dl, AttachReportToCaseNode(report, CASE_ID)).status
        == Status.SUCCESS
    )
    assert list(_case(dl).vulnerability_reports) == [report]


def test_edit_without_a_case_id_is_a_noop(dl):
    assert _run(dl, AttachNoteToCaseNode(REF, None)).status == Status.SUCCESS


@pytest.mark.parametrize(
    "attach,present,passes",
    [
        (True, False, True),
        (True, True, False),
        (False, True, True),
        (False, False, False),
    ],
)
def test_pending_guard_distinguishes_duplicates(dl, attach, present, passes):
    if present:
        case = _case(dl)
        case.notes.append(REF)
        dl.save(case)
    node = CaseReferenceEditPendingNode(REF, CASE_ID, "notes", attach)

    result = _run(dl, node)

    assert (result.status == Status.SUCCESS) is passes
    assert node.is_duplicate is (not passes)


def test_pending_guard_for_unknown_case_is_not_a_duplicate(dl):
    node = CaseReferenceEditPendingNode(
        REF, "https://example.org/cases/none", "notes", True
    )

    assert _run(dl, node).status == Status.FAILURE
    assert node.is_duplicate is False


@pytest.mark.spec("CM-30-001")
@pytest.mark.parametrize(
    "note_author,sender,participant,passes",
    [
        (
            "https://example.org/a/author",
            "https://example.org/a/author",
            True,
            True,
        ),
        (
            "https://example.org/a/author",
            "https://example.org/a/author",
            False,
            False,
        ),
        (
            "https://example.org/a/author",
            "https://example.org/a/other",
            True,
            False,
        ),
        (None, "https://example.org/a/author", True, False),
    ],
)
def test_note_author_guard(dl, note_author, sender, participant, passes):
    note = as_Note(id_=REF, content="x", attributed_to=note_author)
    dl.create(note)
    if participant:
        case = _case(dl)
        seed_case_participant(dl, case, sender)
        dl.save(case)

    result = _run(dl, SenderIsNoteAuthorNode(REF, sender, CASE_ID))

    assert (result.status == Status.SUCCESS) is passes


def test_note_author_guard_for_unknown_note_fails(dl):
    sender = "https://example.org/a/author"
    case = _case(dl)
    seed_case_participant(dl, case, sender)
    dl.save(case)

    result = _run(dl, SenderIsNoteAuthorNode(REF, sender, CASE_ID))

    assert result.status == Status.FAILURE
