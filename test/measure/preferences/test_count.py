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
"""Path-preference counts from hand-built histories (ADR-0182 rule 5).

``docs/topics/measuring_cvd/reward_functions.md`` defines each count.  Entry
*i* of a hand-built ledger is committed at second ``2 i + 1``, which the
hand-computed ratios below read.
"""

from datetime import datetime, timedelta
from fractions import Fraction

import pytest
from pydantic import ValidationError

from test.measure.history.builders import (
    CM,
    EMBARGO,
    EMBARGO_2,
    EMBARGO_END,
    OWNER,
    REPORTER,
    VENDOR,
    VENDOR_2,
    Ledger,
    embargo,
    participant,
    seat_vendor,
    stamp,
    status,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.states.embargo_register import TerminationReason
from vultron.demo.recordings.layout import recording_path
from vultron.measure.history import (
    CaseEvent,
    CaseEventHistory,
    EventKind,
    read_case_event_histories,
)
from vultron.measure.ledger import LedgerSource
from vultron.measure.preferences import (
    DurationUndefined,
    EmbargoDuration,
    ParticipantPathCounts,
    PathPreferences,
    path_preferences,
)

EMBARGO_3 = "urn:uuid:embargo-3"
EMBARGO_4 = "urn:uuid:embargo-4"

#: An RSVP deadline after every entry of a hand-built ledger.
_LATER = stamp(3000)


def _counts(ledger: Ledger) -> PathPreferences:
    return path_preferences(ledger.history())


def _of(counts: PathPreferences, participant: str) -> ParticipantPathCounts:
    found = counts.for_participant(participant)
    assert found is not None, participant
    return found


def _at(second: int) -> datetime:
    return datetime.fromisoformat(stamp(second))


# ---------------------------------------------------------------------------
# Invitations answered before their deadline (CM-23-014)
# ---------------------------------------------------------------------------


@pytest.mark.spec("CM-23-014")
@pytest.mark.spec("CEH-04-017")
@pytest.mark.spec("CEH-04-018")
def test_each_kind_of_invite_is_counted_its_own_way():
    """One Invite answered, one timed out at its deadline, and one the
    owner's close timed out before its deadline, which is left out."""
    ledger = Ledger()
    ledger.standard_genesis()
    seat_vendor(ledger, VENDOR, "Vf")
    ledger.invite(VENDOR, EMBARGO_2, _LATER)
    ledger.answer(VENDOR, EMBARGO_2, accept=True)
    ledger.invite(VENDOR, EMBARGO_3, stamp(8))
    assert ledger.time_out(VENDOR, EMBARGO_3) * 2 + 1 > 8
    ledger.invite(VENDOR, EMBARGO_4, _LATER)
    ledger.leave(OWNER)
    ledger.time_out(VENDOR, EMBARGO_4)
    vendor = _of(_counts(ledger), VENDOR)
    assert (vendor.answered, vendor.timed_out, vendor.timed_out_by_close) == (
        1,
        1,
        1,
    )
    assert vendor.answered_ratio == Fraction(1, 2)


@pytest.mark.spec("CM-23-014")
def test_an_invite_already_overdue_at_the_close_timed_out_at_its_deadline():
    """The close's sweep finds it past its deadline, which expiry evaluated
    lazily had already passed (CM-28-007): at or before the close counts."""
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.invite(REPORTER, EMBARGO_2, stamp(5))
    ledger.invite(REPORTER, EMBARGO_3, stamp(7))
    close = ledger.leave(OWNER)
    assert stamp(close * 2 + 1) == stamp(7)
    ledger.time_out(REPORTER, EMBARGO_2)
    ledger.time_out(REPORTER, EMBARGO_3)
    reporter = _of(_counts(ledger), REPORTER)
    assert (reporter.timed_out, reporter.timed_out_by_close) == (2, 0)
    assert reporter.answered_ratio == Fraction(0)


def test_each_invite_counts_once_by_how_it_first_ended():
    """A late answer and a changed answer add nothing; a row invited again
    after its timeout holds a second Invite (EMB-17-003)."""
    ledger = Ledger()
    ledger.standard_genesis()
    seat_vendor(ledger, VENDOR, "Vf")
    ledger.invite(VENDOR, EMBARGO_2, stamp(4))
    ledger.time_out(VENDOR, EMBARGO_2)
    ledger.answer(VENDOR, EMBARGO_2, accept=True)  # late: the row is AGREED
    ledger.invite(VENDOR, EMBARGO_3, _LATER)
    ledger.answer(VENDOR, EMBARGO_3, accept=True)
    ledger.answer(VENDOR, EMBARGO_3, accept=False)  # a changed answer
    ledger.time_out(VENDOR, EMBARGO_3)  # not INVITED, so no Invite to end
    ledger.invite(VENDOR, EMBARGO_4, stamp(18))
    ledger.time_out(VENDOR, EMBARGO_4)
    ledger.invite(VENDOR, EMBARGO_4, _LATER)
    ledger.answer(VENDOR, EMBARGO_4, accept=True)
    vendor = _of(_counts(ledger), VENDOR)
    assert (vendor.answered, vendor.timed_out, vendor.timed_out_by_close) == (
        2,
        2,
        0,
    )


def test_a_stub_invite_and_an_agreement_with_no_invite_are_not_counted():
    """A stub Invite's row has no RSVP deadline (CM-23-014), and an owner's
    activation or a proposer's own row answers no Invite."""
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.seat(
        participant(
            VENDOR,
            [status("v-r", VENDOR, "RECEIVED", vf="vf", roles=("VENDOR",))],
            roles=("VENDOR",),
            joined=False,
        )
    )
    ledger.add(
        "accept_invite_actor_to_case",
        "Accept",
        VENDOR,
        ledger.stub_invite(VENDOR),
    )
    ledger.add("activate_embargo_on_case", "Add", OWNER, embargo(EMBARGO_2))
    counts = _counts(ledger)
    for actor in (VENDOR, OWNER):
        assert _of(counts, actor).answered_ratio is None, actor


@pytest.mark.spec("CM-23-014")
def test_a_reporter_gets_its_counts():
    """A participant with no vendor path still has counts (ADR-0182 rule 4)."""
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.invite(REPORTER, EMBARGO_2, _LATER)
    ledger.answer(REPORTER, EMBARGO_2, accept=False)
    counts = _counts(ledger)
    reporter = _of(counts, REPORTER)
    assert (reporter.answered, reporter.timed_out) == (1, 0)
    assert reporter.answered_ratio == 1
    assert [p.participant for p in counts.participants] == [
        CM,
        OWNER,
        REPORTER,
    ]
    assert _of(counts, CM).answered_ratio is None


# ---------------------------------------------------------------------------
# Embargo revisions and duration
# ---------------------------------------------------------------------------


def _revised_case() -> Ledger:
    """A default embargo replaced, then revised once, a vendor's fix, an
    exit.  Entry indices: 0 genesis, 1 vendor aware, 2 valid, 3 and 4 the
    two activations, 5 the fix, 6 the exit."""
    ledger = Ledger()
    ledger.standard_genesis()
    seat_vendor(ledger, VENDOR, "Vf")
    ledger.add_status(
        VENDOR, status("v-v", VENDOR, "VALID", vf="Vf", roles=("VENDOR",))
    )
    ledger.add("activate_embargo_on_case", "Add", OWNER, embargo(EMBARGO_2))
    ledger.add("activate_embargo_on_case", "Add", OWNER, embargo(EMBARGO_3))
    fix = ledger.add_status(
        VENDOR, status("v-a", VENDOR, "ACCEPTED", vf="VF", roles=("VENDOR",))
    )
    exit_ = ledger.add(
        "remove_embargo_event_from_case",
        "Remove",
        OWNER,
        embargo(EMBARGO_3),
        content="EARLY",
    )
    assert (fix, exit_) == (5, 6)
    return ledger


def test_a_revised_case_is_counted_by_hand():
    """Duration: the default's start at second 1 to the exit at second 13;
    the fix at second 11.  So (13 - 1) / (11 - 1) = 6/5."""
    case = _counts(_revised_case()).case
    assert case.default_replaced is True
    assert case.revisions == 1
    duration = case.duration
    assert (duration.start, duration.end, duration.last_fix) == (
        _at(1),
        _at(13),
        _at(11),
    )
    assert duration.undefined is None
    assert duration.ratio == Fraction(6, 5)


def test_an_activation_with_no_embargo_in_force_is_no_revision():
    ledger = Ledger()
    ledger.genesis(
        [participant(CM, [status("cm-r", CM, "RECEIVED")])],
        with_embargo=False,
    )
    ledger.add("activate_embargo_on_case", "Add", OWNER, embargo(EMBARGO_2))
    case = _counts(ledger).case
    assert (case.default_replaced, case.revisions) == (False, 0)
    assert case.duration.undefined is DurationUndefined.NOT_ENDED


def test_an_embargo_that_reached_its_end_time_ended_at_it():
    """The commit stamp is only the latest possible end (CEH-03-015)."""
    ledger = Ledger()
    ledger.standard_genesis()
    seat_vendor(ledger, VENDOR, "VF")
    ledger.add(
        "remove_embargo_event_from_case",
        "Remove",
        CM,
        embargo(),
        content="END_TIME_REACHED",
    )
    duration = _counts(ledger).case.duration
    assert duration.end == datetime.fromisoformat(EMBARGO_END)
    assert duration.ratio == Fraction(
        (duration.end - _at(1)) // timedelta(seconds=1), 3 - 1
    )


def _exit(ledger: Ledger, embargo_id: str = EMBARGO) -> int:
    return ledger.add(
        "remove_embargo_event_from_case",
        "Remove",
        OWNER,
        embargo(embargo_id),
        content="EARLY",
    )


def _valid_vendor(ledger: Ledger, actor: str, *, fixed: bool) -> None:
    seat_vendor(ledger, actor, "Vf")
    ledger.add_status(
        actor,
        status(
            f"{actor}-v",
            actor,
            "VALID",
            vf="VF" if fixed else "Vf",
            roles=("VENDOR",),
        ),
    )


def test_no_embargo_has_no_ratio():
    ledger = Ledger()
    ledger.genesis(
        [participant(CM, [status("cm-r", CM, "RECEIVED")])],
        with_embargo=False,
    )
    duration = _counts(ledger).case.duration
    assert duration.undefined is DurationUndefined.NO_EMBARGO
    assert duration.ratio is None


def test_an_open_case_waiting_on_a_valid_vendors_fix_has_no_ratio():
    ledger = Ledger()
    ledger.standard_genesis()
    _valid_vendor(ledger, VENDOR, fixed=False)
    _valid_vendor(ledger, VENDOR_2, fixed=True)
    _exit(ledger)
    duration = _counts(ledger).case.duration
    assert duration.undefined is DurationUndefined.FIX_PENDING
    assert duration.ratio is None
    assert duration.vendors_without_fix == ()


def test_a_closed_case_reports_each_vendor_without_a_fix_beside_the_ratio():
    """The ratio is over the vendors with a fix.  Indices: 0 genesis, 1 and
    2 the first vendor, 3 and 4 the second (fix at second 9), 5 the exit
    (second 11), 6 the close."""
    ledger = Ledger()
    ledger.standard_genesis()
    _valid_vendor(ledger, VENDOR, fixed=False)
    _valid_vendor(ledger, VENDOR_2, fixed=True)
    _exit(ledger)
    ledger.leave(OWNER)
    duration = _counts(ledger).case.duration
    assert duration.vendors_without_fix == (VENDOR,)
    assert duration.ratio == Fraction(11 - 1, 9 - 1)


def test_a_closed_case_with_no_fix_has_no_ratio_and_names_the_vendor():
    ledger = Ledger()
    ledger.standard_genesis()
    _valid_vendor(ledger, VENDOR, fixed=False)
    _exit(ledger)
    ledger.leave(OWNER)
    duration = _counts(ledger).case.duration
    assert duration.undefined is DurationUndefined.NO_FIX
    assert duration.vendors_without_fix == (VENDOR,)


def test_every_fix_ready_before_the_embargo_started_has_no_ratio():
    ledger = Ledger()
    ledger.genesis(
        [participant(CM, [status("cm-r", CM, "RECEIVED")])],
        with_embargo=False,
    )
    _valid_vendor(ledger, VENDOR, fixed=True)
    ledger.add("activate_embargo_on_case", "Add", OWNER, embargo(EMBARGO_2))
    _exit(ledger, EMBARGO_2)
    duration = _counts(ledger).case.duration
    assert duration.undefined is DurationUndefined.FIXES_BEFORE_EMBARGO
    assert duration.ratio is None


_U = DurationUndefined


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"start": _at(1)}, "with a ratio has end"),
        (
            {"start": _at(5), "end": _at(9), "last_fix": _at(5)},
            "last fix after its start",
        ),
        ({"undefined": _U.NO_EMBARGO, "start": _at(1)}, "has no start"),
        (
            {"undefined": _U.NOT_ENDED, "start": _at(1), "end": _at(3)},
            "has no end",
        ),
        (
            {
                "undefined": _U.NOT_ENDED,
                "start": _at(1),
                "vendors_without_fix": (VENDOR,),
            },
            "names no vendor without a fix",
        ),
        ({"undefined": _U.FIX_PENDING, "start": _at(1)}, "has end"),
        (
            {
                "undefined": _U.NO_FIX,
                "start": _at(1),
                "end": _at(3),
                "last_fix": _at(2),
            },
            "has no last fix",
        ),
        (
            {
                "undefined": _U.FIXES_BEFORE_EMBARGO,
                "start": _at(1),
                "end": _at(3),
                "last_fix": _at(2),
            },
            "all ready before",
        ),
    ],
)
def test_a_duration_holds_exactly_the_times_its_reason_implies(
    fields, message
):
    with pytest.raises(ValidationError, match=message):
        EmbargoDuration(**fields)


