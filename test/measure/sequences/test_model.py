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

"""The per-vendor sequence refuses what the validator would not replay (CEH-05)."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from test.measure.history.builders import VENDOR, VENDOR_2
from vultron.core.models.events.base import MessageSemantics
from vultron.core.states.cs import CS
from vultron.core.states.cs_invariants import (
    CSEvent,
    apply_cs_event,
    required_next_cs_events,
)
from vultron.measure.history import CaseEvent, CaseEventKind, EventKind
from vultron.measure.sequences import (
    CaseStateSequence,
    CaseStateSequences,
    Placement,
    SequenceEvent,
    UnprojectableParticipant,
    UnprojectableReason,
)

_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _event(
    kind: CaseEventKind, index: int, participant: str | None = VENDOR
) -> CaseEvent:
    if kind in (CSEvent.P, CSEvent.X, CSEvent.A):
        participant = None
    return CaseEvent(
        kind=kind,
        participant=participant,
        semantic_type=MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT,
        log_index=index,
        committed_at=_AT,
    )


def _sequence(*kinds: CaseEventKind, **overrides) -> CaseStateSequence:
    events = [_event(kind, i) for i, kind in enumerate(kinds)]
    return CaseStateSequence(
        participant=overrides.get("participant", VENDOR),
        events=[
            SequenceEvent(event=event)
            for event in overrides.get("events", events)
        ],
    )


@pytest.mark.spec("CEH-05-004")
@pytest.mark.spec("CEH-05-005")
def test_an_incomplete_prefix_is_held():
    sequence = _sequence(CSEvent.V, CSEvent.F, CSEvent.P)
    assert sequence.kinds == (CSEvent.V, CSEvent.F, CSEvent.P)


@pytest.mark.spec("CEH-05-005")
@pytest.mark.parametrize(
    "kinds",
    [
        # Public awareness then the exploit, vendor awareness absent between.
        (CSEvent.P, CSEvent.X, CSEvent.V),
        # A deployment with no fix-ready event before it.
        (CSEvent.V, CSEvent.D),
    ],
    ids=["PXV", "VD"],
)
def test_a_missing_event_before_a_later_one_is_refused(kinds):
    with pytest.raises(ValidationError, match="not a valid case-state"):
        _sequence(*kinds)


@pytest.mark.spec("CEH-05-001")
def test_a_sequence_with_no_vendor_awareness_is_refused():
    with pytest.raises(ValidationError, match="no vendor-awareness"):
        _sequence(CSEvent.P)


@pytest.mark.spec("CEH-05-002")
def test_a_report_or_embargo_event_is_refused():
    with pytest.raises(ValidationError, match="not a case-state event"):
        _sequence(CSEvent.V, EventKind.REPORT_RECEIVED)
    with pytest.raises(ValidationError, match="not a case-state event"):
        _sequence(
            CSEvent.V,
            events=[
                _event(CSEvent.V, 0),
                CaseEvent(
                    kind=EventKind.EMBARGO_START,
                    semantic_type=MessageSemantics.CREATE_CASE,
                    log_index=1,
                    committed_at=_AT,
                    embargo_id="urn:uuid:embargo-1",
                ),
            ],
        )


@pytest.mark.spec("CEH-05-006")
def test_another_vendors_event_is_refused():
    events = [_event(CSEvent.V, 0), _event(CSEvent.F, 1, VENDOR_2)]
    with pytest.raises(ValidationError, match="belongs to"):
        _sequence(events=events)


def test_events_out_of_log_order_are_refused():
    events = [_event(CSEvent.V, 3), _event(CSEvent.F, 1)]
    with pytest.raises(ValidationError, match="log order"):
        _sequence(events=events)


def test_an_event_repeated_is_refused():
    with pytest.raises(ValidationError, match="occurs more than once"):
        _sequence(CSEvent.V, CSEvent.V)


def test_every_violation_is_named():
    events = [_event(CSEvent.F, 3), _event(EventKind.REPORT_VALID, 1)]
    with pytest.raises(ValidationError) as caught:
        _sequence(events=events)
    message = str(caught.value)
    for problem in (
        "not a case-state event",
        "not in log order",
        "no vendor-awareness event",
    ):
        assert problem in message


def test_an_empty_sequence_is_refused():
    with pytest.raises(ValidationError, match="at least 1 item"):
        _sequence(events=[])


@pytest.mark.spec("CEH-05-007")
def test_an_unprojectable_participant_states_its_reason():
    with pytest.raises(ValidationError):
        UnprojectableParticipant(
            participant=VENDOR,
            reason=UnprojectableReason.NO_VENDOR_AWARENESS,
            detail="",
        )


def test_for_participant_finds_only_a_projected_vendor():
    sequences = CaseStateSequences(
        case_id="urn:uuid:case-1", sequences=[_sequence(CSEvent.V)]
    )
    found = sequences.for_participant(VENDOR)
    assert found is not None
    assert found.participant == VENDOR
    assert sequences.for_participant(VENDOR_2) is None


def _sequence_of(participant: str, aware_at: int) -> CaseStateSequence:
    return CaseStateSequence(
        participant=participant,
        events=[SequenceEvent(event=_event(CSEvent.V, aware_at, participant))],
    )


def _unprojectable(participant: str) -> UnprojectableParticipant:
    return UnprojectableParticipant(
        participant=participant,
        reason=UnprojectableReason.NO_CASE_STATE_EVENTS,
        detail="it has no fix-path or deployment event of its own",
    )


@pytest.mark.parametrize(
    ("sequences", "unprojectable", "problem"),
    [
        (
            [_sequence_of(VENDOR, 1), _sequence_of(VENDOR, 2)],
            [],
            "projected twice",
        ),
        (
            [],
            [_unprojectable(VENDOR), _unprojectable(VENDOR)],
            "reported unprojectable twice",
        ),
        (
            [_sequence_of(VENDOR, 1)],
            [_unprojectable(VENDOR)],
            "both projected and reported unprojectable",
        ),
        (
            [_sequence_of(VENDOR, 5), _sequence_of(VENDOR_2, 2)],
            [],
            "not in vendor-awareness order",
        ),
    ],
    ids=["projected-twice", "reported-twice", "both", "out-of-order"],
)
def test_the_sequences_answer_each_participant_once_in_order(
    sequences, unprojectable, problem
):
    with pytest.raises(ValidationError, match=problem):
        CaseStateSequences(
            case_id="urn:uuid:case-1",
            sequences=sequences,
            unprojectable=unprojectable,
        )


_R, _MOVED, _IMPLIED = (
    Placement.RECORDED,
    Placement.MOVED,
    Placement.IMPLIED,
)


def _placed(
    *members: tuple[CaseEventKind, int, Placement],
) -> CaseStateSequence:
    return CaseStateSequence(
        participant=VENDOR,
        events=[
            SequenceEvent(event=_event(kind, index), placement=placement)
            for kind, index, placement in members
        ],
    )


@pytest.mark.spec("CEH-05-009")
def test_a_vendor_awareness_moved_to_public_awareness_is_held():
    sequence = _placed(
        (CSEvent.P, 1, _R), (CSEvent.V, 5, _MOVED), (CSEvent.X, 3, _R)
    )
    assert sequence.kinds == (CSEvent.P, CSEvent.V, CSEvent.X)
    assert sequence.awareness_index == 5
    assert [m.kind for m in sequence.placed] == [CSEvent.V]


@pytest.mark.spec("CEH-05-009")
def test_moved_and_implied_members_are_held_together():
    """Recorded X, A, V: P implied at X, then V moved up past A."""
    sequence = _placed(
        (CSEvent.X, 1, _R),
        (CSEvent.P, 1, _IMPLIED),
        (CSEvent.V, 4, _MOVED),
        (CSEvent.A, 2, _R),
    )
    assert sequence.kinds == (CSEvent.X, CSEvent.P, CSEvent.V, CSEvent.A)
    assert [m.placement for m in sequence.placed] == [_IMPLIED, _MOVED]


@pytest.mark.spec("CEH-05-009")
@pytest.mark.parametrize(
    ("members", "problem"),
    [
        (
            [(CSEvent.V, 0, _R), (CSEvent.P, 2, _MOVED), (CSEvent.X, 1, _R)],
            "P moved is not forced by Vfdpxa",
        ),
        (
            [(CSEvent.X, 1, _R), (CSEvent.V, 5, _MOVED), (CSEvent.P, 3, _R)],
            "V moved is not forced by vfdpXa",
        ),
        (
            [(CSEvent.P, 1, _R), (CSEvent.V, 2, _MOVED), (CSEvent.X, 3, _R)],
            "recorded no later than itself",
        ),
        (
            [(CSEvent.P, 1, _R), (CSEvent.V, 2, _MOVED)],
            "recorded no later than itself",
        ),
        (
            [(CSEvent.V, 0, _R), (CSEvent.X, 1, _R), (CSEvent.P, 4, _IMPLIED)],
            "must carry the log index and clocks",
        ),
        (
            [(CSEvent.V, 0, _IMPLIED)],
            "V implied is not forced by vfdpxa",
        ),
    ],
    ids=[
        "moved-not-forced",
        "moved-wrong-kind",
        "moved-not-moved",
        "moved-last",
        "implied-own-clock",
        "implied-not-forced",
    ],
)
def test_a_misplaced_event_is_refused(members, problem):
    with pytest.raises(ValidationError, match=problem):
        _placed(*members)


@pytest.mark.spec("CEH-05-009")
def test_every_transient_state_has_exactly_one_way_out():
    """The projection takes a transient state's forced event; the model
    must name exactly one for each (CSB-17-003)."""
    forcing = {
        state: required_next_cs_events(state)
        for state in CS
        if required_next_cs_events(state)
    }
    assert forcing
    for state, forced in forcing.items():
        assert len(forced) == 1, state.name
        (kind,) = forced
        assert apply_cs_event(state, kind) is not None
