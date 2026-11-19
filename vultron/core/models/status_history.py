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

"""The named status histories a status ``Add`` extends (ADR-0204).

Each ``CaseParticipant`` has its statuses at ``<participant>/statuses`` and
the case has its own at ``<case>/statuses``: both are ``OrderedCollection``
identities whose newest item is the current status.  They are identity only,
so no route serves them.  A status is ``Add(ParticipantStatus,
target=<participant>/statuses)`` or ``Add(CaseStatus,
target=<case>/statuses)``, with ``context`` the case.

The history's id is its owner's id with :data:`STATUS_HISTORY_SUFFIX`
appended, so the record a status is added to is read from the ``target``
itself.  Both sides build and read it only through these functions.
"""

from typing import TypeGuard

#: What a record's id gains to name its status history (ADR-0204).
STATUS_HISTORY_SUFFIX = "/statuses"


def status_history_id(owner_id: str) -> str:
    """The id of the status history of the record *owner_id* names.

    Raises:
        ValueError: When *owner_id* is empty, or is itself a history.
    """
    if not owner_id:
        raise ValueError("a status history needs a non-empty owner id")
    if is_status_history_id(owner_id):
        raise ValueError(
            f"'{owner_id}' is already a status history, not its owner"
        )
    return f"{owner_id}{STATUS_HISTORY_SUFFIX}"


def is_status_history_id(ref: object) -> TypeGuard[str]:
    """Whether *ref* is a status history id with a non-empty owner."""
    return (
        isinstance(ref, str)
        and ref.endswith(STATUS_HISTORY_SUFFIX)
        and len(ref) > len(STATUS_HISTORY_SUFFIX)
    )


def status_history_owner(history_id: str) -> str:
    """The id of the record whose status history *history_id* is.

    Raises:
        ValueError: When *history_id* is not a status history id.
    """
    if not is_status_history_id(history_id):
        raise ValueError(f"'{history_id}' is not a status history id")
    return history_id[: -len(STATUS_HISTORY_SUFFIX)]


def status_history_owner_or_none(ref: object) -> str | None:
    """The owner of *ref* when it is a status history id, else ``None``.

    For a reader of a received ``target``, which may name no history at
    all: the caller decides what an absent owner means.
    """
    return status_history_owner(ref) if is_status_history_id(ref) else None


__all__ = [
    "STATUS_HISTORY_SUFFIX",
    "is_status_history_id",
    "status_history_owner_or_none",
    "status_history_id",
    "status_history_owner",
]
