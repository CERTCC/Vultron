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

"""Tests for the one apply function of embargo entries (#4713, ADR-0124).

A register step is applied from the act's own activity; each consent row is
its own entry.  The function checks the starting state, writes what the entry
carries, reads no clock and no store, and leaves its input as it was.
"""

from datetime import UTC, datetime, timedelta

import pytest

import vultron.core.models._helpers as model_helpers
from vultron.core.models import embargo_register
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_apply import (
    ConsentRowChange,
    ConsentRowVerb,
    EmbargoCaseFile,
    EmbargoChange,
    RegisterStep,
    RegisterStepKind,
    apply_embargo_change,
    changed_objects,
)
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_termination import EmbargoTermination
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import EmbargoRegisterStatus
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.errors import VultronEntryRefusedError

CASE_ID = "https://example.org/cases/apply"
ALICE = "https://example.org/actors/alice"
BOB = "https://example.org/actors/bob"
_END = datetime(2027, 1, 1, tzinfo=UTC)

_S = EmbargoConsentState
_K = RegisterStepKind


def _embargo(n: int) -> EmbargoEvent:
    return EmbargoEvent(
        id_=f"{CASE_ID}/embargoes/{n}",
        context=CASE_ID,
        end_time=_END - timedelta(days=n),
        published=_END - timedelta(days=200),
        updated=_END - timedelta(days=200),
    )


E1, E2, E3 = _embargo(1), _embargo(2), _embargo(3)


def _case_file() -> EmbargoCaseFile:
    case = VulnerabilityCase(id_=CASE_ID, name="apply")
    participants = {}
    for actor_id in (ALICE, BOB):
        record = CaseParticipant(
            id_=f"{CASE_ID}/participants/{actor_id.rsplit('/', 1)[-1]}",
            attributed_to=actor_id,
            context=CASE_ID,
        )
        case.actor_participant_index[actor_id] = record.id_
        participants[actor_id] = record
    return EmbargoCaseFile(case=case, participants=participants)


def _step(kind: RegisterStepKind, embargo: EmbargoEvent) -> RegisterStep:
    if kind == _K.PROPOSE:
        return RegisterStep(kind=kind, embargo=embargo)
    if kind == _K.TERMINATE:
        return RegisterStep(
            kind=kind,
            embargo=embargo.id_,
            termination=EmbargoTermination.early(),
        )
    return RegisterStep(kind=kind, embargo=embargo.id_)


def _row(
    verb: ConsentRowVerb,
    actor_id: str,
    embargo: EmbargoEvent,
    state: EmbargoConsentState,
    rsvp_deadline: datetime | None = None,
) -> ConsentRowChange:
    return ConsentRowChange(
        verb=verb,
        row=EmbargoConsent(
            embargo_id=embargo.id_,
            state=state,
            attributed_to=actor_id,
            rsvp_deadline=rsvp_deadline,
        ),
    )


def _create(actor_id: str, embargo: EmbargoEvent) -> ConsentRowChange:
    return _row(ConsentRowVerb.CREATE, actor_id, embargo, _S.UNINVITED)


def _update(
    actor_id: str, embargo: EmbargoEvent, state: EmbargoConsentState
) -> ConsentRowChange:
    return _row(ConsentRowVerb.UPDATE, actor_id, embargo, state)


def _proposed(embargo: EmbargoEvent) -> list[EmbargoChange]:
    """A proposal's entries: the act, then one row entry per participant."""
    return [
        _step(_K.PROPOSE, embargo),
        _create(ALICE, embargo),
        _create(BOB, embargo),
    ]


def _apply_all(
    case_file: EmbargoCaseFile, changes: list[EmbargoChange]
) -> EmbargoCaseFile:
    for change in changes:
        case_file = apply_embargo_change(case_file, change)
    return case_file


def _entry(case_file: EmbargoCaseFile, embargo: EmbargoEvent):
    entry = case_file.case.embargo_register_entry(embargo.id_)
    assert entry is not None
    return entry


def _statuses(case_file: EmbargoCaseFile) -> dict[str, EmbargoRegisterStatus]:
    return {e.embargo_id: e.status for e in case_file.case.embargo_register}


def _dump(case_file: EmbargoCaseFile) -> dict:
    return {
        "case": case_file.case.model_dump(mode="json"),
        "participants": {
            a: p.model_dump(mode="json")
            for a, p in sorted(case_file.participants.items())
        },
    }


#: A negotiation exercising every register step and every row verb.
_LEDGER: list[EmbargoChange] = [
    *_proposed(E1),
    _update(ALICE, E1, _S.AGREED),
    _step(_K.ACTIVATE, E1),
    *_proposed(E2),
    *_proposed(E3),
    _row(
        ConsentRowVerb.UPDATE,
        BOB,
        E2,
        _S.INVITED,
        rsvp_deadline=_END - timedelta(days=150),
    ),
    _step(_K.REJECT, E3),
    _step(_K.ACTIVATE, E2),
    _update(ALICE, E2, _S.AGREED),
    _step(_K.TERMINATE, E2),
]


