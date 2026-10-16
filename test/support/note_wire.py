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

"""Assert that a queued ``Add(Note)`` carries its note inline (VAM-01-010).

Every emitter in this codebase sends a note on the single ``Add(Note)`` that
attaches it, with the case as ``target`` and the full note as ``object``
(#4706).  Each emitter's test checks the sealed outbound body through this one
helper, so the check reads the same everywhere.
"""

from typing import Any

from vultron.adapters.outbox_sealed_body import (
    SealStore,
    read_sealed_body_dict,
)


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
