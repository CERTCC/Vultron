"""The consent side-effect helpers shared by the EM operations (``pec.py``).

Consent is per (participant, embargo) (ADR-0122): "signatory" and "lapsed"
are derived from the rows and the case's active embargo, never written.  The
operations' own tests cover these helpers through ``accept_embargo_invite``
and ``activate_embargo`` (the containment carry-over, EP-05-001) and
accept/reject (single-actor consent).  These pin the contract of the shared
helpers directly, so a change to the carry-over filter, the Accept/Reject row
rules or the actor lookup fails here by name rather than somewhere in a
transition test.
"""

import logging
from typing import cast

import pytest

from test.support.embargo_register import (
    activate,
    propose,
    reject,
    terminate,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState as ECS,
)
from vultron.errors import VultronNotFoundError, VultronValidationError
from vultron.wire.as2.vocab.base.objects.actors import as_Service

from .conftest import (
    _consent_of,
    _consents_of,
    _has_lapsed,
    _is_signatory,
    _make_actor,
    _make_case,
    _make_embargo,
    _seed_consent,
)


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


def test_record_actor_acceptance_is_idempotent(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Re-accepting the same embargo changes nothing and reports nothing."""
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    lifecycle = EmbargoLifecycle(persistence=dl)
    embargo_id = "https://example.org/embargoes/e1"
    propose(case, embargo_id)

    first = lifecycle._record_actor_acceptance(case, owner.id_, embargo_id)
    second = lifecycle._record_actor_acceptance(case, owner.id_, embargo_id)

    assert [(c.consent_before, c.consent_after) for c in first] == [
        (None, ECS.ACCEPTED.value)
    ]
    assert second == []
    assert _consents_of(dl, owner_p.id_) == {embargo_id: "ACCEPTED"}


@pytest.mark.spec("MSM-07-003")
def test_record_actor_acceptance_of_a_proposal_leaves_the_active_row_alone(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Accept always marks that embargo's row — no advance at accept time.

    Accepting a proposed revision writes the revision's row, reports it, and
    leaves the row for the embargo in force exactly as it was.
    """
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    active_id = "https://example.org/embargoes/active"
    proposed_id = "https://example.org/embargoes/proposed"
    activate(case, active_id)
    propose(case, proposed_id)
    _seed_consent(dl, owner_p.id_, active_id, ECS.ACCEPTED)
    lifecycle = EmbargoLifecycle(persistence=dl)

    changes = lifecycle._record_actor_acceptance(case, owner.id_, proposed_id)

    assert [(c.embargo_id, c.consent_after) for c in changes] == [
        (proposed_id, "ACCEPTED")
    ]
    assert _consents_of(dl, owner_p.id_) == {
        active_id: "ACCEPTED",
        proposed_id: "ACCEPTED",
    }


@pytest.mark.spec("MSM-07-003")
def test_record_actor_acceptance_of_an_embargo_not_in_the_register_records_nothing(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A row needs a register entry: an unknown embargo's Accept binds nothing."""
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    lifecycle = EmbargoLifecycle(persistence=dl)

    changes = lifecycle._record_actor_acceptance(
        case, owner.id_, "https://example.org/embargoes/unknown"
    )

    assert changes == []
    assert _consents_of(dl, owner_p.id_) == {}


@pytest.mark.spec("MSM-07-003")
def test_record_actor_acceptance_of_a_rejected_proposal_records_nothing(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Rows for an entry in a final register status accept no trigger (ADR-0122)."""
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    rejected_id = "https://example.org/embargoes/rejected"
    propose(case, rejected_id)
    reject(case, rejected_id)
    _seed_consent(dl, owner_p.id_, rejected_id, ECS.INVITED)
    lifecycle = EmbargoLifecycle(persistence=dl)

    changes = lifecycle._record_actor_acceptance(case, owner.id_, rejected_id)

    assert changes == []
    assert _consents_of(dl, owner_p.id_) == {rejected_id: "INVITED"}


@pytest.mark.spec("MSM-07-004")
@pytest.mark.spec("CM-18-003")
def test_record_actor_rejection_withdrawal_declines_the_active_row(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Rejecting the active embargo is withdrawal: ACCEPTED -> DECLINED."""
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    embargo_id = "https://example.org/embargoes/active"
    _seed_consent(dl, owner_p.id_, embargo_id, ECS.ACCEPTED)
    lifecycle = EmbargoLifecycle(persistence=dl)

    changes = lifecycle._record_actor_rejection(
        case, owner.id_, embargo_id, withdrawal=True
    )

    assert [(c.consent_before, c.consent_after) for c in changes] == [
        ("ACCEPTED", "DECLINED")
    ]
    assert _consent_of(dl, owner_p.id_, embargo_id) == "DECLINED"


@pytest.mark.spec("MSM-07-004")
def test_record_actor_rejection_of_proposed_terms_keeps_a_signatory(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Refusing proposed terms declines that row only; the signatory stays bound."""
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    active = _make_embargo(dl, case.id_)
    proposed_id = "https://example.org/embargoes/proposed"
    activate(case, active.id_)
    dl.save(case)
    _seed_consent(dl, owner_p.id_, active.id_, ECS.ACCEPTED)
    _seed_consent(dl, owner_p.id_, proposed_id, ECS.ACCEPTED)
    lifecycle = EmbargoLifecycle(persistence=dl)

    changes = lifecycle._record_actor_rejection(
        case, owner.id_, proposed_id, withdrawal=False
    )

    assert [(c.embargo_id, c.consent_after) for c in changes] == [
        (proposed_id, "DECLINED")
    ]
    assert _consent_of(dl, owner_p.id_, active.id_) == "ACCEPTED"
    assert _is_signatory(dl, case.id_, owner_p.id_)


@pytest.mark.spec("MSM-07-004")
def test_record_actor_rejection_of_proposed_terms_declines_an_invited_row(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A participant only invited to the proposal declines that row."""
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    proposed_id = "https://example.org/embargoes/p"
    _seed_consent(dl, owner_p.id_, proposed_id, ECS.INVITED)
    lifecycle = EmbargoLifecycle(persistence=dl)

    changes = lifecycle._record_actor_rejection(
        case, owner.id_, proposed_id, withdrawal=False
    )

    assert [c.consent_after for c in changes] == [ECS.DECLINED.value]


@pytest.mark.spec("MSM-07-004", "CM-18-003")
def test_record_actor_rejection_of_a_never_asked_embargo_records_a_decline(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """DECLINE is legal with no row: a Reject before any Invite is an answer."""
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    lifecycle = EmbargoLifecycle(persistence=dl)
    embargo_id = "https://example.org/embargoes/p"

    changes = lifecycle._record_actor_rejection(
        case, owner.id_, embargo_id, withdrawal=False
    )

    assert [(c.consent_before, c.consent_after) for c in changes] == [
        (None, "DECLINED")
    ]
    assert _consent_of(dl, owner_p.id_, embargo_id) == "DECLINED"


@pytest.mark.spec("MSM-07-004", "MSM-07-006")
@pytest.mark.parametrize("withdrawal", [True, False])
def test_accept_and_reject_after_the_embargo_exited_record_nothing(
    owner_and_dl: tuple[as_Service, SqliteDataLayer], withdrawal: bool
) -> None:
    """Once EM is EXITED an Accept or a Reject binds nothing (ADR-0118)."""
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    embargo_id = "https://example.org/embargoes/gone"
    other_id = "https://example.org/embargoes/other"
    activate(case, embargo_id)
    terminate(case)
    dl.save(case)
    _seed_consent(dl, owner_p.id_, embargo_id, ECS.ACCEPTED)
    lifecycle = EmbargoLifecycle(persistence=dl)

    rejected = lifecycle._record_actor_rejection(
        case, owner.id_, embargo_id, withdrawal=withdrawal
    )
    accepted = lifecycle._record_actor_acceptance(case, owner.id_, other_id)

    assert rejected == [] and accepted == []
    assert _consents_of(dl, owner_p.id_) == {embargo_id: "ACCEPTED"}


@pytest.mark.spec("MSM-07-004", "CM-18-003")
def test_record_actor_rejection_declines_an_expired_participant(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A late explicit Reject from EXPIRED is an answer: EXPIRED -> DECLINED."""
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    embargo_id = "https://example.org/embargoes/p"
    _seed_consent(dl, owner_p.id_, embargo_id, ECS.EXPIRED)
    lifecycle = EmbargoLifecycle(persistence=dl)

    changes = lifecycle._record_actor_rejection(
        case, owner.id_, embargo_id, withdrawal=False
    )

    assert [(c.consent_before, c.consent_after) for c in changes] == [
        ("EXPIRED", "DECLINED")
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
    activate(case, active.id_)
    propose(case, proposed.id_)
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
def test_record_actor_acceptance_for_a_declined_actor_records_nothing(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A DECLINED row holds no consent until re-invited (#4003)."""
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    embargo_id = "https://example.org/embargoes/e1"
    _seed_consent(dl, owner_p.id_, embargo_id, ECS.DECLINED)
    lifecycle = EmbargoLifecycle(persistence=dl)

    changes = lifecycle._record_actor_acceptance(case, owner.id_, embargo_id)

    assert changes == []
    assert _consent_of(dl, owner_p.id_, embargo_id) == "DECLINED"


@pytest.mark.spec("MSM-07-004")
def test_record_actor_rejection_withdrawal_declines_every_accepted_proposal(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Withdrawal from A declines A and each open revision the actor accepted.

    A refusal of B alone declines B only.  An open proposal the actor never
    accepted gets no row.
    """
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    active = _make_embargo(dl, case.id_)
    revision = _make_embargo(dl, case.id_, days=90)
    unanswered = _make_embargo(dl, case.id_, days=120)
    activate(case, active.id_)
    propose(case, revision.id_, unanswered.id_)
    dl.save(case)
    lifecycle = EmbargoLifecycle(persistence=dl)

    _seed_consent(dl, owner_p.id_, active.id_, ECS.ACCEPTED)
    _seed_consent(dl, owner_p.id_, revision.id_, ECS.ACCEPTED)
    refused = lifecycle._record_actor_rejection(
        case, owner.id_, revision.id_, withdrawal=False
    )
    assert [c.embargo_id for c in refused] == [revision.id_]
    assert _consents_of(dl, owner_p.id_) == {
        active.id_: "ACCEPTED",
        revision.id_: "DECLINED",
    }

    _seed_consent(dl, owner_p.id_, revision.id_, ECS.ACCEPTED)
    withdrawn = lifecycle._record_actor_rejection(
        case, owner.id_, active.id_, withdrawal=True
    )
    assert {c.embargo_id for c in withdrawn} == {active.id_, revision.id_}
    assert _consents_of(dl, owner_p.id_) == {
        active.id_: "DECLINED",
        revision.id_: "DECLINED",
    }


# ---------------------------------------------------------------------------
# Consent at activation (ADR-0122, EP-05-001)
# ---------------------------------------------------------------------------


def _activate(
    dl: SqliteDataLayer,
    case: VulnerabilityCase,
    *,
    previous_id: str | None,
    revised_id: str,
    ends_no_later: bool | None,
) -> list[str]:
    """Run ``_consent_at_activation``, switch the active embargo; changed ids."""
    changes = EmbargoLifecycle(persistence=dl)._consent_at_activation(
        case,
        embargo_id=revised_id,
        previous_embargo_id=previous_id,
        ends_no_later=ends_no_later,
    )
    fresh = cast(VulnerabilityCase, dl.read(case.id_))
    activate(fresh, revised_id)
    dl.save(fresh)
    return [c.participant_id for c in changes]


def _is_active(dl: SqliteDataLayer, case_id: str, participant_id: str) -> bool:
    """The content gate's answer for the participant (CM-10-004)."""
    case = cast(VulnerabilityCase, dl.read(case_id))
    return case.is_active_participant(
        cast(CaseParticipant, dl.read(participant_id))
    )


@pytest.mark.spec("EP-05-001", "CM-10-001")
def test_shorter_revision_carries_every_accepting_signatory_over(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Containment: a B ending no later than A carries over A's accepters only.

    The owner gains B as its own acceptance; a signatory to A gains an
    ACCEPTED row for B; a participant that declined B keeps its answer even
    though it accepted A; one that never accepted A gets nothing.
    """
    owner, dl = owner_and_dl
    signer = _make_actor(dl, "Signer")
    decliner = _make_actor(dl, "Decliner")
    bystander = _make_actor(dl, "Bystander")
    case, participants = _make_case(
        dl,
        owner.id_,
        extra_participant_ids=[signer.id_, decliner.id_, bystander.id_],
    )
    owner_p, signer_p, decliner_p, bystander_p = participants
    active = _make_embargo(dl, case.id_, days=90)
    shorter = _make_embargo(dl, case.id_, days=30)
    activate(case, active.id_)
    propose(case, shorter.id_)
    dl.save(case)
    _seed_consent(dl, owner_p.id_, active.id_, ECS.ACCEPTED)
    _seed_consent(dl, signer_p.id_, active.id_, ECS.ACCEPTED)
    _seed_consent(dl, decliner_p.id_, active.id_, ECS.ACCEPTED)
    _seed_consent(dl, decliner_p.id_, shorter.id_, ECS.DECLINED)
    _seed_consent(dl, bystander_p.id_, active.id_, ECS.INVITED)

    changed = _activate(
        dl,
        case,
        previous_id=active.id_,
        revised_id=shorter.id_,
        ends_no_later=True,
    )

    assert set(changed) == {owner_p.id_, signer_p.id_}
    assert _consent_of(dl, signer_p.id_, shorter.id_) == "ACCEPTED"
    assert _consent_of(dl, decliner_p.id_, shorter.id_) == "DECLINED"
    assert _consent_of(dl, bystander_p.id_, shorter.id_) is None
    assert _is_signatory(dl, case.id_, owner_p.id_)
    assert _is_signatory(dl, case.id_, signer_p.id_)
    assert not _is_signatory(dl, case.id_, decliner_p.id_)
    assert not _is_signatory(dl, case.id_, bystander_p.id_)


@pytest.mark.spec("EP-05-001", "CM-18-001")
def test_longer_revision_writes_only_the_owners_row_and_lapses_by_derivation(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A longer B carries nobody: non-accepters lapse by derivation, no write.

    The owner's acceptance of B is the only row written.  A signatory to A
    that has not accepted B keeps its A row untouched, is no longer a
    signatory, and ``has_lapsed`` holds; one that accepted B early stays
    bound.  The content gate reads the same lookup.
    """
    owner, dl = owner_and_dl
    signer = _make_actor(dl, "Signer")
    early = _make_actor(dl, "Early")
    case, participants = _make_case(
        dl,
        owner.id_,
        extra_participant_ids=[signer.id_, early.id_],
    )
    owner_p, signer_p, early_p = participants
    active = _make_embargo(dl, case.id_)
    longer = _make_embargo(dl, case.id_, days=90)
    activate(case, active.id_)
    propose(case, longer.id_)
    dl.save(case)
    for p in (owner_p, signer_p, early_p):
        _seed_consent(dl, p.id_, active.id_, ECS.ACCEPTED)
    _seed_consent(dl, early_p.id_, longer.id_, ECS.ACCEPTED)

    changed = _activate(
        dl,
        case,
        previous_id=active.id_,
        revised_id=longer.id_,
        ends_no_later=False,
    )

    assert changed == [owner_p.id_]
    assert _consents_of(dl, signer_p.id_) == {active.id_: "ACCEPTED"}
    assert _has_lapsed(dl, case.id_, signer_p.id_)
    assert not _is_signatory(dl, case.id_, signer_p.id_)
    assert not _is_active(dl, case.id_, signer_p.id_)
    assert _is_signatory(dl, case.id_, owner_p.id_)
    assert _is_signatory(dl, case.id_, early_p.id_)
    assert not _has_lapsed(dl, case.id_, early_p.id_)
    assert _is_active(dl, case.id_, early_p.id_)


@pytest.mark.spec("EP-05-001", "CM-10-001")
def test_first_activation_writes_nothing_and_holders_are_signatories(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """No advance step: ACCEPTED(B) holders are signatories by lookup."""
    owner, dl = owner_and_dl
    early = _make_actor(dl, "Early")
    late = _make_actor(dl, "Late")
    case, participants = _make_case(
        dl,
        owner.id_,
        extra_participant_ids=[early.id_, late.id_],
    )
    owner_p, early_p, late_p = participants
    proposal = _make_embargo(dl, case.id_)
    propose(case, proposal.id_)
    dl.save(case)
    _seed_consent(dl, owner_p.id_, proposal.id_, ECS.ACCEPTED)
    _seed_consent(dl, early_p.id_, proposal.id_, ECS.ACCEPTED)
    _seed_consent(dl, late_p.id_, proposal.id_, ECS.INVITED)
    before = {p.id_: _consents_of(dl, p.id_) for p in participants}

    changed = _activate(
        dl,
        case,
        previous_id=None,
        revised_id=proposal.id_,
        ends_no_later=None,
    )

    assert changed == []
    assert {p.id_: _consents_of(dl, p.id_) for p in participants} == before
    assert _is_signatory(dl, case.id_, owner_p.id_)
    assert _is_signatory(dl, case.id_, early_p.id_)
    assert not _is_signatory(dl, case.id_, late_p.id_)
    assert not _has_lapsed(dl, case.id_, late_p.id_)


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
def test_first_activation_promotes_an_inert_participant_only_by_its_own_reply(
    owner_and_dl: tuple[as_Service, SqliteDataLayer], how: str
) -> None:
    """Activation writes nothing for an inert participant (only the owner's row).

    Both participants are inert.  The one whose own row for the activated
    embargo is ACCEPTED (it accepted early) is a signatory by lookup; the one
    that never replied stays merely INVITED and is not.
    """
    owner, dl = owner_and_dl
    replied = _make_actor(dl, "Replied")
    silent = _make_actor(dl, "Silent")
    case, participants = _make_case(
        dl,
        owner.id_,
        extra_participant_ids=[replied.id_, silent.id_],
    )
    owner_p, replied_p, silent_p = participants
    embargo = _make_embargo(dl, case.id_)
    propose(case, embargo.id_)
    dl.save(case)
    _seed_consent(dl, replied_p.id_, embargo.id_, ECS.ACCEPTED)
    _seed_consent(dl, silent_p.id_, embargo.id_, ECS.INVITED)
    _make_inert(dl, replied_p.id_, how)
    _make_inert(dl, silent_p.id_, how)

    changed = _activate(
        dl,
        case,
        previous_id=None,
        revised_id=embargo.id_,
        ends_no_later=None,
    )

    # The activation is the owner's agreement (ADR-0122); nobody else moves.
    assert changed == [owner_p.id_]
    assert _is_signatory(dl, case.id_, replied_p.id_)
    assert not _is_signatory(dl, case.id_, silent_p.id_)
    assert _consent_of(dl, silent_p.id_, embargo.id_) == "INVITED"


@pytest.mark.spec("EP-05-001")
@pytest.mark.parametrize("how", ["unjoined", "closed"])
def test_longer_revision_lapses_an_inert_signatory_too(
    owner_and_dl: tuple[as_Service, SqliteDataLayer], how: str
) -> None:
    """A signatory that never accepted longer terms lapses, inert or not.

    Derivation does not look at joined/closed, so an inert participant cannot
    stay bound to terms it never agreed to — and a closed participant that
    still receives case content is not admitted to the longer period's content
    (CM-10-004).
    """
    owner, dl = owner_and_dl
    inert = _make_actor(dl, "Inert")
    case, participants = _make_case(
        dl,
        owner.id_,
        extra_participant_ids=[inert.id_],
    )
    owner_p, inert_p = participants
    active = _make_embargo(dl, case.id_)
    longer = _make_embargo(dl, case.id_, days=90)
    activate(case, active.id_)
    propose(case, longer.id_)
    dl.save(case)
    _seed_consent(dl, owner_p.id_, active.id_, ECS.ACCEPTED)
    _seed_consent(dl, inert_p.id_, active.id_, ECS.ACCEPTED)
    _make_inert(dl, inert_p.id_, how)

    _activate(
        dl,
        case,
        previous_id=active.id_,
        revised_id=longer.id_,
        ends_no_later=False,
    )

    assert _has_lapsed(dl, case.id_, inert_p.id_)
    assert not _is_signatory(dl, case.id_, inert_p.id_)
    assert not _is_active(dl, case.id_, inert_p.id_)
