#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

from vultron.wire.as2.vocab.activities.case import AddNoteToCaseActivity
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Create
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.examples._base import (
    base_url,
    case,
    finder,
    vendor,
)


def note() -> as_Note:
    _case = case()
    _note = as_Note(
        name="Note",
        id=f"{base_url}/notes/1",
        content="This is a note.",
        context=_case.as_id,
    )
    return _note


def add_note_to_case() -> AddNoteToCaseActivity:
    _finder = finder()
    _case = case()
    _note = note()
    _note.context = _case.as_id

    activity = AddNoteToCaseActivity(
        actor=_finder.as_id,
        object=_note,
        target=_case.as_id,
    )

    return activity


def create_note():
    _case = case()
    _note = note()
    _vendor = vendor()
    activity = as_Create(
        actor=_vendor.as_id,
        object=_note,
        target=_case.as_id,
    )
    return activity
