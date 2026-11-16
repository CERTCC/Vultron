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
"""The path-preference counts of one case (ADR-0182).

Each count describes the case and compares it with nothing: no count has a
chance value, so none is a score (ADR-0182).  A preference about a
participant's own acts is counted for each participant, every role
included, so a reporter or a coordinator has counts though it has no score
(:class:`ParticipantPathCounts`).  A preference about the embargo is counted
for the case, because the embargo belongs to the case
(:class:`CasePathCounts`).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from fractions import Fraction

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    model_validator,
)

from vultron.core.models._helpers import timestamp_serializer
from vultron.primitives import NonEmptyString

_TICK = timedelta(microseconds=1)


class ParticipantPathCounts(BaseModel):
    """One participant's embargo Invites, by how each ended.

    Only an embargo Invite is counted, never a stub Invite to the case: that
    carries no RSVP deadline, so it can never time out at one (CM-23-014).  An
    Invite whose embargo was rejected, cancelled, replaced or ended before
    the participant answered is in no count: no Invite was left to answer.

    Fields:
        participant: The participant's actor.
        answered: Invites answered before any timeout of them.  A late
            answer, or a changed one, adds nothing: each Invite counts once,
            by how it first ended.
        timed_out: Invites that timed out at their RSVP deadline: a pocket
            veto.
        timed_out_by_close: Invites the Case Owner's close timed out before
            their RSVP deadline (CM-23-014).  The participant still had time
            to answer, so they are reported here and left out of the ratio.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    participant: NonEmptyString
    answered: int = Field(default=0, ge=0)
    timed_out: int = Field(default=0, ge=0)
    timed_out_by_close: int = Field(default=0, ge=0)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def answered_ratio(self) -> Fraction | None:
        """The Invites answered out of those answered or timed out at their
        deadline; ``None`` with neither."""
        counted = self.answered + self.timed_out
        return Fraction(self.answered, counted) if counted else None


class DurationUndefined(StrEnum):
    """Why a case has no embargo-duration ratio."""

    #: The case had no embargo.
    NO_EMBARGO = "no_embargo"
    #: The embargo has not ended yet.
    NOT_ENDED = "not_ended"
    #: The case is still open, and a vendor whose report reached Valid has
    #: no fix ready yet: the last fix is still to come.
    FIX_PENDING = "fix_pending"
    #: No vendor has a fix ready.
    NO_FIX = "no_fix"
    #: Every fix was ready by the embargo's start, so the time until the
    #: last fix is not above zero.
    FIXES_BEFORE_EMBARGO = "fixes_before_embargo"


#: The times each reason, or a ratio (``None``), implies: ``True`` present,
#: ``False`` absent, ``None`` either.
_TIMES_NEEDED: dict[DurationUndefined | None, dict[str, bool | None]] = {
    None: {"start": True, "end": True, "last fix": True},
    DurationUndefined.NO_EMBARGO: {
        "start": False,
        "end": False,
        "last fix": False,
    },
    DurationUndefined.NOT_ENDED: {
        "start": True,
        "end": False,
        "last fix": None,
    },
    DurationUndefined.FIX_PENDING: {
        "start": True,
        "end": True,
        "last fix": None,
    },
    DurationUndefined.NO_FIX: {"start": True, "end": True, "last fix": False},
    DurationUndefined.FIXES_BEFORE_EMBARGO: {
        "start": True,
        "end": True,
        "last fix": True,
    },
}

#: The reasons read before the case's vendors are, so none names a vendor
#: without a fix: a vendor lacks one only once the case has closed.
_BEFORE_THE_LAST_FIX = frozenset(
    {
        DurationUndefined.NO_EMBARGO,
        DurationUndefined.NOT_ENDED,
        DurationUndefined.FIX_PENDING,
    }
)


def _named(reason: DurationUndefined | None) -> str:
    return "with a ratio" if reason is None else f"undefined as {reason}"


