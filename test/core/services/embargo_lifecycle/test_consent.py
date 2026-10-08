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

from test.support.embargo_register import activate, propose
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
    """ACCEPT moves the INVITED row for that embargo to ACCEPTED."""
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
        pec_trigger=PEC_Trigger.ACCEPT,
    )

    assert result.case_changed is False
    assert result.case_embargo_changed is False
    assert [
        (c.embargo_id, c.consent_before, c.consent_after)
        for c in result.participant_changes
    ] == [(embargo.id_, "INVITED", "ACCEPTED")]
    assert _consent_of(dl, owner_participant_id, embargo.id_) == "ACCEPTED"


def test_record_participant_consent_decline_trigger(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """DECLINE moves an ACCEPTED row to DECLINED and touches no other row."""
    owner, dl = owner_and_dl
    case, participants = _make_case(dl, owner.id_)
    owner_participant_id = participants[0].id_
    embargo = _make_embargo(dl, case.id_)
    propose(case, embargo.id_)
    dl.save(case)
    other = _make_embargo(dl, case.id_, days=90)
    _seed_consent(dl, owner_participant_id, embargo.id_, ECS.ACCEPTED)
    _seed_consent(dl, owner_participant_id, other.id_, ECS.ACCEPTED)

    lifecycle = EmbargoLifecycle(persistence=dl)
    lifecycle.record_participant_consent(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
        pec_trigger=PEC_Trigger.DECLINE,
    )

    assert _consents_of(dl, owner_participant_id) == {
        embargo.id_: "DECLINED",
        other.id_: "ACCEPTED",
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
        pec_trigger=PEC_Trigger.ACCEPT,
    )

    assert result.participant_changes == []
    assert result.case_changed is False


def test_record_participant_consent_illegal_trigger_raises(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """AC-5: illegal trigger raises VultronInvalidStateTransitionError.

    EXPIRE from ACCEPTED is not a valid consent transition.
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
    _seed_consent(dl, owner_participant_id, embargo.id_, ECS.ACCEPTED)

    lifecycle = EmbargoLifecycle(persistence=dl)
    with pytest.raises(VultronInvalidStateTransitionError):
        lifecycle.record_participant_consent(
            case_id=case.id_,
            embargo_id=embargo.id_,
            actor_id=owner.id_,
            pec_trigger=PEC_Trigger.EXPIRE,  # illegal from ACCEPTED
        )
    assert _consent_of(dl, owner_participant_id, embargo.id_) == "ACCEPTED"


# ---------------------------------------------------------------------------
# Tests: record_embargo_rejection — the consent half of a Reject (MSM-07-004)
# ---------------------------------------------------------------------------


def _active_with_revision(dl: SqliteDataLayer, owner: as_Service):
    """Owner (ACCEPTED A) and a finder (ACCEPTED A and B); A active, B proposed."""
    finder = _make_actor(dl, "Finder Org")
    case, (owner_p, finder_p) = _make_case(
        dl, owner.id_, extra_participant_ids=[finder.id_]
    )
    active = _make_embargo(dl, case.id_)
    revision = _make_embargo(dl, case.id_, days=90)
    activate(case, active.id_)
    propose(case, revision.id_)
    dl.save(case)
    _seed_consent(dl, owner_p.id_, active.id_, ECS.ACCEPTED)
    _seed_consent(dl, finder_p.id_, active.id_, ECS.ACCEPTED)
    _seed_consent(dl, finder_p.id_, revision.id_, ECS.ACCEPTED)
    return case, finder, owner_p.id_, finder_p.id_, active.id_, revision.id_


@pytest.mark.spec("MSM-07-004")
@pytest.mark.spec("CM-18-003")
def test_record_embargo_rejection_of_the_active_embargo_is_withdrawal(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Withdrawal declines the active row and every accepted open proposal."""
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
        (active_id, "ACCEPTED", "DECLINED"),
        (rev, "ACCEPTED", "DECLINED"),
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
        active_id: "ACCEPTED",
        rev: "DECLINED",
    }
    assert _is_signatory(dl, case.id_, finder_p)
    # Recording consent decides nothing: B stays an open proposal.
    assert cast(VulnerabilityCase, dl.read(case.id_)).proposed_embargo_ids == [
        rev
    ]


@pytest.mark.spec("MSM-07-004")
def test_record_embargo_rejection_by_the_owner_of_a_revision_changes_nothing(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """EJ on the received side: the owner keeps A; no record moves."""
    owner, dl = owner_and_dl
    case, _finder, owner_p, _finder_p, active_id, rev = _active_with_revision(
        dl, owner
    )

    result = EmbargoLifecycle(persistence=dl).record_embargo_rejection(
        case_id=case.id_, actor_id=owner.id_, embargo_id=rev
    )

    assert result.participant_changes == []
    assert _consents_of(dl, owner_p) == {active_id: "ACCEPTED"}
    assert _is_signatory(dl, case.id_, owner_p)


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
        active_id: "ACCEPTED",
        rev: "ACCEPTED",
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
    ] == [(embargo.id_, None, "INVITED")]
    record = cast(CaseParticipant, dl.read(participants[1].id_))
    assert record.consent_for(embargo.id_) == ECS.INVITED
    assert record.invite_rsvp_deadline == deadline


@pytest.mark.spec("EP-09-004")
def test_record_embargo_invite_on_a_signatory_keeps_the_active_row_and_adds_the_revision(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A signatory asked about a revision stays bound and gains INVITED(B).

    The row belongs to the embargo the Invite names, so the ACCEPTED row for
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
    _seed_consent(dl, participants[1].id_, active.id_, ECS.ACCEPTED)

    result = EmbargoLifecycle(persistence=dl).record_embargo_invite(
        case_id=case.id_, invitee_id=invitee.id_, embargo_id=revision.id_
    )

    assert [
        (c.embargo_id, c.consent_after) for c in result.participant_changes
    ] == [(revision.id_, "INVITED")]
    assert _consents_of(dl, participants[1].id_) == {
        active.id_: "ACCEPTED",
        revision.id_: "INVITED",
    }
    assert _is_signatory(dl, case.id_, participants[1].id_)


@pytest.mark.spec("CM-28-013")
def test_a_fresh_invite_without_a_deadline_drops_a_stale_one(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A passed deadline must not expire the row a new Invite just created."""
    owner, dl = owner_and_dl
    invitee = _make_actor(dl, "Signatory")
    case, participants = _make_case(dl, owner.id_, [invitee.id_])
    active = _make_embargo(dl, case.id_)
    revision = _make_embargo(dl, case.id_, days=90)
    activate(case, active.id_)
    propose(case, revision.id_)
    dl.save(case)
    _seed_consent(dl, participants[1].id_, active.id_, ECS.ACCEPTED)
    record = cast(CaseParticipant, dl.read(participants[1].id_))
    record.invite_rsvp_deadline = now_utc() - timedelta(days=1)
    dl.save(record)

    EmbargoLifecycle(persistence=dl).record_embargo_invite(
        case_id=case.id_, invitee_id=invitee.id_, embargo_id=revision.id_
    )
    result = EmbargoLifecycle(persistence=dl).detect_and_apply_expiry(
        case_id=case.id_, actor_id=invitee.id_, now=now_utc()
    )

    assert result.participant_changes == []
    assert _consents_of(dl, participants[1].id_)[revision.id_] == "INVITED"


@pytest.mark.spec("EP-09-004")
def test_record_embargo_invite_leaves_an_accepted_row_for_that_embargo(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """INVITE is illegal from ACCEPTED on the same embargo: recorded no-op."""
    owner, dl = owner_and_dl
    invitee = _make_actor(dl, "Signatory")
    case, participants = _make_case(dl, owner.id_, [invitee.id_])
    embargo = _make_embargo(dl, case.id_)
    _seed_consent(dl, participants[1].id_, embargo.id_, ECS.ACCEPTED)

    result = EmbargoLifecycle(persistence=dl).record_embargo_invite(
        case_id=case.id_, invitee_id=invitee.id_, embargo_id=embargo.id_
    )

    assert result.participant_changes == []
    assert _consent_of(dl, participants[1].id_, embargo.id_) == "ACCEPTED"


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
# Invite expiry — every still-INVITED row expires (CM-28-013, CM-18-002)
# ---------------------------------------------------------------------------


def _invited_to_two(
    dl: SqliteDataLayer, owner: as_Service, *, deadline_in_days: int
):
    """A participant INVITED to A (active) and B (proposed), with a deadline."""
    invitee = _make_actor(dl, "Invitee")
    case, participants = _make_case(dl, owner.id_, [invitee.id_])
    active = _make_embargo(dl, case.id_)
    revision = _make_embargo(dl, case.id_, days=90)
    activate(case, active.id_)
    propose(case, revision.id_)
    dl.save(case)
    invitee_p = participants[1]
    _seed_consent(dl, invitee_p.id_, active.id_, ECS.INVITED)
    _seed_consent(dl, invitee_p.id_, revision.id_, ECS.INVITED)
    record = cast(CaseParticipant, dl.read(invitee_p.id_))
    record.invite_rsvp_deadline = now_utc() + timedelta(days=deadline_in_days)
    dl.save(record)
    return case, invitee, invitee_p.id_, active.id_, revision.id_


@pytest.mark.spec("CM-28-013", "CM-18-002")
def test_record_invite_expiry_expires_every_invited_row(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """One RSVP deadline per participant: EXPIRE applies to each INVITED row."""
    owner, dl = owner_and_dl
    case, invitee, pid, active_id, rev_id = _invited_to_two(
        dl, owner, deadline_in_days=-1
    )
    _seed_consent(dl, pid, "https://example.org/embargoes/old", ECS.DECLINED)

    result = EmbargoLifecycle(persistence=dl).record_invite_expiry(
        case_id=case.id_, actor_id=invitee.id_
    )

    assert result.is_expired is True
    assert {
        (c.embargo_id, c.consent_before, c.consent_after)
        for c in result.participant_changes
    } == {
        (active_id, "INVITED", "EXPIRED"),
        (rev_id, "INVITED", "EXPIRED"),
    }
    assert _consents_of(dl, pid) == {
        active_id: "EXPIRED",
        rev_id: "EXPIRED",
        "https://example.org/embargoes/old": "DECLINED",
    }
    # Idempotent: nothing is INVITED any more.
    again = EmbargoLifecycle(persistence=dl).record_invite_expiry(
        case_id=case.id_, actor_id=invitee.id_
    )
    assert again.participant_changes == [] and again.is_expired is False


@pytest.mark.spec("CM-28-013", "CM-18-002")
def test_detect_and_apply_expiry_expires_every_invited_row_after_the_deadline(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    owner, dl = owner_and_dl
    case, invitee, pid, active_id, rev_id = _invited_to_two(
        dl, owner, deadline_in_days=1
    )
    lifecycle = EmbargoLifecycle(persistence=dl)

    before = lifecycle.detect_and_apply_expiry(
        case_id=case.id_, actor_id=invitee.id_, now=now_utc()
    )
    assert before.is_expired is False and before.participant_changes == []
    assert _consents_of(dl, pid) == {active_id: "INVITED", rev_id: "INVITED"}

    after = lifecycle.detect_and_apply_expiry(
        case_id=case.id_,
        actor_id=invitee.id_,
        now=now_utc() + timedelta(days=2),
    )
    assert after.is_expired is True
    assert len(after.participant_changes) == 2
    assert _consents_of(dl, pid) == {active_id: "EXPIRED", rev_id: "EXPIRED"}


@pytest.mark.spec("CM-28-013", "CM-18-002")
def test_a_signatory_past_its_deadline_is_not_reported_expired(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """ACCEPTED(active) wins over a stale deadline; the revision row expires."""
    owner, dl = owner_and_dl
    case, invitee, pid, active_id, rev_id = _invited_to_two(
        dl, owner, deadline_in_days=-1
    )
    _seed_consent(dl, pid, active_id, ECS.ACCEPTED)
    lifecycle = EmbargoLifecycle(persistence=dl)

    assessed = lifecycle.assess_invite_expiry(
        case_id=case.id_, actor_id=invitee.id_, now=now_utc()
    )
    result = lifecycle.detect_and_apply_expiry(
        case_id=case.id_, actor_id=invitee.id_, now=now_utc()
    )

    assert assessed == (False, True)
    assert result.is_expired is False
    assert _consents_of(dl, pid) == {active_id: "ACCEPTED", rev_id: "EXPIRED"}


# ---------------------------------------------------------------------------
# honour_late_accept — EMB-17-001, ADR-0118
# ---------------------------------------------------------------------------


@pytest.mark.spec("EMB-17-001")
@pytest.mark.parametrize(
    ("seed", "expected"),
    [
        (
            ECS.EXPIRED,
            [("EXPIRED", "ACCEPTED")],
        ),
        (
            ECS.DECLINED,
            [("DECLINED", "INVITED"), ("INVITED", "ACCEPTED")],
        ),
    ],
)
def test_honour_late_accept_accepts_the_active_embargo(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    seed: ECS,
    expected: list[tuple[str, str]],
) -> None:
    """A late Accept is honoured from EXPIRED, and from DECLINED via INVITED."""
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
    assert _consent_of(dl, pid, active.id_) == "ACCEPTED"
    assert _is_signatory(dl, case.id_, pid)

    again = EmbargoLifecycle(persistence=dl).honour_late_accept(
        case_id=case.id_, actor_id=late.id_, embargo_id=active.id_
    )
    assert again.participant_changes == []
