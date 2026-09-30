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

"""Narrowing accessors for the optional payloads of trigger results.

``ActivityResult.activity`` and ``NoteResult.note`` are ``None`` when the BT
captured nothing (UCORG-05-005), so a happy-path test that reads into them
first asserts they are present.  These helpers make that one assertion and
return the payload typed as a ``dict``, so the test body indexes it without a
repeated ``assert ... is not None`` and the type checkers see the narrowing.
"""

from typing import Any

from vultron.core.models.use_case_result import ActivityResult, NoteResult


def activity_of(result: ActivityResult) -> dict[str, Any]:
    """Return the emitted activity of *result*, failing if none was captured."""
    assert (
        result.activity is not None
    ), f"{type(result).__name__} captured no activity"
    return result.activity


def note_of(result: NoteResult) -> dict[str, Any]:
    """Return the minted note of *result*, failing if none was captured."""
    assert result.note is not None, "NoteResult captured no note"
    return result.note
