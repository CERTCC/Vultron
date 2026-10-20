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

"""Attach a note to a case, idempotently (``note/AGENTS.md``).

Idempotency checks the case's ``notes``, never whether the note object
exists: a note can be stored without being attached.
"""

from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.ports.case_persistence import CasePersistence


def note_attached(case: VulnerabilityCase, note_id: str) -> bool:
    """True when *note_id* is already in *case*'s ``notes``."""
    return note_id in [_as_id(n) for n in case.notes]


def attach_note(
    datalayer: CasePersistence, case: VulnerabilityCase, note_id: str
) -> bool:
    """Attach *note_id* to *case* and save it; False if it was attached already."""
    if note_attached(case, note_id):
        return False
    case.notes.append(note_id)
    datalayer.save(case)
    return True


__all__ = ["attach_note", "note_attached"]
