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

"""The shared recipient selection (CM-10-004, CM-10-007, #4046 AC-2/AC-3)."""

import logging

import pytest

from test.support.embargo_register import activate
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.participants.recipients import (
    case_content_participants,
    case_content_recipients,
    closed_participant_ledger_cutoff,
    entry_records_own_closure,
    inactive_joined_participants,
    inert_participants,
    invitation_recipients,
    is_case_content_recipient,
    ledger_entry_recipients,
    may_act_on_case,
    reporter_introduction_recipients,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole

_CASE_ID = "https://example.org/cases/recipients-001"
_SENDER = "https://example.org/actors/sender"
_SIGNATORY = "https://example.org/actors/signatory"
_INVITED = "https://example.org/actors/invited"
_UNJOINED = "https://example.org/actors/unjoined"
_CLOSED = "https://example.org/actors/closed"
_EMBARGO_ID = f"{_CASE_ID}/embargoes/e1"


@pytest.fixture()
def dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=_SENDER)


def _seat(
    dl: SqliteDataLayer,
    case: VulnerabilityCase,
    actor_id: str,
    *,
    consent: EmbargoConsentState | None = EmbargoConsentState.AGREED,
    joined: bool = True,
    rm_state: RM = RM.ACCEPTED,
    store: bool = True,
    roles: tuple[CVDRole, ...] = (),
) -> CaseParticipant:
    participant = CaseParticipant(
        id_=f"{_CASE_ID}/participants/{actor_id.rsplit('/', 1)[-1]}",
        attributed_to=actor_id,
        context=_CASE_ID,
        case_roles=list(roles),
        joined=joined,
        embargo_consents=(
            [EmbargoConsent(embargo_id=_EMBARGO_ID, state=consent)]
            if consent is not None
            else []
        ),
        participant_statuses=[
            ParticipantStatus(
                context=_CASE_ID,
                attributed_to=actor_id,
                rm=RmDimension(state=rm_state),
            )
        ],
    )
    if store:
        dl.create(participant)
    case.case_participants.append(participant.id_)
    case.actor_participant_index[actor_id] = participant.id_
    return participant


def _embargoed_case(dl: SqliteDataLayer) -> VulnerabilityCase:
    """A case under an active embargo with one participant of each kind."""
    case = VulnerabilityCase(id_=_CASE_ID, attributed_to=_SENDER)
    activate(case, _EMBARGO_ID)
    _seat(dl, case, _SENDER)
    _seat(dl, case, _SIGNATORY)
    _seat(dl, case, _INVITED, consent=EmbargoConsentState.INVITED)
    _seat(
        dl, case, _UNJOINED, consent=EmbargoConsentState.INVITED, joined=False
    )
    _seat(dl, case, _CLOSED, rm_state=RM.CLOSED)
    return case


@pytest.mark.spec("CM-10-004", "CM-23-004")
def test_case_content_reaches_only_active_open_participants(
    dl: SqliteDataLayer,
) -> None:
    """Inert participants and a closed signatory are sent no case content."""
    case = _embargoed_case(dl)
    assert case_content_recipients(case, dl, excluding={_SENDER}) == [
        _SIGNATORY
    ]


@pytest.mark.spec("CM-10-004", "CM-23-004")
def test_with_no_embargo_every_joined_open_participant_is_active(
    dl: SqliteDataLayer,
) -> None:
    case = VulnerabilityCase(id_=_CASE_ID, attributed_to=_SENDER)
    _seat(dl, case, _SIGNATORY, consent=None)
    _seat(dl, case, _INVITED, consent=EmbargoConsentState.DECLINED)
    _seat(dl, case, _UNJOINED, joined=False)
    _seat(dl, case, _CLOSED, rm_state=RM.CLOSED)
    assert case_content_recipients(case, dl) == [_SIGNATORY, _INVITED]


@pytest.mark.spec("CM-10-007")
def test_invitations_reach_inert_participants_but_not_closed_ones(
    dl: SqliteDataLayer,
) -> None:
    case = _embargoed_case(dl)
    assert invitation_recipients(case, dl, excluding={_SENDER}) == [
        _SIGNATORY,
        _INVITED,
        _UNJOINED,
    ]


@pytest.mark.spec("CM-23-004")
def test_inert_participants_is_the_roster_minus_the_content_recipients(
    dl: SqliteDataLayer,
) -> None:
    case = _embargoed_case(dl)
    assert inert_participants(case, dl) == {_INVITED, _UNJOINED, _CLOSED}