def test_a_participant_is_counted_once():
    with pytest.raises(ValidationError, match="more than once"):
        PathPreferences(
            case_id="c",
            participants=[
                ParticipantPathCounts(participant=VENDOR),
                ParticipantPathCounts(participant=VENDOR),
            ],
            case=_counts(_revised_case()).case,
        )


def test_a_recorded_revision_replaces_the_default_and_is_answered():
    """``rcv-embargo``: the reporter's proposal replaces the default embargo,
    and the vendor accepts its Invite (entries 31 and 32)."""
    (history,) = read_case_event_histories(
        [recording_path("rcv-embargo")]
    ).histories.values()
    counts = path_preferences(history)
    assert (counts.case.default_replaced, counts.case.revisions) == (True, 0)
    vendor = _of(counts, "http://actor1:7999/api/v2/actors/actor1")
    assert (vendor.answered, vendor.timed_out) == (1, 0)
    assert counts.case.duration.ratio is not None


def test_a_vendor_whose_report_never_reached_valid_is_not_waited_for():
    """Only a vendor whose report reached Valid holds the ratio back, or is
    named without a fix.  Indices: 0 genesis, 1 the aware vendor, 2 and 3
    the fixed vendor (fix at second 7), 4 the exit (second 9)."""
    ledger = Ledger()
    ledger.standard_genesis()
    seat_vendor(ledger, VENDOR, "Vf")
    _valid_vendor(ledger, VENDOR_2, fixed=True)
    _exit(ledger)
    assert _counts(ledger).case.duration.ratio == Fraction(9 - 1, 7 - 1)
    ledger.leave(OWNER)
    assert _counts(ledger).case.duration.vendors_without_fix == ()