class EmbargoDuration(BaseModel):
    """The embargo's duration against the time until the last fix.

    The ratio is the embargo duration divided by the time from the embargo's
    start until the last vendor's fix is ready.  Near 1 is the preference;
    above 1 the embargo outlasted the last fix, below 1 it ended before it.

    Fields:
        start: When the case's first embargo started.
        end: When that embargo, across every revision, ended: the end time
            of an embargo that reached it, otherwise the exit's commit stamp.
        last_fix: When the last vendor's fix was ready.
        vendors_without_fix: Each vendor of a closed case whose report
            reached Valid and that has no fix.  The ratio is over the vendors
            with one.
        undefined: Why there is no ratio; ``None`` exactly when there is one.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    start: datetime | None = None
    end: datetime | None = None
    last_fix: datetime | None = None
    vendors_without_fix: tuple[NonEmptyString, ...] = ()
    undefined: DurationUndefined | None = None

    _serialize_times = timestamp_serializer("start", "end", "last_fix")

    @model_validator(mode="after")
    def _a_ratio_or_why_not(self) -> EmbargoDuration:
        """Each reason, or the ratio, holds exactly the times it implies."""
        problems: list[str] = []
        reason = self.undefined
        has = {
            "start": self.start is not None,
            "end": self.end is not None,
            "last fix": self.last_fix is not None,
        }
        needs = _TIMES_NEEDED[reason]
        problems.extend(
            f"a duration {_named(reason)} {'has' if need else 'has no'} {name}"
            for name, need in needs.items()
            if need is not None and has[name] != need
        )
        if self.vendors_without_fix and reason in _BEFORE_THE_LAST_FIX:
            problems.append(
                f"a duration {_named(reason)} names no vendor without a fix"
            )
        if not problems and has["last fix"] and has["start"]:
            assert self.last_fix is not None and self.start is not None
            after = self.last_fix > self.start
            if reason is None and not after:
                problems.append(
                    "a duration with a ratio has its last fix after its start"
                )
            if reason is DurationUndefined.FIXES_BEFORE_EMBARGO and after:
                problems.append(
                    "a duration whose fixes were all ready before the"
                    " embargo has no last fix after its start"
                )
        if problems:
            raise ValueError("; ".join(problems))
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ratio(self) -> Fraction | None:
        """The embargo duration over the time until the last fix; ``None``
        when :attr:`undefined` says why."""
        if (
            self.undefined is not None
            or self.start is None
            or self.end is None
            or self.last_fix is None
        ):
            return None
        return Fraction(
            (self.end - self.start) // _TICK,
            (self.last_fix - self.start) // _TICK,
        )


class CasePathCounts(BaseModel):
    """The case's embargo revisions and its embargo duration.

    Fields:
        default_replaced: Whether a negotiated embargo replaced the default
            embargo the case's creation seated.  That replacement is the
            normal path, not churn, so it is not a revision here.
        revisions: The revisions the Case Owner activated while an embargo
            was in force, the replacement of a default embargo left out
            (EP-09-005).  A low count is the preference; a reader weighs it
            with :attr:`duration`, since a trailing vendor can need one.
        duration: The embargo duration against the time until the last fix.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    default_replaced: bool = False
    revisions: int = Field(default=0, ge=0)
    duration: EmbargoDuration


class PathPreferences(BaseModel):
    """The path-preference counts of one case.

    Fields:
        case_id: The case.
        participants: One record for each participant the history names, in
            the order it first names each.
        case: The counts for the case.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: NonEmptyString
    participants: list[ParticipantPathCounts] = Field(default_factory=list)
    case: CasePathCounts

    @model_validator(mode="after")
    def _one_record_per_participant(self) -> PathPreferences:
        names = [p.participant for p in self.participants]
        if len(set(names)) != len(names):
            raise ValueError("a participant is listed more than once")
        return self

    def for_participant(
        self, participant: str
    ) -> ParticipantPathCounts | None:
        """The counts of *participant*, or ``None`` when it has none."""
        for counts in self.participants:
            if counts.participant == participant:
                return counts
        return None