@pytest.mark.spec("CM-23-004")
def test_closed_participant_has_no_stream_to_pause(
    dl: SqliteDataLayer,
) -> None:
    """A closed, withheld participant is not paused: it is sent nothing."""
    case = _embargoed_case(dl)
    _seat(
        dl,
        case,
        "https://example.org/actors/closed-invited",
        consent=EmbargoConsentState.INVITED,
        rm_state=RM.CLOSED,
    )
    assert inactive_joined_participants(case, dl, excluding={_SENDER}) == [
        _INVITED
    ]


@pytest.mark.spec("CM-10-004")
def test_single_recipient_check(dl: SqliteDataLayer) -> None:
    case = _embargoed_case(dl)
    assert is_case_content_recipient(case, dl, _SIGNATORY)
    assert not is_case_content_recipient(case, dl, _INVITED)
    assert not is_case_content_recipient(case, dl, _UNJOINED)
    assert not is_case_content_recipient(
        case, dl, "https://example.org/actors/stranger"
    )


@pytest.mark.spec("CM-10-004")
def test_unresolvable_record_is_withheld_with_a_warning(
    dl: SqliteDataLayer, caplog: pytest.LogCaptureFixture
) -> None:
    """Fail closed: a roster entry the case cannot vouch for gets nothing."""
    case = VulnerabilityCase(id_=_CASE_ID, attributed_to=_SENDER)
    _seat(dl, case, _SIGNATORY)
    _seat(dl, case, _INVITED, store=False)
    with caplog.at_level(logging.WARNING):
        assert case_content_recipients(case, dl) == [_SIGNATORY]
        assert invitation_recipients(case, dl) == [_SIGNATORY]
        assert not is_case_content_recipient(case, dl, _INVITED)
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any(_INVITED in r.getMessage() for r in warnings)


def test_stored_record_wins_over_a_stale_inline_copy(
    dl: SqliteDataLayer,
) -> None:
    """The stored record is consulted first, as ``iter_case_participants`` does.

    Participant writes save the stored record, so an inline copy the case
    carries can be stale.
    """
    case = VulnerabilityCase(id_=_CASE_ID, attributed_to=_SENDER)
    stored = _seat(dl, case, _SIGNATORY, joined=False)
    case.case_participants[0] = stored.model_copy(update={"joined": True})
    assert case_content_recipients(case, dl) == []


def test_inline_copy_is_the_fallback_when_nothing_is_stored(
    dl: SqliteDataLayer,
) -> None:
    """During bootstrap the inline copy is all there is, and it is used."""
    case = VulnerabilityCase(id_=_CASE_ID, attributed_to=_SENDER)
    case.case_participants[0] = _seat(dl, case, _SIGNATORY, store=False)
    assert case_content_recipients(case, dl) == [_SIGNATORY]


def test_case_content_participants_pairs_each_recipient_with_its_record(
    dl: SqliteDataLayer,
) -> None:
    """The pairs carry the record the selection resolved, inline-only included.

    A caller that narrows by a record field (the bootstrap reporter filter)
    must not read the record again: an inline-only record would vanish.
    """
    case = VulnerabilityCase(id_=_CASE_ID, attributed_to=_SENDER)
    stored = _seat(dl, case, _SIGNATORY)
    inline = _seat(dl, case, _INVITED, store=False)
    case.case_participants[1] = inline
    _seat(dl, case, _UNJOINED, joined=False)
    pairs = case_content_participants(case, dl)
    assert [(a, p.id_) for a, p in pairs] == [
        (_SIGNATORY, stored.id_),
        (_INVITED, inline.id_),
    ]
    assert [a for a, _ in pairs] == case_content_recipients(case, dl)


_REMOVED = "https://example.org/actors/removed"


@pytest.mark.spec("CM-31-001", "CM-10-007")
@pytest.mark.parametrize("embargo", [False, True])
def test_removed_participant_gets_no_case_content(
    dl: SqliteDataLayer, embargo: bool
) -> None:
    """The shared selection asks the case-level check, which reads the fact.

    The removed participant is a signatory and joined; only the removal fact
    makes it inert.  It stays on the roster (CM-19-001).
    """
    case = VulnerabilityCase(id_=_CASE_ID, attributed_to=_SENDER)
    if embargo:
        activate(case, _EMBARGO_ID)
    _seat(dl, case, _SIGNATORY)
    removed = _seat(dl, case, _REMOVED)
    removed.removal_activity = f"{_CASE_ID}/activities/remove-1"
    dl.save(removed)

    assert case_content_recipients(case, dl) == [_SIGNATORY]
    assert not is_case_content_recipient(case, dl, _REMOVED)
    assert inert_participants(case, dl) == {_REMOVED}
    # Joined but not active, so its ledger stream is paused for backfill.
    assert inactive_joined_participants(case, dl) == [_REMOVED]
    assert _REMOVED in case.actor_participant_index