class TestRegisterSteps:
    """The act's own activity carries the whole register step."""

    @pytest.mark.spec("EMB-18-006")
    def test_activate_supersedes_the_embargo_in_force(self):
        case_file = _apply_all(
            _case_file(),
            [*_proposed(E1), _step(_K.ACTIVATE, E1), *_proposed(E2)],
        )
        after = apply_embargo_change(case_file, _step(_K.ACTIVATE, E2))
        assert _statuses(after) == {
            E1.id_: EmbargoRegisterStatus.SUPERSEDED,
            E2.id_: EmbargoRegisterStatus.ACTIVE,
        }
        assert _entry(after, E2).replaces == E1.id_
        assert after.case.em_state == EM.ACTIVE

    def test_terminate_cancels_every_open_proposal(self):
        case_file = _apply_all(
            _case_file(),
            [
                *_proposed(E1),
                _step(_K.ACTIVATE, E1),
                *_proposed(E2),
                *_proposed(E3),
            ],
        )
        termination = EmbargoTermination.end_time_reached()
        after = apply_embargo_change(
            case_file,
            RegisterStep(
                kind=_K.TERMINATE, embargo=E1.id_, termination=termination
            ),
        )
        assert _statuses(after) == {
            E1.id_: EmbargoRegisterStatus.TERMINATED,
            E2.id_: EmbargoRegisterStatus.CANCELLED,
            E3.id_: EmbargoRegisterStatus.CANCELLED,
        }
        assert after.case.embargo_termination == termination
        assert after.case.em_state == EM.EXITED

    def test_reject_and_threat_cancel_close_one_proposal(self):
        case_file = _apply_all(_case_file(), [*_proposed(E1), *_proposed(E2)])
        after = _apply_all(
            case_file, [_step(_K.REJECT, E1), _step(_K.CANCEL, E2)]
        )
        assert _statuses(after) == {
            E1.id_: EmbargoRegisterStatus.REJECTED,
            E2.id_: EmbargoRegisterStatus.CANCELLED,
        }
        assert after.case.em_state == EM.NONE

    def test_a_proposal_carries_its_embargo_inline(self):
        after = apply_embargo_change(_case_file(), _step(_K.PROPOSE, E1))
        assert _entry(after, E1).embargo == E1

    def test_terminate_ends_only_the_embargo_it_names(self):
        """Never "whatever is active locally" (#4294 AC-3)."""
        case_file = _apply_all(
            _case_file(), [*_proposed(E1), _step(_K.ACTIVATE, E1)]
        )
        with pytest.raises(VultronEntryRefusedError, match="in force"):
            apply_embargo_change(case_file, _step(_K.TERMINATE, E2))

    @pytest.mark.spec("EMB-18-006")
    def test_a_step_whose_em_move_is_not_a_transition_is_refused(
        self, monkeypatch
    ):
        """The EM check is part of the register step (ADR-0130, AC-2)."""
        case_file = _apply_all(_case_file(), _proposed(E1))
        before = _dump(case_file)
        monkeypatch.setattr(
            embargo_register, "is_em_transition", lambda *_: False
        )
        with pytest.raises(VultronEntryRefusedError, match="EM transition"):
            apply_embargo_change(case_file, _step(_K.ACTIVATE, E1))
        assert _dump(case_file) == before

    @pytest.mark.parametrize(
        "kind, field",
        [(_K.TERMINATE, None), (_K.ACTIVATE, "termination")],
    )
    def test_the_termination_fits_the_kind(self, kind, field):
        termination = EmbargoTermination.early() if field else None
        with pytest.raises(ValueError, match="termination"):
            RegisterStep(kind=kind, embargo=E1.id_, termination=termination)

    def test_only_a_proposal_carries_the_embargo_object(self):
        with pytest.raises(ValueError, match="only PROPOSE"):
            RegisterStep(kind=_K.ACTIVATE, embargo=E1)


