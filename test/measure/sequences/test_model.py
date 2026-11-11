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
from vultron.core.states.cs_invariants import CSEvent
from vultron.measure.history import CaseEvent, CaseEventKind, EventKind
from vultron.measure.sequences import (
    CaseStateSequence,
    CaseStateSequences,
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
        events=overrides.get("events", events),
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
        # A fix before awareness.
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


def test_an_empty_sequence_is_refused():
    with pytest.raises(ValidationError):
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
    assert sequences.for_participant(VENDOR) is not None
    assert sequences.for_participant(VENDOR_2) is None