# ---------------------------------------------------------------------------
# CM-23-004: a closed participant receives its own closure entries only
# ---------------------------------------------------------------------------


def _entry(
    log_index: int,
    semantic_type: str,
    *,
    object_id: str,
    actor: str = _SENDER,
) -> CaseLedgerEntry:
    return CaseLedgerEntry(
        case_id=_CASE_ID,
        log_index=log_index,
        log_object_id=object_id,
        semantic_type=semantic_type,
        payload_snapshot={"type": "Add", "actor": actor},
        prev_log_hash="0" * 64,
        entry_hash=f"{log_index:064d}",
    )


def _close_case_entry(log_index: int, leaver: str) -> CaseLedgerEntry:
    return _entry(
        log_index,
        "close_case",
        object_id=f"{_CASE_ID}/activities/leave-{log_index}",
        actor=leaver,
    )


def _status_entry(log_index: int, status_id: str) -> CaseLedgerEntry:
    return _entry(
        log_index,
        "add_participant_status_to_participant",
        object_id=status_id,
    )


def _closed_status_id(record: CaseParticipant) -> str:
    status_id = record.participant_statuses[-1].id_
    assert status_id
    return status_id


@pytest.mark.spec("CM-23-004", "CM-23-001")
def test_leaver_receives_the_entries_recording_its_own_closure(
    dl: SqliteDataLayer,
) -> None:
    """Its close_case entry and its closure steps reach a closed leaver."""
    case = _embargoed_case(dl)
    closed = dl.read(case.actor_participant_index[_CLOSED])
    assert isinstance(closed, CaseParticipant)
    for entry in (
        _close_case_entry(5, _CLOSED),
        _status_entry(6, _closed_status_id(closed)),
    ):
        assert ledger_entry_recipients(
            case, dl, entry, excluding={_SENDER}
        ) == [_SIGNATORY, _CLOSED]


@pytest.mark.spec("CM-23-004", "CM-23-002")
def test_closed_participant_receives_nothing_about_anyone_else(
    dl: SqliteDataLayer,
) -> None:
    """Later entries, another actor's closure and case_fully_closed skip it."""
    case = _embargoed_case(dl)
    signatory = dl.read(case.actor_participant_index[_SIGNATORY])
    assert isinstance(signatory, CaseParticipant)
    for entry in (
        _close_case_entry(7, _SIGNATORY),
        _status_entry(8, _closed_status_id(signatory)),
        _entry(9, "case_fully_closed", object_id=f"{_CASE_ID}/leave-9"),
        _entry(10, "add_note_to_case", object_id=f"{_CASE_ID}/notes/n1"),
    ):
        assert ledger_entry_recipients(
            case, dl, entry, excluding={_SENDER}
        ) == [_SIGNATORY]


@pytest.mark.spec("CM-23-004", "CM-10-004", "CM-31-001")
@pytest.mark.parametrize("why_inert", ["embargo-withheld", "removed"])
def test_own_closure_entries_never_widen_entitlement(
    dl: SqliteDataLayer, why_inert: str
) -> None:
    """A closed participant that is inert is not sent its closure either.

    Inert because the active embargo withholds it, or because it was
    removed (CM-31-001): neither its ``close_case`` entry nor its closure
    status entry reaches it.
    """
    case = _embargoed_case(dl)
    actor_id = "https://example.org/actors/closed-inert"
    inert_closed = _seat(
        dl,
        case,
        actor_id,
        consent=(
            EmbargoConsentState.INVITED
            if why_inert == "embargo-withheld"
            else EmbargoConsentState.AGREED
        ),
        rm_state=RM.CLOSED,
    )
    if why_inert == "removed":
        inert_closed.removal_activity = f"{_CASE_ID}/activities/remove-1"
        dl.save(inert_closed)
    for entry in (
        _close_case_entry(5, actor_id),
        _status_entry(6, _closed_status_id(inert_closed)),
    ):
        assert entry_records_own_closure(entry, actor_id, inert_closed)
        assert ledger_entry_recipients(
            case, dl, entry, excluding={_SENDER}
        ) == [_SIGNATORY]


@pytest.mark.spec("CM-23-004")
@pytest.mark.spec("OID-01-006")
def test_a_slash_spelled_leave_still_records_the_leavers_own_closure(
    dl: SqliteDataLayer,
) -> None:
    """The ``close_case`` snapshot keeps the leaver's trailing slash; the
    roster names it canonically, and the two are one actor."""
    case = _embargoed_case(dl)
    closed = dl.read(case.actor_participant_index[_CLOSED])
    assert isinstance(closed, CaseParticipant)
    entry = _close_case_entry(5, _CLOSED + "/")
    assert entry_records_own_closure(entry, _CLOSED, closed)
    assert not entry_records_own_closure(
        _close_case_entry(6, _SIGNATORY + "/"), _CLOSED, closed
    )


