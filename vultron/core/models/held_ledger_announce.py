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
"""Where a held out-of-order ``Announce(CaseLedgerEntry)`` waits (SYNC-14).

A participant that receives an ``Announce(CaseLedgerEntry)`` it cannot apply
yet (a forward gap, SYNC-14-001; a case not yet seeded, SYNC-15-004; or an
entry the case is not yet at, ADR-0124) holds the ``Announce`` it received,
not the entry inside it: the received body sits in a
:class:`~vultron.core.models.deferred_inbox_activity.DeferredInboxActivity`,
the record the inbox replays a held activity from (IO-03-004).  When the
entry's predecessor commits, or the case is seeded, that very ``Announce`` is
replayed through the inbox as a delivery of its own (SYNC-14-009).  Nothing
is rebuilt and nothing is attributed to a sender who did not send it.

This record is the index that finds it: one row per held ``Announce``, keyed
by the receiver from the entry's case and ``prev_log_hash``, so the successor
of a new chain tail is one read (:meth:`HeldLedgerAnnounce.build_id`).  It
holds no entry and no body, only what the drain and the size bound read
(SYNC-14-006), and the id of the held ``Announce``.  It is not a
``CaseLedgerEntry``, so the presence of a ``CaseLedgerEntry`` still means
"committed and effects applied" (SYNC-13-001, SYNC-14-005).
"""

from __future__ import annotations

import urllib.parse
from typing import Any, Literal

from pydantic import Field, model_validator

from vultron.core.models.base import (
    CoreRecord,
    NonEmptyString,
    UriString,
    with_record_id,
)


class HeldLedgerAnnounce(CoreRecord):
    """One held ``Announce(CaseLedgerEntry)``, found by its entry's predecessor.

    Attributes:
        case_id: The case the held entry belongs to.
        prev_log_hash: The held entry's ``prev_log_hash``: the chain tail it
            waits for.
        log_index: The held entry's position, read by the size bound.
        entry_hash: The held entry's own hash, which tells a duplicate from a
            fork under the same predecessor.
        entry_id: The held entry's id, for the log.
        activity_id: The sender's id for the held ``Announce``; its received
            body is held under ``DeferredInboxActivity.build_id`` of it.
    """

    type_: Literal["HeldLedgerAnnounce"] = Field(  # type: ignore[assignment]
        default="HeldLedgerAnnounce",
        validation_alias="type",
        serialization_alias="type",
    )
    case_id: UriString = Field(..., description="URI of the entry's case")
    prev_log_hash: NonEmptyString = Field(
        ..., description="The chain tail the held entry extends"
    )
    log_index: int = Field(..., ge=0, description="The held entry's index")
    entry_hash: NonEmptyString = Field(
        ..., description="The held entry's own hash"
    )
    entry_id: UriString = Field(..., description="The held entry's id")
    activity_id: UriString = Field(
        ..., description="The sender's id for the held Announce"
    )

    @classmethod
    def build_id(cls, case_id: str, prev_log_hash: str) -> str:
        """The receiver's id for what waits on *prev_log_hash* in *case_id*."""
        case_slug = urllib.parse.quote(case_id, safe="")
        hash_slug = urllib.parse.quote(prev_log_hash, safe="")
        return f"held-ledger-announce/{case_slug}/{hash_slug}"

    @model_validator(mode="before")
    @classmethod
    def _set_id(cls, data: Any) -> Any:
        """Compute ``id_`` deterministically from the case and predecessor."""
        if isinstance(data, dict):
            case_id = data.get("case_id")
            prev_log_hash = data.get("prev_log_hash")
            if case_id is not None and prev_log_hash is not None:
                data = with_record_id(
                    data, cls.build_id(case_id, prev_log_hash)
                )
        return data


__all__ = ["HeldLedgerAnnounce"]
