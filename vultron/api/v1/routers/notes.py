#!/usr/bin/env python
"""
Vultron API Routers
"""

#  Copyright (c) 2025 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
from fastapi import APIRouter

from vultron.as_vocab.activities.case import AddNoteToCase
from vultron.as_vocab.base.objects.object_types import as_Note
from vultron.scripts import vocab_examples

router = APIRouter(prefix="/notes", tags=["notes"])


@router.get(
    "/example",
    response_model=as_Note,
    response_model_exclude_none=True,
    description="Get an example Note object.",
    tags=["examples"],
)
def get_example_note() -> as_Note:
    """
    Get an example Note object
    """
    return vocab_examples.note()


@router.post(
    "/validate",
    response_model=as_Note,
    response_model_exclude_none=True,
    summary="Validate Note object format",
    description="Validates a Note object.",
)
def validate_note(note: as_Note) -> as_Note:
    """Validates a Note object."""
    return note


@router.put(
    "/{id}/cases/{case_id}",
    response_model=AddNoteToCase,
    response_model_exclude_none=True,
    summary="Add Note to Case",
    description="Adds a Note to an existing Vulnerability Case.",
)
def add_note_to_case(id: str, case_id: str) -> AddNoteToCase:
    """Adds a Note to an existing Vulnerability Case."""
    return vocab_examples.add_note_to_case()