@pytest.mark.spec("CM-23-004")
def test_closed_participant_ledger_cutoff_is_its_last_own_closure_entry(
    dl: SqliteDataLayer,
) -> None:
    case = _embargoed_case(dl)
    closed = dl.read(case.actor_participant_index[_CLOSED])
    assert isinstance(closed, CaseParticipant)
    entries = [
        _entry(0, "create_case", object_id=_CASE_ID),
        _close_case_entry(1, _CLOSED),
        _status_entry(2, _closed_status_id(closed)),
        _entry(3, "case_fully_closed", object_id=f"{_CASE_ID}/leave-3"),
    ]
    assert closed_participant_ledger_cutoff(case, dl, _CLOSED, entries) == 2
    assert (
        closed_participant_ledger_cutoff(case, dl, _CLOSED, entries[:1]) == -1
    )
    # No cutoff for a participant that has not closed, or one not listed.
    assert (
        closed_participant_ledger_cutoff(case, dl, _SIGNATORY, entries) is None
    )
    assert (
        closed_participant_ledger_cutoff(
            case, dl, "https://example.org/actors/stranger", entries
        )
        is None
    )


@pytest.mark.spec("CBT-01-001", "CM-10-004", "CM-10-007", "CM-23-004")
def test_reporter_introduction_reaches_only_active_open_reporters(
    dl: SqliteDataLayer,
) -> None:
    """The receiver introduces only active, open REPORTER participants.

    An inert reporter, a closed reporter, and a participant holding neither
    role are left out; the excluded receiver and CASE_MANAGER are too.
    """
    case = VulnerabilityCase(id_=_CASE_ID, attributed_to=_SENDER)
    activate(case, _EMBARGO_ID)
    _seat(dl, case, _SENDER, roles=(CVDRole.CASE_OWNER,))
    _seat(dl, case, _SIGNATORY, roles=(CVDRole.REPORTER,))
    _seat(
        dl,
        case,
        _INVITED,
        consent=EmbargoConsentState.INVITED,
        roles=(CVDRole.REPORTER,),
    )
    _seat(dl, case, _CLOSED, rm_state=RM.CLOSED, roles=(CVDRole.REPORTER,))
    _seat(dl, case, _UNJOINED, roles=(CVDRole.VENDOR,))
    assert reporter_introduction_recipients(case, dl, excluding={_SENDER}) == [
        _SIGNATORY
    ]


# ---------------------------------------------------------------------------
# CM-23-018: the sender predicate behind the ACTIVE_PARTICIPANT standing
# ---------------------------------------------------------------------------


@pytest.mark.spec("CM-23-018", "CM-10-004")
def test_only_an_active_open_participant_may_act_on_the_case(
    dl: SqliteDataLayer,
) -> None:
    """Closed, inert, removed and unlisted senders may not act."""
    case = _embargoed_case(dl)
    removed = _seat(dl, case, _REMOVED)
    removed.removal_activity = f"{_CASE_ID}/activities/remove-1"
    dl.save(removed)

    assert may_act_on_case(case, dl, _SIGNATORY)
    for actor_id in (
        _CLOSED,
        _INVITED,
        _UNJOINED,
        _REMOVED,
        "https://example.org/actors/stranger",
    ):
        assert not may_act_on_case(case, dl, actor_id), actor_id


@pytest.mark.spec("CM-23-018", "SYNC-03-005")
def test_a_closed_participant_keeps_the_recipient_check_but_not_the_sender_one(
    dl: SqliteDataLayer,
) -> None:
    """The bare active check still admits a closed participant (its replay)."""
    case = _embargoed_case(dl)
    assert is_case_content_recipient(case, dl, _CLOSED)
    assert not may_act_on_case(case, dl, _CLOSED)


@pytest.mark.spec("CM-23-018")
def test_the_sender_predicate_matches_the_case_content_selection(
    dl: SqliteDataLayer,
) -> None:
    """A sender may act exactly when it would be sent the case's content."""
    case = _embargoed_case(dl)
    may_act = [
        a for a in case.actor_participant_index if may_act_on_case(case, dl, a)
    ]
    assert may_act == case_content_recipients(case, dl)


@pytest.mark.spec("CM-23-018")
def test_an_unresolvable_sender_record_may_not_act(
    dl: SqliteDataLayer,
) -> None:
    case = VulnerabilityCase(id_=_CASE_ID, attributed_to=_SENDER)
    _seat(dl, case, _SIGNATORY, store=False)
    case.case_participants.clear()
    assert not may_act_on_case(case, dl, _SIGNATORY)
