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

"""Assert that an ``Add(Note)`` carries its note inline (VAM-01-010).

Every emitter in this codebase sends a note on the single ``Add(Note)`` that
attaches it, with the case as ``target`` and the full note as ``object``
(#4706).  Each emitter's test checks the sealed outbound body through this one
helper, so the check reads the same everywhere.  A note the CASE_MANAGER
writes itself is not sent but committed (#4829):
:func:`assert_case_manager_note_recorded` checks its entry instead.
"""

from typing import Any, cast

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.outbox_sealed_body import (
    SealStore,
    read_sealed_body_dict,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry


def assert_add_note_carries_note_inline(
    dl: SealStore, activity_id: str, case_id: str
) -> dict[str, Any]:
    """Assert *activity_id*'s sealed body is an inline ``Add(Note)`` to *case_id*.

    Returns the inline note, so a caller can check its content.
    """
    body = read_sealed_body_dict(dl, activity_id)
    assert body is not None, f"'{activity_id}' was never sealed"
    assert body["type"] == "Add"
    assert body["target"] == case_id
    note = body["object"]
    assert isinstance(note, dict), (
        f"Add(Note) must carry the note inline, not {note!r} (VAM-01-010)"
    )
    assert note["type"] == "Note"
    assert note.get("id")
    assert note.get("content")
    return note


def assert_case_manager_note_recorded(
    dl: SqliteDataLayer, case_id: str
) -> dict[str, Any]:
    """Assert *dl*'s CASE_MANAGER recorded exactly one note on *case_id*.

    The note is the CASE_MANAGER's own ``add_note_to_case`` entry, an
    ``Add(Note)`` carrying the note inline and addressed to nobody; the note
    is attached to the case, and no ``Add(Note)`` is queued for delivery:
    the ledger fan-out is its delivery (CLP-10-001, SYNC-02-002).  Returns
    the inline note.
    """
    entries = [
        e
        for e in dl.list_objects("CaseLedgerEntry")
        if isinstance(e, CaseLedgerEntry)
        and e.case_id == case_id
        and e.semantic_type == "add_note_to_case"
    ]
    assert len(entries) == 1, [e.log_object_id for e in entries]
    body = entries[0].payload_snapshot
    assert body["type"] == "Add"
    assert body["target"] == case_id
    assert not body.get("to"), body.get("to")
    note = body["object"]
    assert isinstance(note, dict) and note["type"] == "Note", note
    assert note.get("content")
    case = cast(VulnerabilityCase, dl.read(case_id))
    assert note["id"] in [_as_id(n) for n in case.notes]
    for activity_id in dl.outbox_list():
        queued = read_sealed_body_dict(dl, activity_id) or {}
        assert queued.get("type") != "Add", (
            f"'{activity_id}' sends the note directly"
        )
    return cast(dict[str, Any], note)
