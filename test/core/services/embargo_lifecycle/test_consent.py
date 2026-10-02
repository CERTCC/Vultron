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

from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC, PEC_Trigger
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronNotFoundError,
    VultronValidationError,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service

from .conftest import (
    _accepted_ids_of,
    _make_actor,
    _make_case,
    _make_embargo,
    _pec_of,
    _seed_consent,
)


def test_record_participant_consent_accept_trigger(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """ACCEPT trigger moves INVITED participant to SIGNATORY."""
    owner, dl = owner_and_dl
    case, participants = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
    owner_participant_id = participants[0].id_
    embargo = _make_embargo(dl, case.id_)

    # Set owner participant to INVITED so ACCEPT is valid
    owner_p = cast(CaseParticipant, dl.read(owner_participant_id))
    object.__setattr__(owner_p, "embargo_consent_state", PEC.INVITED)
    dl.save(owner_p)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.record_participant_consent(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
        pec_trigger=PEC_Trigger.ACCEPT,
    )

    assert result.case_changed is False
    assert result.case_embargo_changed is False

    refreshed = cast(CaseParticipant, dl.read(owner_participant_id))
    assert refreshed.embargo_consent_state == PEC.SIGNATORY.value
    assert embargo.id_ in refreshed.accepted_embargo_ids


def test_record_participant_consent_decline_trigger(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """DECLINE trigger moves LAPSED participant to DECLINED and removes embargo ID."""
    owner, dl = owner_and_dl
    case, participants = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
    owner_participant_id = participants[0].id_
    embargo = _make_embargo(dl, case.id_)

    # Seed as LAPSED (SIGNATORY → LAPSED after revise) with accepted embargo
    owner_p = cast(CaseParticipant, dl.read(owner_participant_id))
    object.__setattr__(owner_p, "embargo_consent_state", PEC.LAPSED)
    owner_p.accepted_embargo_ids = [embargo.id_]
    dl.save(owner_p)

    lifecycle = EmbargoLifecycle(persistence=dl)
    lifecycle.record_participant_consent(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
        pec_trigger=PEC_Trigger.DECLINE,
    )

    refreshed = cast(CaseParticipant, dl.read(owner_participant_id))
    assert refreshed.embargo_consent_state == PEC.DECLINED.value
    assert embargo.id_ not in refreshed.accepted_embargo_ids


def test_record_participant_consent_actor_not_in_case(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Actor without a CaseParticipant: result has no pec changes, no crash."""
    owner, dl = owner_and_dl
    outsider = _make_actor(dl, "Outsider Org")
    case, _ = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
    embargo = _make_embargo(dl, case.id_)

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

    ACCEPT from SIGNATORY is not a valid PEC transition.
    apply_pec_transition() is fail-closed and raises; this test pins that
    behavior and confirms record_participant_consent propagates it.
    """
    owner, dl = owner_and_dl
    case, participants = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
    owner_participant_id = participants[0].id_
    embargo = _make_embargo(dl, case.id_)

    owner_p = cast(CaseParticipant, dl.read(owner_participant_id))
    object.__setattr__(owner_p, "embargo_consent_state", PEC.SIGNATORY)
    dl.save(owner_p)

    lifecycle = EmbargoLifecycle(persistence=dl)
    with pytest.raises(VultronInvalidStateTransitionError):
        lifecycle.record_participant_consent(
            case_id=case.id_,
            embargo_id=embargo.id_,
            actor_id=owner.id_,
            pec_trigger=PEC_Trigger.ACCEPT,  # illegal from SIGNATORY
        )


# ---------------------------------------------------------------------------
# Tests: record_embargo_rejection — the consent half of a Reject (MSM-07-004)
# ---------------------------------------------------------------------------


def _active_with_revision(dl: SqliteDataLayer, owner: as_Service):
    """Owner (SIGNATORY, [A]) and a finder (SIGNATORY, [A, B]); A active, B proposed."""
    finder = _make_actor(dl, "Finder Org")
    case, (owner_p, finder_p) = _make_case(
        dl, owner.id_, extra_participant_ids=[finder.id_], em_state=EM.REVISE
    )
    active = _make_embargo(dl, case.id_)
    revision = _make_embargo(dl, case.id_, days=90)
    case.active_embargo = active.id_
    case.proposed_embargoes = [revision.id_]
    dl.save(case)
    _seed_consent(dl, owner_p.id_, PEC.SIGNATORY, [active.id_])
    _seed_consent(dl, finder_p.id_, PEC.SIGNATORY, [active.id_, revision.id_])
    return case, finder, owner_p.id_, finder_p.id_, active.id_, revision.id_


@pytest.mark.spec("MSM-07-004")
@pytest.mark.spec("CM-18-003")
def test_record_embargo_rejection_of_the_active_embargo_is_withdrawal(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    owner, dl = owner_and_dl
    case, finder, _owner_p, finder_p, active_id, _rev = _active_with_revision(
        dl, owner
    )

    result = EmbargoLifecycle(persistence=dl).record_embargo_rejection(
        case_id=case.id_, actor_id=finder.id_, embargo_id=active_id
    )

    assert result.em_before == result.em_after == EM.REVISE
    assert result.case_changed is False
    assert [
        (c.pec_before, c.pec_after) for c in result.participant_changes
    ] == [(PEC.SIGNATORY.value, PEC.DECLINED.value)]
    assert active_id not in _accepted_ids_of(dl, finder_p)


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

    assert result.participant_changes == []
    assert _pec_of(dl, finder_p) == PEC.SIGNATORY.value
    assert _accepted_ids_of(dl, finder_p) == [active_id]
    # Recording consent decides nothing: B stays an open proposal.
    assert cast(VulnerabilityCase, dl.read(case.id_)).proposed_embargoes == [
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
    assert _pec_of(dl, owner_p) == PEC.SIGNATORY.value
    assert _accepted_ids_of(dl, owner_p) == [active_id]


def test_record_embargo_rejection_of_an_unknown_embargo_raises(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    owner, dl = owner_and_dl
    case, finder, _o, finder_p, _a, _r = _active_with_revision(dl, owner)
    stranger = _make_embargo(dl, case.id_, days=10)

    with pytest.raises(VultronValidationError, match="neither the active"):
        EmbargoLifecycle(persistence=dl).record_embargo_rejection(
            case_id=case.id_, actor_id=finder.id_, embargo_id=stranger.id_
        )
    assert _pec_of(dl, finder_p) == PEC.SIGNATORY.value


# ---------------------------------------------------------------------------
# record_embargo_invite — the relay's and the replay's one rule (EP-09-004)
# ---------------------------------------------------------------------------


@pytest.mark.spec("EP-09-004")
@pytest.mark.spec("CM-28-013")
def test_record_embargo_invite_invites_an_unbound_participant(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    owner, dl = owner_and_dl
    invitee = _make_actor(dl, "Invitee")
    case, participants = _make_case(
        dl, owner.id_, [invitee.id_], em_state=EM.REVISE
    )
    deadline = days_from_now_utc(7)

    result = EmbargoLifecycle(persistence=dl).record_embargo_invite(
        case_id=case.id_, invitee_id=invitee.id_, rsvp_deadline=deadline
    )

    assert result.em_before == result.em_after == EM.REVISE
    assert [c.pec_after for c in result.participant_changes] == [
        PEC.INVITED.value
    ]
    record = cast(CaseParticipant, dl.read(participants[1].id_))
    assert record.embargo_consent_state == PEC.INVITED
    assert record.invite_rsvp_deadline == deadline


@pytest.mark.spec("EP-09-004")
def test_record_embargo_invite_leaves_a_signatory_signed(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """INVITE is illegal from SIGNATORY: a recorded no-op, never a fault."""
    owner, dl = owner_and_dl
    invitee = _make_actor(dl, "Signatory")
    case, participants = _make_case(dl, owner.id_, [invitee.id_])
    _seed_consent(dl, participants[1].id_, PEC.SIGNATORY, [])

    result = EmbargoLifecycle(persistence=dl).record_embargo_invite(
        case_id=case.id_, invitee_id=invitee.id_
    )

    assert result.participant_changes == []
    assert _pec_of(dl, participants[1].id_) == PEC.SIGNATORY


def test_record_embargo_invite_raises_for_an_unknown_invitee(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)

    with pytest.raises(VultronNotFoundError):
        EmbargoLifecycle(persistence=dl).record_embargo_invite(
            case_id=case.id_, invitee_id="https://example.org/users/nobody"
        )