class TestConsentRows:
    """Each consent row is its own entry, checked against its starting state."""

    def _proposed_file(self) -> EmbargoCaseFile:
        return _apply_all(_case_file(), _proposed(E1))

    def test_a_created_row_is_stored_as_carried(self):
        case_file = apply_embargo_change(_case_file(), _step(_K.PROPOSE, E1))
        after = apply_embargo_change(case_file, _create(ALICE, E1))
        row = after.participants[ALICE].embargo_consents[0]
        assert row == _create(ALICE, E1).row
        assert row.id_ == EmbargoConsent.build_id(E1.id_, ALICE)
        assert after.participants[BOB] is case_file.participants[BOB]

    def test_an_updated_row_replaces_the_held_one(self):
        after = apply_embargo_change(
            self._proposed_file(), _update(BOB, E1, _S.DECLINED)
        )
        assert after.participants[BOB].consent_for(E1.id_) == _S.DECLINED

    def test_a_fresh_deadline_on_an_invited_row_is_an_update(self):
        first = _END - timedelta(days=100)
        later = _END - timedelta(days=90)
        case_file = apply_embargo_change(
            self._proposed_file(),
            _row(ConsentRowVerb.UPDATE, BOB, E1, _S.INVITED, first),
        )
        after = apply_embargo_change(
            case_file,
            _row(ConsentRowVerb.UPDATE, BOB, E1, _S.INVITED, later),
        )
        assert after.participants[BOB].rsvp_deadline_for(E1.id_) == later

    @pytest.mark.parametrize(
        "change, problem",
        [
            (_create(ALICE, E1), "already holds a row"),
            (_update(ALICE, E1, _S.UNINVITED), "changes nothing"),
            (_update(ALICE, E1, _S.TIMED_OUT), "no consent transition"),
            (_update(ALICE, E2, _S.AGREED), "no register entry"),
            (
                _update("https://example.org/actors/eve", E1, _S.AGREED),
                "no participant record",
            ),
        ],
    )
    def test_a_row_that_does_not_start_where_the_entry_implies_is_refused(
        self, change, problem
    ):
        case_file = self._proposed_file()
        before = _dump(case_file)
        with pytest.raises(VultronEntryRefusedError, match=problem):
            apply_embargo_change(case_file, change)
        assert _dump(case_file) == before

    def test_a_row_for_a_final_entry_is_frozen(self):
        case_file = apply_embargo_change(
            self._proposed_file(), _step(_K.REJECT, E1)
        )
        with pytest.raises(VultronEntryRefusedError, match="REJECTED"):
            apply_embargo_change(case_file, _update(ALICE, E1, _S.AGREED))

    def test_an_update_needs_a_held_row(self):
        case_file = apply_embargo_change(_case_file(), _step(_K.PROPOSE, E1))
        with pytest.raises(VultronEntryRefusedError, match="holds no row"):
            apply_embargo_change(case_file, _update(ALICE, E1, _S.AGREED))

    def test_a_row_change_names_its_participant(self):
        with pytest.raises(ValueError, match="names no participant"):
            ConsentRowChange(
                verb=ConsentRowVerb.UPDATE,
                row=EmbargoConsent(embargo_id=E1.id_, state=_S.AGREED),
            )


@pytest.mark.spec("CM-23-016")
@pytest.mark.spec("CLP-07-013")
def test_two_replicas_applying_one_ledger_hold_identical_case_files():
    """Every id and time in the result came from an entry."""
    seed = _case_file()
    first = _apply_all(seed, _LEDGER)
    second = _apply_all(seed, _LEDGER)
    assert first.case is not second.case
    assert _dump(first) == _dump(second)
    assert first.case.em_state == EM.EXITED


def test_applying_an_entry_leaves_its_input_as_it_was():
    case_file = _case_file()
    before = _dump(case_file)
    after = _apply_all(case_file, _LEDGER)
    assert _dump(case_file) == before
    assert changed_objects(case_file, after) == [
        after.case,
        after.participants[ALICE],
        after.participants[BOB],
    ]


@pytest.mark.spec("CM-23-016")
def test_a_dropped_entry_refuses_the_next_and_is_never_patched_over():
    """AC-4: a replica missing one entry refuses the one after it.

    Without the owner's ``ACTIVATE`` of E1, the revision's activation finds
    nothing in force to supersede, and the consent row the activation's
    successor updates was never created.  Neither is written.
    """
    ledger = [*_proposed(E1), _step(_K.ACTIVATE, E1), *_proposed(E2)]
    dropped = ledger.index(_step(_K.ACTIVATE, E1))
    replica = _apply_all(_case_file(), ledger[:dropped])
    replica = _apply_all(replica, ledger[dropped + 1 :])
    before = _dump(replica)
    with pytest.raises(VultronEntryRefusedError):
        apply_embargo_change(
            replica,
            RegisterStep(
                kind=_K.TERMINATE,
                embargo=E1.id_,
                termination=EmbargoTermination.early(),
            ),
        )
    assert _dump(replica) == before

    rows_dropped = _apply_all(_case_file(), [_step(_K.PROPOSE, E1)])
    with pytest.raises(VultronEntryRefusedError, match="holds no row"):
        apply_embargo_change(rows_dropped, _update(ALICE, E1, _S.AGREED))


class _NoClock:
    """A ``datetime`` stand-in whose clock reads fail the test."""

    @staticmethod
    def now(*_args, **_kwargs):
        raise AssertionError("the apply function read the clock")


@pytest.mark.spec("CM-23-016")
def test_the_apply_function_reads_no_clock_mints_no_id_and_reads_no_store(
    monkeypatch,
):
    """AC-5: no clock, no minted id, and only the case file it is given.

    The function takes no store: its only inputs are the case file and the
    change.  Every clock read and id mint in core goes through
    ``now_utc`` and ``_new_urn``; both fail here.
    """
    case_file = _case_file()
    monkeypatch.setattr(model_helpers, "datetime", _NoClock)

    def _no_mint() -> str:
        raise AssertionError("the apply function minted an id")

    monkeypatch.setattr(model_helpers.uuid, "uuid4", _no_mint)
    after = _apply_all(case_file, _LEDGER)
    assert after.case.em_state == EM.EXITED
