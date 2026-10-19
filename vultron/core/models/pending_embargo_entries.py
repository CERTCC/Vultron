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

"""The entries an embargo act still owes, stored before its first commit.

One embargo act commits several entries: its own, then one CASE_MANAGER
entry per consent row it changes (CLP-07-013).  The CASE_MANAGER decides
every entry before the first commit.  When a later commit fails, the act is
left with only some of its entries, and a later run must commit the rest
exactly as decided, never decide them again (CLP-07-015, ADR-0146).

:class:`PendingEmbargoEntries` is the record that carries that decision
across runs.  It is case bookkeeping (CLP-07-014): it is not ledgered, not
replicated and not part of the case file.  A later run reads it only to
commit the entries already decided, unchanged, and never to decide a
case-file value.  It is stored before the act's first commit and removed
once the act's last entry is committed and applied.
"""

import urllib.parse
from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from vultron.core.models.base import (
    CoreRecord,
    NonEmptyString,
    UriString,
    ValidatedAssignmentMixin,
    with_record_id,
)
from vultron.core.models.embargo_apply import ConsentRowChange, RegisterStep


class PlannedEmbargoEntryRecord(ValidatedAssignmentMixin):
    """One entry an embargo act will commit after its own, as data.

    *change* is what applying the entry writes; ``None`` for an entry that
    changes no embargo object.  *activity_id*, *event_type* and
    *activity_json* are the CASE_MANAGER's own activity for the entry,
    sealed before the act's first commit and carrying the changed object in
    full: a later run commits exactly this body.  All three are absent for
    a change the act's own entry carries (such as the owner's ``AGREED`` row
    at activation), which has no commit of its own.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    change: RegisterStep | ConsentRowChange | None = None
    activity_id: NonEmptyString | None = None
    event_type: NonEmptyString | None = None
    #: The sealed activity body, verbatim.  Held as one JSON string so
    #: storage does not normalise the nested keys of the body it holds.
    activity_json: NonEmptyString | None = None

    @model_validator(mode="after")
    def _activity_fields_together(self) -> "PlannedEmbargoEntryRecord":
        given = [
            self.activity_id is not None,
            self.event_type is not None,
            self.activity_json is not None,
        ]
        if any(given) and not all(given):
            raise ValueError(
                "a planned entry with its own commit names its activity id,"
                " event type and sealed body; one with none names none"
            )
        if not any(given) and self.change is None:
            raise ValueError(
                "a planned entry with no commit of its own must carry a change"
            )
        return self

    @property
    def commits(self) -> bool:
        """True when the entry has a commit of its own."""
        return self.activity_id is not None


class PendingEmbargoEntries(CoreRecord):
    """The entries an embargo act still owes after its own (CLP-07-015).

    Attributes:
        case_id: URI of the case the act is on.
        act_id: ``log_object_id`` of the act's own ledger entry.  When it is
            in the ledger the act happened, and its entries are owed; when it
            is not, the act never happened, and nothing is.
        act_event_type: ``event_type`` of the act's own entry, when the
            object it names may also be the object of other entries (an
            expiry names the Invite that expired).  ``None`` matches any
            entry naming *act_id*.
        act_change: The change the act's own entry carries, when this run
            commits that entry: a later run applies it again only when the
            case file lacks it (a save that failed after the commits).
        author_id: URI of the CASE_MANAGER that authors the entries.
        entries: Every entry the act commits after its own, in commit order.

    Spec: CLP-07-014, CLP-07-015; ADR-0146.
    """

    type_: Literal["PendingEmbargoEntries"] = Field(  # type: ignore[assignment]
        default="PendingEmbargoEntries",
        validation_alias="type",
        serialization_alias="type",
    )
    case_id: UriString = Field(..., description="URI of the case")
    act_id: UriString = Field(
        ..., description="log_object_id of the act's own ledger entry"
    )
    act_event_type: NonEmptyString | None = Field(
        default=None, description="event_type of the act's own ledger entry"
    )
    act_change: RegisterStep | ConsentRowChange | None = Field(
        default=None, description="The change the act's own entry carries"
    )
    author_id: UriString = Field(
        ..., description="URI of the CASE_MANAGER that authors the entries"
    )
    entries: list[PlannedEmbargoEntryRecord] = Field(
        ..., min_length=1, description="The entries after the act's own"
    )

    @classmethod
    def build_id(cls, case_id: str, act_id: str) -> str:
        """Return the stable DataLayer ID for the act *act_id* on *case_id*."""
        case_slug = urllib.parse.quote(case_id, safe="")
        act_slug = urllib.parse.quote(act_id, safe="")
        return f"pending-embargo-entries/{case_slug}/{act_slug}"

    @model_validator(mode="before")
    @classmethod
    def _set_id(cls, data: Any) -> Any:
        """Compute ``id_`` deterministically from ``case_id`` and ``act_id``."""
        if isinstance(data, dict):
            case_id = data.get("case_id")
            act_id = data.get("act_id")
            if case_id is not None and act_id is not None:
                data = with_record_id(data, cls.build_id(case_id, act_id))
        return data


__all__ = ["PendingEmbargoEntries", "PlannedEmbargoEntryRecord"]