def _event(kind: EventKind, index: int, **fields: object) -> CaseEvent:
    return CaseEvent.model_validate(
        {
            "kind": kind,
            "semantic_type": MessageSemantics.UPDATE_EMBARGO_CONSENT,
            "log_index": index,
            "committed_at": _at(index),
            **fields,
        }
    )


def _history(*events: CaseEvent) -> CaseEventHistory:
    return CaseEventHistory(
        case_id="urn:uuid:case-1",
        source=LedgerSource.COMPLETE_COPY,
        end_confirmed=True,
        events=list(events),
    )


def test_a_timeout_before_the_close_is_never_the_closes():
    """Even with its deadline after the close: the close's sweep follows it."""
    history = _history(
        _event(
            EventKind.CONSENT_INVITED,
            1,
            participant=VENDOR,
            embargo_id=EMBARGO_2,
            rsvp_deadline=_at(9),
        ),
        _event(
            EventKind.CONSENT_TIMED_OUT,
            2,
            participant=VENDOR,
            embargo_id=EMBARGO_2,
            deadline=_at(9),
        ),
        _event(EventKind.CASE_CLOSED, 3),
    )
    vendor = _of(path_preferences(history), VENDOR)
    assert (vendor.timed_out, vendor.timed_out_by_close) == (1, 0)


def test_a_timeout_after_the_close_with_no_deadline_is_the_closes():
    """A merge can lose the deadline; nothing then shows it had passed."""
    history = _history(
        _event(
            EventKind.CONSENT_INVITED,
            1,
            participant=VENDOR,
            embargo_id=EMBARGO_2,
            rsvp_deadline=_at(9),
        ),
        _event(EventKind.CASE_CLOSED, 2),
        _event(
            EventKind.CONSENT_TIMED_OUT,
            3,
            participant=VENDOR,
            embargo_id=EMBARGO_2,
        ),
    )
    vendor = _of(path_preferences(history), VENDOR)
    assert (vendor.timed_out, vendor.timed_out_by_close) == (0, 1)


def test_an_exit_before_the_first_start_is_not_its_end():
    """A merge missing an activation can hold an exit with no start."""
    history = _history(
        _event(
            EventKind.EMBARGO_EXIT,
            1,
            embargo_id=EMBARGO,
            exit_reason=TerminationReason.EARLY,
        ),
        _event(EventKind.EMBARGO_START, 2, embargo_id=EMBARGO_2),
    )
    duration = path_preferences(history).case.duration
    assert duration.undefined is DurationUndefined.NOT_ENDED
    assert duration.start == _at(2)
