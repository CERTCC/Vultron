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

"""The PEC side-effect helpers shared by the EM operations (``pec.py``).

The operations' own tests cover these through ``accept_embargo_invite`` and
``activate_embargo`` (the revision-activation cascade, EP-05-001),
``terminate_active_embargo`` (RESET cascade) and accept/reject
(single-actor consent).  These pin the contract of the shared helpers
directly, so a change to the cascade filter or the actor lookup fails here
by name rather than somewhere in a transition test.
"""

import logging

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.core.states.participant_embargo_consent import PEC
from vultron.errors import VultronNotFoundError, VultronValidationError
from vultron.wire.as2.vocab.base.objects.actors import as_Service

from .conftest import (
    _accepted_ids_of,
    _force_pec,
    _make_actor,
    _make_case,
    _make_embargo,
    _pec_of,
    _seed_consent,
)


@pytest.mark.spec("EP-05-001")
@pytest.mark.spec("CM-18-002")
def test_cascade_pec_revise_lapses_only_signatories_lacking_the_revision(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """The REVISE cascade is keyed on the revised embargo, not on state alone.

    Run at *activation* of longer terms (EP-05-001): a SIGNATORY whose
    ``accepted_embargo_ids`` lacks the revised id lapses; a SIGNATORY that
    already accepted it stays; every other state is untouched.
    """
    owner, dl = owner_and_dl
    signer = _make_actor(dl, "Signer")
    accepted = _make_actor(dl, "Accepted")
    invitee = _make_actor(dl, "Invitee")
    case, participants = _make_case(
        dl,
        owner.id_,
        extra_participant_ids=[signer.id_, accepted.id_, invitee.id_],
    )
    owner_p, signer_p, accepted_p, invitee_p = participants
    active = _make_embargo(dl, case.id_)
    revision = _make_embargo(dl, case.id_, days=90)
    _seed_consent(dl, signer_p.id_, PEC.SIGNATORY, [active.id_])
    _seed_consent(
        dl, accepted_p.id_, PEC.SIGNATORY, [active.id_, revision.id_]
    )
    _force_pec(dl, invitee_p.id_, PEC.INVITED)

    lifecycle = EmbargoLifecycle(persistence=dl)
    changes = lifecycle._cascade_pec_revise(
        case, revised_embargo_id=revision.id_
    )

    assert [c.participant_id for c in changes] == [signer_p.id_]
    assert changes[0].pec_before == PEC.SIGNATORY.value
    assert _pec_of(dl, signer_p.id_) == PEC.LAPSED.value
    assert _pec_of(dl, accepted_p.id_) == PEC.SIGNATORY.value
    assert _pec_of(dl, invitee_p.id_) == PEC.INVITED.value
    assert _pec_of(dl, owner_p.id_) == PEC.UNBOUND.value


@pytest.mark.spec("CM-18-003", "MSM-07-006")
def test_cascade_pec_exit_skips_unbound_exited_and_exits_the_rest(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """EXIT cascade moves every non-terminal record to UNBOUND_EXITED.

    An UNBOUND record exits too (ADR-0118): termination ends the embargo
    for everyone, so no record is left able to sign it. A record already
    at the terminal UNBOUND_EXITED is skipped and reported as no change.
    """
    owner, dl = owner_and_dl
    signer = _make_actor(dl, "Signer")
    invitee = _make_actor(dl, "Invitee")
    gone = _make_actor(dl, "Gone")
    case, participants = _make_case(
        dl,
        owner.id_,
        extra_participant_ids=[signer.id_, invitee.id_, gone.id_],
    )
    owner_p, signer_p, invitee_p, gone_p = participants
    _force_pec(dl, signer_p.id_, PEC.SIGNATORY)
    _force_pec(dl, invitee_p.id_, PEC.INVITED)
    _force_pec(dl, gone_p.id_, PEC.UNBOUND_EXITED)

    lifecycle = EmbargoLifecycle(persistence=dl)
    changes = lifecycle._cascade_pec_exit(case)

    assert {c.participant_id for c in changes} == {
        owner_p.id_,
        signer_p.id_,
        invitee_p.id_,
    }
    for p in participants:
        assert _pec_of(dl, p.id_) == PEC.UNBOUND_EXITED.value


def test_participant_for_actor_unknown_actor_warns_and_returns_none(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An actor with no participant record yields None and a WARNING naming the purpose."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)
    lifecycle = EmbargoLifecycle(persistence=dl)

    with caplog.at_level(
        logging.WARNING, logger="vultron.core.services.embargo_lifecycle"
    ):
        resolved = lifecycle._participant_for_actor(
            case, "https://example.org/actors/stranger", "acceptance"
        )

    assert resolved is None
    assert any(
        "cannot record embargo acceptance" in r.getMessage()
        for r in caplog.records
    )


def test_record_actor_pec_acceptance_is_idempotent_for_signatory(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A SIGNATORY re-accepting the same embargo changes nothing and reports nothing."""
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    lifecycle = EmbargoLifecycle(persistence=dl)
    embargo_id = "https://example.org/embargoes/e1"

    first = lifecycle._record_actor_pec_acceptance(case, owner.id_, embargo_id)
    second = lifecycle._record_actor_pec_acceptance(
        case, owner.id_, embargo_id
    )

    assert [c.pec_after for c in first] == [PEC.SIGNATORY.value]
    assert second == []
    assert _accepted_ids_of(dl, owner_p.id_) == [embargo_id]


@pytest.mark.spec("MSM-07-003")
def test_record_actor_pec_acceptance_without_advance_records_the_id_only(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """``advance=False`` writes the list and leaves the state — and reports nothing.

    A list-only write is not a consent *state* change, so it is persisted
    but does not appear in ``participant_changes``.
    """
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    _force_pec(dl, owner_p.id_, PEC.INVITED)
    lifecycle = EmbargoLifecycle(persistence=dl)
    embargo_id = "https://example.org/embargoes/proposed"

    changes = lifecycle._record_actor_pec_acceptance(
        case, owner.id_, embargo_id, advance=False
    )

    assert changes == []
    assert _pec_of(dl, owner_p.id_) == PEC.INVITED.value
    assert _accepted_ids_of(dl, owner_p.id_) == [embargo_id]


@pytest.mark.spec("MSM-07-004")
@pytest.mark.spec("CM-18-003")
def test_record_actor_pec_rejection_withdrawal_declines_a_signatory(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Rejecting the active embargo is withdrawal: SIGNATORY → DECLINED, id dropped."""
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    embargo_id = "https://example.org/embargoes/active"
    _seed_consent(dl, owner_p.id_, PEC.SIGNATORY, [embargo_id])
    lifecycle = EmbargoLifecycle(persistence=dl)

    changes = lifecycle._record_actor_pec_rejection(
        case, owner.id_, embargo_id, withdrawal=True
    )

    assert [(c.pec_before, c.pec_after) for c in changes] == [
        (PEC.SIGNATORY.value, PEC.DECLINED.value)
    ]
    assert _accepted_ids_of(dl, owner_p.id_) == []


@pytest.mark.spec("MSM-07-004")
def test_record_actor_pec_rejection_of_proposed_terms_keeps_a_signatory(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Refusing proposed terms drops the id but leaves a SIGNATORY bound."""
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    active_id = "https://example.org/embargoes/active"
    proposed_id = "https://example.org/embargoes/proposed"
    _seed_consent(dl, owner_p.id_, PEC.SIGNATORY, [active_id, proposed_id])
    lifecycle = EmbargoLifecycle(persistence=dl)

    changes = lifecycle._record_actor_pec_rejection(
        case, owner.id_, proposed_id, withdrawal=False
    )

    assert changes == []
    assert _pec_of(dl, owner_p.id_) == PEC.SIGNATORY.value
    assert _accepted_ids_of(dl, owner_p.id_) == [active_id]


@pytest.mark.spec("MSM-07-004")
def test_record_actor_pec_rejection_of_proposed_terms_declines_a_non_signatory(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A participant not yet bound has no consent for the refusal to leave intact."""
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    _force_pec(dl, owner_p.id_, PEC.INVITED)
    lifecycle = EmbargoLifecycle(persistence=dl)

    changes = lifecycle._record_actor_pec_rejection(
        case, owner.id_, "https://example.org/embargoes/p", withdrawal=False
    )

    assert [c.pec_after for c in changes] == [PEC.DECLINED.value]


@pytest.mark.spec("MSM-07-004", "CM-18-003")
@pytest.mark.parametrize("withdrawal", [True, False])
def test_record_actor_pec_rejection_keeps_unbound_exited(
    owner_and_dl: tuple[as_Service, SqliteDataLayer], withdrawal: bool
) -> None:
    """A Reject after termination changes no state: UNBOUND_EXITED is terminal.

    The stale id is still dropped from the list, so the record carries no
    acceptance of terms it can no longer be bound by (ADR-0118).
    """
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    embargo_id = "https://example.org/embargoes/gone"
    _seed_consent(dl, owner_p.id_, PEC.UNBOUND_EXITED, [embargo_id])
    lifecycle = EmbargoLifecycle(persistence=dl)

    changes = lifecycle._record_actor_pec_rejection(
        case, owner.id_, embargo_id, withdrawal=withdrawal
    )

    assert changes == []
    assert _pec_of(dl, owner_p.id_) == PEC.UNBOUND_EXITED.value
    assert _accepted_ids_of(dl, owner_p.id_) == []


@pytest.mark.spec("MSM-07-004", "CM-18-003")
def test_record_actor_pec_rejection_declines_an_expired_participant(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A late explicit Reject from EXPIRED is an answer: EXPIRED → DECLINED."""
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    _force_pec(dl, owner_p.id_, PEC.EXPIRED)
    lifecycle = EmbargoLifecycle(persistence=dl)

    changes = lifecycle._record_actor_pec_rejection(
        case, owner.id_, "https://example.org/embargoes/p", withdrawal=False
    )

    assert [(c.pec_before, c.pec_after) for c in changes] == [
        (PEC.EXPIRED.value, PEC.DECLINED.value)
    ]


def test_assert_rejectable_classifies_active_proposed_and_unknown(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A Reject names the active embargo, an open proposal, or nothing the case knows."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)
    active = _make_embargo(dl, case.id_)
    proposed = _make_embargo(dl, case.id_, days=60)
    stranger = _make_embargo(dl, case.id_, days=10)
    case.active_embargo = active.id_
    case.proposed_embargoes = [proposed.id_]
    dl.save(case)

    assert EmbargoLifecycle._assert_rejectable(case, active.id_) is True
    assert EmbargoLifecycle._assert_rejectable(case, proposed.id_) is False
    with pytest.raises(VultronValidationError, match="neither the active"):
        EmbargoLifecycle._assert_rejectable(case, stranger.id_)


@pytest.mark.spec("EP-05-001")
def test_revision_ends_no_later_orders_by_end_time_and_keeps_b_on_a_tie(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Shorter B → carry over; longer B → lapse arm; equal terms carry over."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)
    active = _make_embargo(dl, case.id_, days=45)
    shorter = _make_embargo(dl, case.id_, days=30)
    longer = _make_embargo(dl, case.id_, days=90)
    # Same instant, not the same ``days``: a second ``days_from_now_utc(45)``
    # ends a second later whenever a second boundary falls between the two
    # mints, which made this tie fail on a slow runner (#4010).
    equal = _make_embargo(dl, case.id_, end_time=active.end_time)
    lifecycle = EmbargoLifecycle(persistence=dl)

    def ends_no_later(revised: str) -> bool:
        return lifecycle._revision_ends_no_later(
            previous_embargo_id=active.id_, revised_embargo_id=revised
        )

    assert ends_no_later(shorter.id_) is True
    assert ends_no_later(longer.id_) is False
    assert ends_no_later(equal.id_) is True


def test_revision_comparison_fails_closed_on_an_unreadable_embargo(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A replica that lacks the replaced embargo cannot decide the arm — it raises.

    Neither arm is silently chosen: ``accept_embargo_invite`` and
    ``activate_embargo`` take this answer *before* mutating the case, so the
    failure leaves EM and ``active_embargo`` untouched.
    """
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)
    revision = _make_embargo(dl, case.id_, days=90)

    with pytest.raises(VultronNotFoundError):
        EmbargoLifecycle(persistence=dl)._revision_ends_no_later(
            previous_embargo_id="https://example.org/embargoes/gone",
            revised_embargo_id=revision.id_,
        )


@pytest.mark.spec("CM-18-003")
def test_record_actor_pec_acceptance_for_a_declined_actor_records_nothing(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """DECLINED holds no consent: neither the state nor the list moves (#4003)."""
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    _force_pec(dl, owner_p.id_, PEC.DECLINED)
    lifecycle = EmbargoLifecycle(persistence=dl)
    embargo_id = "https://example.org/embargoes/e1"

    advancing = lifecycle._record_actor_pec_acceptance(
        case, owner.id_, embargo_id
    )
    list_only = lifecycle._record_actor_pec_acceptance(
        case, owner.id_, embargo_id, advance=False
    )

    assert advancing == [] and list_only == []
    assert _pec_of(dl, owner_p.id_) == PEC.DECLINED.value
    assert _accepted_ids_of(dl, owner_p.id_) == []


@pytest.mark.spec("MSM-07-004")
def test_record_actor_pec_rejection_withdrawal_drops_every_open_proposal(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Withdrawal from A drops A and every open revision of it; a refusal of B drops B only."""
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    active = _make_embargo(dl, case.id_)
    revision = _make_embargo(dl, case.id_, days=90)
    case.active_embargo = active.id_
    case.proposed_embargoes = [revision.id_]
    dl.save(case)
    lifecycle = EmbargoLifecycle(persistence=dl)

    _seed_consent(dl, owner_p.id_, PEC.SIGNATORY, [active.id_, revision.id_])
    refused = lifecycle._record_actor_pec_rejection(
        case, owner.id_, revision.id_, withdrawal=False
    )
    assert refused == []
    assert _accepted_ids_of(dl, owner_p.id_) == [active.id_]

    _seed_consent(dl, owner_p.id_, PEC.SIGNATORY, [active.id_, revision.id_])
    withdrawn = lifecycle._record_actor_pec_rejection(
        case, owner.id_, active.id_, withdrawal=True
    )
    assert [c.pec_after for c in withdrawn] == [PEC.DECLINED.value]
    assert _accepted_ids_of(dl, owner_p.id_) == []


# ---------------------------------------------------------------------------
# Inert participants: consent moves only by their own replies (#4046 AC-5)
# ---------------------------------------------------------------------------


def _make_inert(dl: SqliteDataLayer, participant_id: str, how: str) -> None:
    """Make a participant inert by *how* — test setup only.

    ``"unjoined"``: it has not accepted its stub Invite.  ``"closed"``: it has
    recorded RM ``CLOSED`` (CM-23-004).
    """
    from typing import cast

    from vultron.core.models.case_participant import CaseParticipant
    from vultron.core.models.dimensions import RmDimension
    from vultron.core.models.participant_status import ParticipantStatus
    from vultron.core.states.rm import RM

    participant = cast(CaseParticipant, dl.read(participant_id))
    update: dict[str, object] = (
        {"joined": False}
        if how == "unjoined"
        else {
            "participant_statuses": [
                ParticipantStatus(
                    context=cast(str, participant.context),
                    attributed_to=participant.attributed_to,
                    rm=RmDimension(state=RM.CLOSED),
                )
            ]
        }
    )
    dl.save(participant.model_copy(update=update))


@pytest.mark.spec("CM-10-007")
@pytest.mark.parametrize("how", ["unjoined", "closed"])
def test_advance_holders_of_promotes_only_on_the_participants_own_reply(
    owner_and_dl: tuple[as_Service, SqliteDataLayer], how: str
) -> None:
    """Activation promotes an inert participant only if it accepted itself.

    Both participants are inert and INVITED.  The one whose own
    ``accepted_embargo_ids`` holds the activated id (it accepted early)
    advances; the one that never replied stays INVITED.
    """
    owner, dl = owner_and_dl
    replied = _make_actor(dl, "Replied")
    silent = _make_actor(dl, "Silent")
    case, participants = _make_case(
        dl, owner.id_, extra_participant_ids=[replied.id_, silent.id_]
    )
    _, replied_p, silent_p = participants
    embargo = _make_embargo(dl, case.id_)
    _seed_consent(dl, replied_p.id_, PEC.INVITED, [embargo.id_])
    _force_pec(dl, silent_p.id_, PEC.INVITED)
    _make_inert(dl, replied_p.id_, how)
    _make_inert(dl, silent_p.id_, how)

    changes = EmbargoLifecycle(persistence=dl)._advance_holders_of(
        case, embargo.id_
    )

    assert [c.participant_id for c in changes] == [replied_p.id_]
    assert _pec_of(dl, replied_p.id_) == PEC.SIGNATORY.value
    assert _pec_of(dl, silent_p.id_) == PEC.INVITED.value


@pytest.mark.spec("EP-05-001")
@pytest.mark.parametrize("how", ["unjoined", "closed"])
def test_longer_revision_lapses_an_inert_signatory_too(
    owner_and_dl: tuple[as_Service, SqliteDataLayer], how: str
) -> None:
    """A signatory that never accepted longer terms lapses, inert or not.

    Skipping it would leave it SIGNATORY to terms it never agreed to — and a
    closed participant still receives case content, so that would leak the
    longer-embargo period's content to it (CM-10-004).
    """
    owner, dl = owner_and_dl
    inert = _make_actor(dl, "Inert")
    case, participants = _make_case(
        dl, owner.id_, extra_participant_ids=[inert.id_]
    )
    inert_p = participants[1]
    active = _make_embargo(dl, case.id_)
    longer = _make_embargo(dl, case.id_, days=90)
    _seed_consent(dl, inert_p.id_, PEC.SIGNATORY, [active.id_])
    _make_inert(dl, inert_p.id_, how)

    changes = EmbargoLifecycle(persistence=dl)._cascade_pec_revise(
        case, revised_embargo_id=longer.id_
    )

    assert [c.participant_id for c in changes] == [inert_p.id_]
    assert _pec_of(dl, inert_p.id_) == PEC.LAPSED.value


@pytest.mark.spec("CM-10-007")
def test_cascade_pec_exit_reaches_an_inert_participant(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Termination exits every record, an inert one included (#4046 AC-5)."""
    owner, dl = owner_and_dl
    inert = _make_actor(dl, "Inert")
    case, participants = _make_case(
        dl, owner.id_, extra_participant_ids=[inert.id_]
    )
    inert_p = participants[1]
    _force_pec(dl, inert_p.id_, PEC.INVITED)
    _make_inert(dl, inert_p.id_, "unjoined")

    changes = EmbargoLifecycle(persistence=dl)._cascade_pec_exit(case)

    assert inert_p.id_ in {c.participant_id for c in changes}
    assert _pec_of(dl, inert_p.id_) == PEC.UNBOUND_EXITED.value
