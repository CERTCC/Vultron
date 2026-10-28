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

"""Tests for the ADR-0140 label check's rehydration against a store.

A ledger snapshot keeps a nested object bare where its sender named it
(CLP-07-006), and a bare object satisfies no ``object_`` type (SE-01-006),
so the label differs with and without the store that holds the object.
"""

from typing import Any

import pytest

from test.support import ledger_labels
from test.support.ledger_labels import label_mismatch, registry_label
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.note import VultronNote

_CASE = "https://example.org/cases/case-1"
_NOTE = "https://example.org/notes/note-1"


def _add_note_snapshot() -> dict[str, Any]:
    """An ``Add(Note)`` whose note is named by its bare id."""
    return {
        "type": "Add",
        "id": "https://example.org/activities/add-note-1",
        "published": "2026-10-28T12:00:00Z",
        "actor": "https://example.org/actors/vendor",
        "object": _NOTE,
        "target": _CASE,
    }


def _store_holding_the_note() -> SqliteDataLayer:
    dl = SqliteDataLayer(
        "sqlite:///:memory:", actor_id="https://example.org/actors/cm"
    )
    dl.create(VultronNote(id_=_NOTE, content="a note", context=_CASE))
    return dl


@pytest.mark.spec("SE-01-006")
@pytest.mark.spec("CLP-07-006")
def test_a_bare_object_is_labelled_after_rehydrating_against_the_store():
    snapshot = _add_note_snapshot()

    assert (
        registry_label(snapshot)
        == MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT.value
    )
    assert (
        registry_label(snapshot, _store_holding_the_note())
        == MessageSemantics.ADD_NOTE_TO_CASE.value
    )


@pytest.mark.spec("CLP-02-014")
def test_label_mismatch_passes_the_store_through():
    label = MessageSemantics.ADD_NOTE_TO_CASE.value
    snapshot = _add_note_snapshot()

    assert label_mismatch(label, snapshot, _store_holding_the_note()) is None
    assert label_mismatch(label, snapshot) is not None


def test_a_payload_rehydrated_to_a_non_activity_is_refused(monkeypatch):
    monkeypatch.setattr(
        ledger_labels,
        "rehydrate",
        lambda _activity, _dl: VultronNote(id_=_NOTE, content="x"),
    )

    with pytest.raises(TypeError, match="not an activity"):
        registry_label(_add_note_snapshot(), _store_holding_the_note())
