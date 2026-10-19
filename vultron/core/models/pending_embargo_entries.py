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
)
from vultron.core.models.embargo_apply import ConsentRowChange, RegisterStep


class RecordedEntryActivity(ValidatedAssignmentMixin):
    """The CASE_MANAGER's own record activity for one planned entry.

    Sealed before the act's first commit and carrying the changed object in
    full: a later run commits exactly this body (ADR-0146).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    activity_id: NonEmptyString
    event_type: NonEmptyString
    #: The sealed activity body, verbatim.  Held as one JSON string so
    #: storage does not normalise the nested keys of the body it holds.
    activity_json: NonEmptyString


class PlannedEmbargoEntryRecord(ValidatedAssignmentMixin):
    """One entry an embargo act will commit after its own, as data.

    *change* is what applying the entry writes; ``None`` for an entry that
    changes no embargo object.  *recorded* is the entry's record activity;
    ``None`` for a change the act's own entry carries (such as the owner's
    ``AGREED`` row at activation), which has no commit of its own.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    change: RegisterStep | ConsentRowChange | None = None
    recorded: RecordedEntryActivity | None = None

    @model_validator(mode="after")
    def _commits_or_changes(self) -> "PlannedEmbargoEntryRecord":
        if self.recorded is None and self.change is None:
            raise ValueError(
                "a planned entry with no commit of its own must carry a change"
            )
        return self


class PendingEmbargoEntries(CoreRecord):
    """The entries an embargo act still owes after its own (CLP-07-015).

    Built with :meth:`for_act`, whose id names the case, the act and the
    act's first owed entry, so two acts naming the same object (two
    invitees' expiries of an Invite that cannot be named) never share one.

    Attributes:
        case_id: URI of the case the act is on.
        act_id: ``log_object_id`` of the act's own ledger entry.  When it is
            in the ledger the act happened, and its entries are owed; when it
            is not, the act never happened, and nothing is.
        act_event_type: ``event_type`` of the act's own entry, when the
            object it names may also be the object of other entries (an
            expiry names the Invite that expired).  ``None`` matches any
            entry naming *act_id*.
        act_committed_after: When this run commits the act's own entry, the
            ledger's last ``log_index`` before it (``-1`` for an empty
            ledger): only an entry after it is the act's, so an earlier entry
            naming the same object is never taken for it.  ``None`` when the
            act's entry was committed before the plan (a received act).
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
    act_committed_after: int | None = Field(
        default=None,
        ge=-1,
        description="The ledger's last log_index before the act's own entry",
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
    def build_id(cls, case_id: str, act_id: str, first_owed_id: str) -> str:
        """The stable DataLayer ID of a plan on *case_id*.

        *act_id* names the act; *first_owed_id* is the activity id of the
        first entry the plan owes, which the act and its row derive.
        """
        slugs = "/".join(
            urllib.parse.quote(part, safe="")
            for part in (case_id, act_id, first_owed_id)
        )
        return f"pending-embargo-entries/{slugs}"

    @classmethod
    def for_act(cls, **fields: Any) -> "PendingEmbargoEntries":
        """A plan whose id :meth:`build_id` derives from *fields*.

        Raises:
            ValueError: no entry in ``entries`` has a commit of its own, so
                the plan would owe nothing.
        """
        entries = [
            PlannedEmbargoEntryRecord.model_validate(entry)
            for entry in fields["entries"]
        ]
        first = next(
            (entry.recorded for entry in entries if entry.recorded), None
        )
        if first is None:
            raise ValueError("a plan owes at least one entry with a commit")
        return cls(
            id_=cls.build_id(
                fields["case_id"], fields["act_id"], first.activity_id
            ),
            **{**fields, "entries": entries},
        )


__all__ = [
    "PendingEmbargoEntries",
    "PlannedEmbargoEntryRecord",
    "RecordedEntryActivity",
]
