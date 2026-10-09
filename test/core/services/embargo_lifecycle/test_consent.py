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


"""record_participant_consent — PEC-only operations that leave EM state alone
(consent.py)."""

from datetime import timedelta
from typing import cast

import pytest

from test.support.embargo_register import (
    activate,
    propose,
    reject,
    write_consent_rows,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models._helpers import days_from_now_utc, now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState as ECS,
    PEC_Trigger,
)
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronNotFoundError,
    VultronValidationError,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service

from .conftest import (
    _consent_of,
    _consents_of,
    _is_signatory,
    _make_actor,
    _make_case,
    _make_embargo,
    _seed_consent,
)


def test_record_participant_consent_accept_trigger(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """AGREE moves the INVITED row for that embargo to AGREED."""
    owner, dl = owner_and_dl
    case, participants = _make_case(dl, owner.id_)
    owner_participant_id = participants[0].id_
    embargo = _make_embargo(dl, case.id_)
    propose(case, embargo.id_)
    dl.save(case)
    _seed_consent(dl, owner_participant_id, embargo.id_, ECS.INVITED)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.record_participant_consent(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
        pec_trigger=PEC_Trigger.AGREE,
    )

    assert result.case_changed is False
    assert result.case_embargo_changed is False
    assert [
        (c.embargo_id, c.consent_before, c.consent_after)
        for c in result.participant_changes
    ] == [(embargo.id_, "INVITED", "AGREED")]
    assert _consent_of(dl, owner_participant_id, embargo.id_) == "AGREED"


def test_record_participant_consent_decline_trigger(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """DECLINE moves an AGREED row to DECLINED and touches no other row."""
    owner, dl = owner_and_dl
    case, participants = _make_case(dl, owner.id_)
    owner_participant_id = participants[0].id_
    embargo = _make_embargo(dl, case.id_)
    propose(case, embargo.id_)
    dl.save(case)
    other = _make_embargo(dl, case.id_, days=90)
    _seed_consent(dl, owner_participant_id, embargo.id_, ECS.AGREED)
    _seed_consent(dl, owner_participant_id, other.id_, ECS.AGREED)

    lifecycle = EmbargoLifecycle(persistence=dl)
    lifecycle.record_participant_consent(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
        pec_trigger=PEC_Trigger.DECLINE,
    )

    assert _consents_of(dl, owner_participant_id) == {
        embargo.id_: "DECLINED",
        other.id_: "AGREED",
    }


def test_record_participant_consent_actor_not_in_case(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Actor without a CaseParticipant: result has no changes, no crash."""
    owner, dl = owner_and_dl
    outsider = _make_actor(dl, "Outsider Org")
    case, _ = _make_case(dl, owner.id_)
    embargo = _make_embargo(dl, case.id_)
    propose(case, embargo.id_)
    dl.save(case)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.record_participant_consent(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=outsider.id_,  # not in case
        pec_trigger=PEC_Trigger.AGREE,
    )

    assert result.participant_changes == []
    assert result.case_changed is False


def test_record_participant_consent_illegal_trigger_raises(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """AC-5: illegal trigger raises VultronInvalidStateTransitionError.

    TIME_OUT from AGREED is not a valid consent transition.
    apply_pec_transition() is fail-closed and raises; this test pins that
    behavior and confirms record_participant_consent propagates it, leaving
    the row as it was.
    """
    owner, dl = owner_and_dl
    case, participants = _make_case(dl, owner.id_)
    owner_participant_id = participants[0].id_
    embargo = _make_embargo(dl, case.id_)
    propose(case, embargo.id_)
    dl.save(case)
    _seed_consent(dl, owner_participant_id, embargo.id_, ECS.AGREED)

    lifecycle = EmbargoLifecycle(persistence=dl)
    with pytest.raises(VultronInvalidStateTransitionError):
        lifecycle.record_participant_consent(
            case_id=case.id_,
            embargo_id=embargo.id_,
            actor_id=owner.id_,
            pec_trigger=PEC_Trigger.TIME_OUT,  # illegal from AGREED
        )
    assert _consent_of(dl, owner_participant_id, embargo.id_) == "AGREED"


# ---------------------------------------------------------------------------
# Tests: record_embargo_rejection — the consent half of a Reject (MSM-07-004)
# ---------------------------------------------------------------------------


def _active_with_revision(dl: SqliteDataLayer, owner: as_Service):
    """Owner (AGREED A) and a finder (AGREED A and B); A active, B proposed."""
    finder = _make_actor(dl, "Finder Org")
    case, (owner_p, finder_p) = _make_case(
        dl, owner.id_, extra_participant_ids=[finder.id_]
    )
    active = _make_embargo(dl, case.id_)
    revision = _make_embargo(dl, case.id_, days=90)
    activate(case, active.id_)
    propose(case, revision.id_)
    dl.save(case)
    write_consent_rows(dl, case)
    _seed_consent(dl, owner_p.id_, active.id_, ECS.AGREED)
    _seed_consent(dl, finder_p.id_, active.id_, ECS.AGREED)
    _seed_consent(dl, finder_p.id_, revision.id_, ECS.AGREED)
    return case, finder, owner_p.id_, finder_p.id_, active.id_, revision.id_


@pytest.mark.spec("MSM-07-004")
@pytest.mark.spec("CM-18-003")
def test_record_embargo_rejection_of_the_active_embargo_is_withdrawal(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Withdrawal declines the active row and every agreed open proposal."""
    owner, dl = owner_and_dl
    case, finder, _owner_p, finder_p, active_id, rev = _active_with_revision(
        dl, owner
    )

    result = EmbargoLifecycle(persistence=dl).record_embargo_rejection(
        case_id=case.id_, actor_id=finder.id_, embargo_id=active_id
    )

    assert result.em_before == result.em_after == EM.REVISE
    assert result.case_changed is False
    assert {
        (c.embargo_id, c.consent_before, c.consent_after)
        for c in result.participant_changes
    } == {
        (active_id, "AGREED", "DECLINED"),
        (rev, "AGREED", "DECLINED"),
    }
    assert _consents_of(dl, finder_p) == {
        active_id: "DECLINED",
        rev: "DECLINED",
    }
    assert not _is_signatory(dl, case.id_, finder_p)


@pytest.mark.spec("MSM-07-004")
def test_record_embargo_rejection_of_a_proposed_revision_keeps_a_signatory(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    owner, dl = owner_and_dl
    case, finder, _owner_p, finder_p, active_id, rev = _active_with_revision(
        dl, owner
    )

    result = EmbargoLifecycle(persistence=dl).record_embargo_rejection(
        case_id=case.id_, actor_id=finder.id_, embargo_id=rev
    )

    assert [
        (c.embargo_id, c.consent_after) for c in result.participant_changes
    ] == [(rev, "DECLINED")]
    assert _consents_of(dl, finder_p) == {
        active_id: "AGREED",
        rev: "DECLINED",
    }
    assert _is_signatory(dl, case.id_, finder_p)
    # Recording consent decides nothing: B stays an open proposal.
    assert cast(VulnerabilityCase, dl.read(case.id_)).proposed_embargo_ids == [
        rev
    ]


@pytest.mark.spec("MSM-07-004")
def test_record_embargo_rejection_by_the_owner_declines_its_own_row(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """The owner's Reject(Invite) of a revision is its consent (ADR-0122).

    It declines row(B) like anyone's; the owner stays a signatory of A, and
    B stays open — the owner's decision is ``reject_embargo_proposal``.
    """
    owner, dl = owner_and_dl
    case, _finder, owner_p, _finder_p, active_id, rev = _active_with_revision(
        dl, owner
    )

    result = EmbargoLifecycle(persistence=dl).record_embargo_rejection(
        case_id=case.id_, actor_id=owner.id_, embargo_id=rev
    )

    assert [
        (c.embargo_id, c.consent_before, c.consent_after)
        for c in result.participant_changes
    ] == [(rev, "UNINVITED", "DECLINED")]
    assert _consents_of(dl, owner_p) == {
        active_id: "AGREED",
        rev: "DECLINED",
    }
    assert _is_signatory(dl, case.id_, owner_p)
    assert cast(VulnerabilityCase, dl.read(case.id_)).proposed_embargo_ids == [
        rev
    ]


def test_record_embargo_rejection_of_an_unknown_embargo_raises(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    owner, dl = owner_and_dl
    case, finder, _o, finder_p, active_id, rev = _active_with_revision(
        dl, owner
    )
    stranger = _make_embargo(dl, case.id_, days=10)

    with pytest.raises(VultronValidationError, match="neither the active"):
        EmbargoLifecycle(persistence=dl).record_embargo_rejection(
            case_id=case.id_, actor_id=finder.id_, embargo_id=stranger.id_
        )
    assert _consents_of(dl, finder_p) == {
        active_id: "AGREED",
        rev: "AGREED",
    }


# ---------------------------------------------------------------------------
# record_embargo_invite — the relay's and the replay's one rule (EP-09-004)
# ---------------------------------------------------------------------------


@pytest.mark.spec("EP-09-004")
@pytest.mark.spec("CM-28-013")
def test_record_embargo_invite_invites_an_unasked_participant(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    owner, dl = owner_and_dl
    invitee = _make_actor(dl, "Invitee")
    case, participants = _make_case(dl, owner.id_, [invitee.id_])
    activate(case, _make_embargo(dl, case.id_).id_)
    embargo = _make_embargo(dl, case.id_)
    propose(case, embargo.id_)
    dl.save(case)
    write_consent_rows(dl, case)
    deadline = days_from_now_utc(7)

    result = EmbargoLifecycle(persistence=dl).record_embargo_invite(
        case_id=case.id_,
        invitee_id=invitee.id_,
        embargo_id=embargo.id_,
        rsvp_deadline=deadline,
    )

    assert result.em_before == result.em_after == EM.REVISE
    assert [
        (c.embargo_id, c.consent_before, c.consent_after)
        for c in result.participant_changes
    ] == [(embargo.id_, "UNINVITED", "INVITED")]
    record = cast(CaseParticipant, dl.read(participants[1].id_))
    assert record.consent_for(embargo.id_) == ECS.INVITED
    assert record.rsvp_deadline_for(embargo.id_) == deadline


@pytest.mark.spec("EP-09-004")
def test_record_embargo_invite_on_a_signatory_keeps_the_active_row_and_adds_the_revision(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A signatory asked about a revision stays bound and gains INVITED(B).

    The row belongs to the embargo the Invite names, so the AGREED row for
    the embargo in force is untouched (EP-09-004 is natural, not a no-op).
    """
    owner, dl = owner_and_dl
    invitee = _make_actor(dl, "Signatory")
    case, participants = _make_case(dl, owner.id_, [invitee.id_])
    active = _make_embargo(dl, case.id_)
    revision = _make_embargo(dl, case.id_, days=90)
    activate(case, active.id_)
    propose(case, revision.id_)
    dl.save(case)
    write_consent_rows(dl, case)
    _seed_consent(dl, participants[1].id_, active.id_, ECS.AGREED)

    result = EmbargoLifecycle(persistence=dl).record_embargo_invite(
        case_id=case.id_, invitee_id=invitee.id_, embargo_id=revision.id_
    )

    assert [
        (c.embargo_id, c.consent_after) for c in result.participant_changes
    ] == [(revision.id_, "INVITED")]
    assert _consents_of(dl, participants[1].id_) == {
        active.id_: "AGREED",
        revision.id_: "INVITED",
    }
    assert _is_signatory(dl, case.id_, participants[1].id_)


@pytest.mark.spec("CM-28-013")
def test_a_fresh_invite_without_a_deadline_drops_a_stale_one(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A passed deadline must not time out the row a new Invite just re-sent.

    The row is still INVITED, so the Invite moves no state; it replaces the
    row's deadline with its own (none here), and the stale one is gone.
    """
    owner, dl = owner_and_dl
    invitee = _make_actor(dl, "Signatory")
    case, participants = _make_case(dl, owner.id_, [invitee.id_])
    active = _make_embargo(dl, case.id_)
    revision = _make_embargo(dl, case.id_, days=90)
    activate(case, active.id_)
    propose(case, revision.id_)
    dl.save(case)
    write_consent_rows(dl, case)
    _seed_consent(dl, participants[1].id_, active.id_, ECS.AGREED)
    _seed_consent(
        dl,
        participants[1].id_,
        revision.id_,
        ECS.INVITED,
        rsvp_deadline=now_utc() - timedelta(days=1),
    )

    invited = EmbargoLifecycle(persistence=dl).record_embargo_invite(
        case_id=case.id_, invitee_id=invitee.id_, embargo_id=revision.id_
    )
    result = EmbargoLifecycle(persistence=dl).detect_and_apply_expiry(
        case_id=case.id_,
        actor_id=invitee.id_,
        embargo_id=revision.id_,
        now=now_utc(),
    )

    assert invited.participant_changes == []
    assert result.participant_changes == []
    record = cast(CaseParticipant, dl.read(participants[1].id_))
    assert record.consent_for(revision.id_) == ECS.INVITED
    assert record.rsvp_deadline_for(revision.id_) is None


@pytest.mark.spec("CM-28-013")
def test_a_fresh_invite_restamps_an_invited_rows_deadline(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """An Invite re-sent to an INVITED row replaces that row's deadline."""
    owner, dl = owner_and_dl
    invitee = _make_actor(dl, "Invitee")
    case, participants = _make_case(dl, owner.id_, [invitee.id_])
    embargo = _make_embargo(dl, case.id_)
    propose(case, embargo.id_)
    dl.save(case)
    write_consent_rows(dl, case)
    first = days_from_now_utc(3)
    second = days_from_now_utc(7)
    lifecycle = EmbargoLifecycle(persistence=dl)

    lifecycle.record_embargo_invite(
        case_id=case.id_,
        invitee_id=invitee.id_,
        embargo_id=embargo.id_,
        rsvp_deadline=first,
    )
    again = lifecycle.record_embargo_invite(
        case_id=case.id_,
        invitee_id=invitee.id_,
        embargo_id=embargo.id_,
        rsvp_deadline=second,
    )

    assert again.participant_changes == []
    record = cast(CaseParticipant, dl.read(participants[1].id_))
    assert record.consent_for(embargo.id_) == ECS.INVITED
    assert record.rsvp_deadline_for(embargo.id_) == second


@pytest.mark.spec("EP-09-004")
def test_record_embargo_invite_leaves_an_agreed_row_for_that_embargo(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """INVITE is illegal from AGREED on the same embargo: recorded no-op."""
    owner, dl = owner_and_dl
    invitee = _make_actor(dl, "Signatory")
    case, participants = _make_case(dl, owner.id_, [invitee.id_])
    embargo = _make_embargo(dl, case.id_)
    propose(case, embargo.id_)
    dl.save(case)
    _seed_consent(dl, participants[1].id_, embargo.id_, ECS.AGREED)

    result = EmbargoLifecycle(persistence=dl).record_embargo_invite(
        case_id=case.id_, invitee_id=invitee.id_, embargo_id=embargo.id_
    )

    assert result.participant_changes == []
    assert _consent_of(dl, participants[1].id_, embargo.id_) == "AGREED"


def test_record_embargo_invite_raises_for_an_unknown_invitee(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)

    with pytest.raises(VultronNotFoundError):
        EmbargoLifecycle(persistence=dl).record_embargo_invite(
            case_id=case.id_,
            invitee_id="https://example.org/users/nobody",
            embargo_id="https://example.org/embargoes/e1",
        )


# ---------------------------------------------------------------------------
# Invite expiry — one invitation's row times out (CM-28-001, CM-28-013)
# ---------------------------------------------------------------------------


def _invited_to_two(
    dl: SqliteDataLayer,
    owner: as_Service,
    *,
    active_deadline_in_days: int,
    revision_deadline_in_days: int,
):
    """A participant INVITED to A (active) and B (proposed), each with a deadline."""
    invitee = _make_actor(dl, "Invitee")
    case, participants = _make_case(dl, owner.id_, [invitee.id_])
    active = _make_embargo(dl, case.id_)
    revision = _make_embargo(dl, case.id_, days=90)
    activate(case, active.id_)
    propose(case, revision.id_)
    dl.save(case)
    write_consent_rows(dl, case)
    invitee_p = participants[1]
    for embargo_id, days in (
        (active.id_, active_deadline_in_days),
        (revision.id_, revision_deadline_in_days),
    ):
        _seed_consent(
            dl,
            invitee_p.id_,
            embargo_id,
            ECS.INVITED,
            rsvp_deadline=now_utc() + timedelta(days=days),
        )
    return case, invitee, invitee_p.id_, active.id_, revision.id_


@pytest.mark.spec("CM-28-001", "CM-28-013", "CM-18-002")
def test_record_invite_expiry_times_out_only_the_invitations_row(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A deadline belongs to one invitation: TIME_OUT moves only that row."""
    owner, dl = owner_and_dl
    case, invitee, pid, active_id, rev_id = _invited_to_two(
        dl, owner, active_deadline_in_days=-1, revision_deadline_in_days=-1
    )

    result = EmbargoLifecycle(persistence=dl).record_invite_expiry(
        case_id=case.id_, actor_id=invitee.id_, embargo_id=active_id
    )

    assert result.is_expired is True
    assert [
        (c.embargo_id, c.consent_before, c.consent_after)
        for c in result.participant_changes
    ] == [(active_id, "INVITED", "TIMED_OUT")]
    assert _consents_of(dl, pid) == {
        active_id: "TIMED_OUT",
        rev_id: "INVITED",
    }
    # Idempotent: the row is no longer INVITED.
    again = EmbargoLifecycle(persistence=dl).record_invite_expiry(
        case_id=case.id_, actor_id=invitee.id_, embargo_id=active_id
    )
    assert again.participant_changes == [] and again.is_expired is False


@pytest.mark.spec("CM-28-001", "CM-28-012", "CM-28-013")
def test_concurrent_invitations_time_out_at_their_own_deadlines(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Two invitations with different deadlines: only the earlier times out."""
    owner, dl = owner_and_dl
    case, invitee, pid, active_id, rev_id = _invited_to_two(
        dl, owner, active_deadline_in_days=1, revision_deadline_in_days=5
    )
    lifecycle = EmbargoLifecycle(persistence=dl)
    at_earlier = now_utc() + timedelta(days=2)

    assessed = {
        embargo_id: lifecycle.assess_invite_expiry(
            case_id=case.id_,
            actor_id=invitee.id_,
            embargo_id=embargo_id,
            now=at_earlier,
        )
        for embargo_id in (active_id, rev_id)
    }
    assert assessed == {active_id: (True, True), rev_id: (False, False)}

    for embargo_id, (_, needs_apply) in assessed.items():
        if needs_apply:
            lifecycle.record_invite_expiry(
                case_id=case.id_, actor_id=invitee.id_, embargo_id=embargo_id
            )

    assert _consents_of(dl, pid) == {active_id: "TIMED_OUT", rev_id: "INVITED"}
    record = cast(CaseParticipant, dl.read(pid))
    assert record.rsvp_deadline_for(active_id) is None
    assert record.rsvp_deadline_for(rev_id) is not None


@pytest.mark.spec("CM-28-013", "CM-18-002")
def test_detect_and_apply_expiry_times_out_the_row_after_its_deadline(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    owner, dl = owner_and_dl
    case, invitee, pid, active_id, rev_id = _invited_to_two(
        dl, owner, active_deadline_in_days=1, revision_deadline_in_days=1
    )
    lifecycle = EmbargoLifecycle(persistence=dl)

    before = lifecycle.detect_and_apply_expiry(
        case_id=case.id_,
        actor_id=invitee.id_,
        embargo_id=active_id,
        now=now_utc(),
    )
    assert before.is_expired is False and before.participant_changes == []
    assert _consents_of(dl, pid) == {active_id: "INVITED", rev_id: "INVITED"}

    after = lifecycle.detect_and_apply_expiry(
        case_id=case.id_,
        actor_id=invitee.id_,
        embargo_id=active_id,
        now=now_utc() + timedelta(days=2),
    )
    assert after.is_expired is True
    assert len(after.participant_changes) == 1
    assert _consents_of(dl, pid) == {active_id: "TIMED_OUT", rev_id: "INVITED"}


@pytest.mark.spec("CM-28-013", "CM-18-002")
def test_a_signatory_past_its_deadline_is_not_reported_expired(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """AGREED(active) wins over a passed deadline; the revision row times out."""
    owner, dl = owner_and_dl
    case, invitee, pid, active_id, rev_id = _invited_to_two(
        dl, owner, active_deadline_in_days=-1, revision_deadline_in_days=-1
    )
    _seed_consent(dl, pid, active_id, ECS.AGREED)
    lifecycle = EmbargoLifecycle(persistence=dl)

    assessed = lifecycle.assess_invite_expiry(
        case_id=case.id_,
        actor_id=invitee.id_,
        embargo_id=rev_id,
        now=now_utc(),
    )
    result = lifecycle.detect_and_apply_expiry(
        case_id=case.id_,
        actor_id=invitee.id_,
        embargo_id=rev_id,
        now=now_utc(),
    )

    assert assessed == (False, True)
    assert result.is_expired is False
    assert _consents_of(dl, pid) == {active_id: "AGREED", rev_id: "TIMED_OUT"}


@pytest.mark.spec("CM-28-013")
def test_an_invited_row_for_a_final_entry_never_times_out(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A row whose entry was rejected is frozen, past its deadline or not."""
    owner, dl = owner_and_dl
    case, invitee, pid, _active_id, rev_id = _invited_to_two(
        dl, owner, active_deadline_in_days=5, revision_deadline_in_days=-1
    )
    reject(case, rev_id)
    dl.save(case)
    lifecycle = EmbargoLifecycle(persistence=dl)

    assert lifecycle.assess_invite_expiry(
        case_id=case.id_,
        actor_id=invitee.id_,
        embargo_id=rev_id,
        now=now_utc(),
    ) == (True, False)
    result = lifecycle.record_invite_expiry(
        case_id=case.id_, actor_id=invitee.id_, embargo_id=rev_id
    )

    assert result.participant_changes == []
    assert _consents_of(dl, pid)[rev_id] == "INVITED"


# ---------------------------------------------------------------------------
# honour_late_accept — EMB-17-001, ADR-0118
# ---------------------------------------------------------------------------


@pytest.mark.spec("EMB-17-001")
@pytest.mark.parametrize(
    ("seed", "expected"),
    [
        (
            ECS.TIMED_OUT,
            [("TIMED_OUT", "AGREED")],
        ),
        (
            ECS.DECLINED,
            [("DECLINED", "INVITED"), ("INVITED", "AGREED")],
        ),
    ],
)
def test_honour_late_accept_agrees_to_the_active_embargo(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    seed: ECS,
    expected: list[tuple[str, str]],
) -> None:
    """A late Accept is honoured from TIMED_OUT, and from DECLINED via INVITED."""
    owner, dl = owner_and_dl
    late = _make_actor(dl, "Late")
    case, participants = _make_case(dl, owner.id_, [late.id_])
    active = _make_embargo(dl, case.id_)
    activate(case, active.id_)
    dl.save(case)
    pid = participants[1].id_
    _seed_consent(dl, pid, active.id_, seed)
    assert not _is_signatory(dl, case.id_, pid)

    result = EmbargoLifecycle(persistence=dl).honour_late_accept(
        case_id=case.id_, actor_id=late.id_, embargo_id=active.id_
    )

    assert [
        (c.consent_before, c.consent_after) for c in result.participant_changes
    ] == expected
    assert _consent_of(dl, pid, active.id_) == "AGREED"
    assert _is_signatory(dl, case.id_, pid)

    again = EmbargoLifecycle(persistence=dl).honour_late_accept(
        case_id=case.id_, actor_id=late.id_, embargo_id=active.id_
    )
    assert again.participant_changes == []


@pytest.mark.spec("EMB-17-003")
def test_an_invitation_to_a_final_entry_is_closed_before_its_deadline(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Rejected terms close their invitation: expired for routing, no time-out.

    The row is frozen, so there is nothing to apply; the caller's EMB-17
    routing answers the Accept with an invitation to the current embargo.
    """
    owner, dl = owner_and_dl
    case, invitee, pid, _active_id, rev_id = _invited_to_two(
        dl, owner, active_deadline_in_days=5, revision_deadline_in_days=5
    )
    reject(case, rev_id)
    dl.save(case)

    assert EmbargoLifecycle(persistence=dl).assess_invite_expiry(
        case_id=case.id_,
        actor_id=invitee.id_,
        embargo_id=rev_id,
        now=now_utc(),
    ) == (True, False)
    assert _consent_of(dl, pid, rev_id) == "INVITED"
