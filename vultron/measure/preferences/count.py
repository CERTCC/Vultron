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
"""Count a case's path preferences from its event history (ADR-0182 rule 5).

:func:`path_preferences` reads only the
:class:`~vultron.measure.history.CaseEventHistory`, never the ledger: the
invitations, answers and timeouts are its consent events, the revisions its
embargo starts, and the case's close its ``CASE_CLOSED`` event.
``docs/topics/measuring_cvd/reward_functions.md`` defines each count.
"""

from __future__ import annotations

import logging
from datetime import datetime

from vultron.core.states.cs_invariants import CSEvent
from vultron.core.states.embargo_register import TerminationReason
from vultron.measure.history import (
    CaseEvent,
    CaseEventHistory,
    EventKind,
    GapLabel,
)
from vultron.measure.preferences.model import (
    CasePathCounts,
    DurationUndefined,
    EmbargoDuration,
    ParticipantPathCounts,
    PathPreferences,
)

logger = logging.getLogger(__name__)

_K = EventKind
_ANSWERS = frozenset({_K.CONSENT_AGREED, _K.CONSENT_DECLINED})


def _closed_out(timeout: CaseEvent, close: CaseEvent | None) -> bool:
    """Whether the Case Owner's close timed *timeout* out before its RSVP
    deadline (CM-23-014).

    The close's sweep follows the close entry.  An Invite whose deadline is
    at or before the close's commit stamp had already lapsed, since expiry
    is evaluated lazily (CM-28-007), so it timed out at its deadline.
    """
    return (
        close is not None
        and timeout.log_index > close.log_index
        and (timeout.deadline is None or timeout.deadline > close.committed_at)
    )


def _invitations(
    history: CaseEventHistory, participant: str, close: CaseEvent | None
) -> ParticipantPathCounts:
    """Count *participant*'s embargo Invites by how each first ended.

    An Invite is open from its row's ``CONSENT_INVITED`` event until the
    row's next answer or timeout, which ends it.  A row invited again after
    a timeout opens a new Invite (CM-18-003, EMB-17-003).
    """
    open_rows: set[str] = set()
    answered = timed_out = closed_out = 0
    for event in history.for_participant(participant):
        row = event.embargo_id
        if row is None:
            continue
        if event.kind is _K.CONSENT_INVITED:
            open_rows.add(row)
            continue
        if row not in open_rows:
            continue
        if event.kind in _ANSWERS:
            answered += 1
        elif event.kind is _K.CONSENT_TIMED_OUT:
            if _closed_out(event, close):
                closed_out += 1
            else:
                timed_out += 1
        else:
            continue
        open_rows.discard(row)
    return ParticipantPathCounts(
        participant=participant,
        answered=answered,
        timed_out=timed_out,
        timed_out_by_close=closed_out,
    )


def _revisions(starts: list[CaseEvent]) -> tuple[bool, int]:
    """Whether the default embargo was replaced, and the other revisions.

    The default embargo is the one the case's creation seated (EP-04-012);
    a revision is an embargo start that replaced an embargo in force.
    """
    default = next(
        (
            s.embargo_id
            for s in starts
            if GapLabel.SEATED_AT_CREATION in s.gaps
        ),
        None,
    )
    replaced = [s.replaces_embargo_id for s in starts if s.replaces_embargo_id]
    default_replaced = default is not None and default in replaced
    return default_replaced, sum(1 for r in replaced if r != default)


def _first_times(
    history: CaseEventHistory, kind: CSEvent | EventKind
) -> dict[str, datetime]:
    """Each participant's first event of *kind*, by its commit stamp."""
    times: dict[str, datetime] = {}
    for event in history.of_kind(kind):
        if event.participant is not None:
            times.setdefault(event.participant, event.committed_at)
    return times


def _end_of(exit_: CaseEvent) -> datetime:
    """When an embargo really ended: at its end time when it reached it,
    since the stamp is then only the latest possible end (CEH-03-015)."""
    if (
        exit_.exit_reason is TerminationReason.END_TIME_REACHED
        and exit_.deadline is not None
    ):
        return exit_.deadline
    return exit_.committed_at


def _duration(
    history: CaseEventHistory, close: CaseEvent | None
) -> EmbargoDuration:
    """The case's first embargo, across every revision, against the time
    until the last vendor's fix."""
    starts = history.of_kind(_K.EMBARGO_START)
    if not starts:
        return EmbargoDuration(undefined=DurationUndefined.NO_EMBARGO)
    start = starts[0]
    exit_ = next(
        (
            e
            for e in history.of_kind(_K.EMBARGO_EXIT)
            if e.log_index >= start.log_index
        ),
        None,
    )
    if exit_ is None:
        return EmbargoDuration(
            start=start.committed_at, undefined=DurationUndefined.NOT_ENDED
        )
    fixes = _first_times(history, CSEvent.F)
    vendors = _first_times(history, CSEvent.V)
    valid = _first_times(history, _K.REPORT_VALID)
    without_fix = tuple(v for v in vendors if v in valid and v not in fixes)
    last_fix = max(fixes.values(), default=None)
    end = _end_of(exit_)
    undefined: DurationUndefined | None = None
    if without_fix and close is None:
        undefined = DurationUndefined.FIX_PENDING
    elif last_fix is None:
        undefined = DurationUndefined.NO_FIX
    elif last_fix <= start.committed_at:
        undefined = DurationUndefined.FIXES_BEFORE_EMBARGO
    return EmbargoDuration(
        start=start.committed_at,
        end=end,
        last_fix=last_fix,
        vendors_without_fix=() if close is None else without_fix,
        undefined=undefined,
    )


def path_preferences(history: CaseEventHistory) -> PathPreferences:
    """Count the path preferences of the case *history* records.

    Read-only.  Every participant the history names gets its counts, a
    reporter or a coordinator as much as a vendor (ADR-0182 rule 4).  A
    history with a hole gives wrong counts, not imprecise ones, so a caller
    refuses one first, as the standing record does (CEH-02-006).

    Args:
        history: One case's event history, as
            :func:`~vultron.measure.history.case_event_history` derives it.

    Returns:
        One :class:`ParticipantPathCounts` per participant, in the order the
        history first names each, and the case's :class:`CasePathCounts`.
    """
    closes = history.of_kind(_K.CASE_CLOSED)
    close = closes[0] if closes else None
    participants = dict.fromkeys(
        e.participant for e in history.events if e.participant is not None
    )
    default_replaced, revisions = _revisions(history.of_kind(_K.EMBARGO_START))
    counts = PathPreferences(
        case_id=history.case_id,
        participants=[_invitations(history, p, close) for p in participants],
        case=CasePathCounts(
            default_replaced=default_replaced,
            revisions=revisions,
            duration=_duration(history, close),
        ),
    )
    logger.debug(
        "Case %s: path preferences counted for %d participants",
        history.case_id,
        len(counts.participants),
    )
    return counts
