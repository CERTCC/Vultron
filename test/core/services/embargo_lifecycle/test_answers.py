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


"""``accept_embargo_invite`` and ``reject_embargo_invite`` (answers.py).

Owner versus non-owner behaviour, STRICT and OBSERVED mode, idempotency,
pruning of decided proposals (EP-08-003), and the per-embargo consent rules
of ADR-0093: the revision-activation cascade (EP-05-001, MSM-07-005), a
signatory's answer to a *proposed* revision (MSM-07-003), and which embargo
a Reject names (MSM-07-004)."""

from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    TransitionMode,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC, PEC_Trigger
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronValidationError,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_participant import CaseParticipant

from .conftest import (
    _accepted_ids_of,
    _make_actor,
    _make_case,
    _make_embargo,
    _pec_of,
    _seed_consent,
)

# ---------------------------------------------------------------------------
# Tests: accept_embargo_invite
# ---------------------------------------------------------------------------


def test_accept_embargo_invite_owner_strict_valid(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Owner accepts an embargo invite: PROPOSED → ACTIVE, PEC updated."""
    owner, dl = owner_and_dl
    case, participants = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
    owner_participant_id = participants[0].id_
    embargo = _make_embargo(dl, case.id_)

    # Seed owner to INVITED so ACCEPT transition is valid
    owner_p = cast(CaseParticipant, dl.read(owner_participant_id))
    object.__setattr__(owner_p, "embargo_consent_state", PEC.INVITED)
    dl.save(owner_p)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.accept_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
    )

    assert result.em_before == EM.PROPOSED
    assert result.em_after == EM.ACTIVE
    assert result.case_embargo_changed is True

    owner_participant = cast(CaseParticipant, dl.read(owner_participant_id))
    assert owner_participant.embargo_consent_state == PEC.SIGNATORY.value


def test_accept_embargo_invite_non_owner_strict(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Non-owner accepting invite: only PEC updated, EM state unchanged."""
    owner, dl = owner_and_dl
    finder = _make_actor(dl, "Finder Org")
    case, _ = _make_case(
        dl,
        owner.id_,
        extra_participant_ids=[finder.id_],
        em_state=EM.PROPOSED,
    )
    embargo = _make_embargo(dl, case.id_)

    # Seed finder to INVITED so ACCEPT transition is valid
    finder_participant_id = case.actor_participant_index.get(finder.id_)
    assert finder_participant_id is not None
    finder_p = cast(CaseParticipant, dl.read(finder_participant_id))
    object.__setattr__(finder_p, "embargo_consent_state", PEC.INVITED)
    dl.save(finder_p)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.accept_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=finder.id_,  # non-owner
    )

    # EM must not change: only owner drives the EM machine
    assert result.em_after == EM.PROPOSED
    assert result.case_embargo_changed is False

    finder_participant = cast(CaseParticipant, dl.read(finder_participant_id))
    assert finder_participant.embargo_consent_state == PEC.SIGNATORY.value


def test_accept_embargo_invite_strict_invalid_state_raises(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Owner accept from EXITED state raises VultronInvalidStateTransitionError."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.EXITED)
    embargo = _make_embargo(dl, case.id_)

    lifecycle = EmbargoLifecycle(persistence=dl)
    with pytest.raises(VultronInvalidStateTransitionError):
        lifecycle.accept_embargo_invite(
            case_id=case.id_,
            embargo_id=embargo.id_,
            actor_id=owner.id_,
        )


def test_accept_embargo_invite_observed_invalid_state_no_raise(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """OBSERVED mode: invalid start state syncs to ACTIVE without raising."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.EXITED)
    embargo = _make_embargo(dl, case.id_)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.accept_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
        transition_mode=TransitionMode.OBSERVED,
    )

    assert result.em_after == EM.ACTIVE


def test_accept_embargo_invite_observed_already_active_syncs_embargo(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """OBSERVED accept when EM already ACTIVE but active_embargo differs: syncs."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.ACTIVE)
    old_embargo = _make_embargo(dl, case.id_)
    # Simulate active_embargo pointing at a different (old) embargo
    case.active_embargo = old_embargo.id_
    dl.save(case)

    new_embargo = _make_embargo(dl, case.id_)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.accept_embargo_invite(
        case_id=case.id_,
        embargo_id=new_embargo.id_,
        actor_id=owner.id_,
        transition_mode=TransitionMode.OBSERVED,
    )

    # EM stays ACTIVE (already there)
    assert result.em_after == EM.ACTIVE
    # But active_embargo must be updated to point at the new embargo
    refreshed_case = cast(VulnerabilityCase, dl.read(case.id_))
    assert _as_id(refreshed_case.active_embargo) == new_embargo.id_


def test_accept_embargo_invite_idempotent(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Accepting the same embargo twice is idempotent for PEC."""
    owner, dl = owner_and_dl
    case, participants = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
    owner_participant_id = participants[0].id_
    embargo = _make_embargo(dl, case.id_)

    # Seed as INVITED so first ACCEPT is valid
    owner_p = cast(CaseParticipant, dl.read(owner_participant_id))
    object.__setattr__(owner_p, "embargo_consent_state", PEC.INVITED)
    dl.save(owner_p)

    lifecycle = EmbargoLifecycle(persistence=dl)
    lifecycle.accept_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
    )
    # Second call: EM now ACTIVE; owner is non-owner w.r.t. EM gate (ACTIVE can't accept again)
    # The PEC side should still be idempotent
    lifecycle.accept_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
        transition_mode=TransitionMode.OBSERVED,
    )

    owner_participant = cast(CaseParticipant, dl.read(owner_participant_id))
    # accepted_embargo_ids should not contain duplicates
    assert owner_participant.accepted_embargo_ids.count(embargo.id_) == 1


# ---------------------------------------------------------------------------
# Tests: reject_embargo_invite
# ---------------------------------------------------------------------------


def test_reject_embargo_invite_owner_proposed_to_none(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Owner rejects from PROPOSED (ER): EM → NONE; the owner, not yet bound, declines.

    The owner is also a rejecting participant (MSM-07-004 rule 2): with no
    embargo in force, refusing the proposed terms is a DECLINE.
    """
    owner, dl = owner_and_dl
    case, participants = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
    owner_participant_id = participants[0].id_
    embargo = _make_embargo(dl, case.id_)
    case.proposed_embargoes = [embargo.id_]
    dl.save(case)

    # Seed owner to INVITED so DECLINE transition is valid
    owner_p = cast(CaseParticipant, dl.read(owner_participant_id))
    object.__setattr__(owner_p, "embargo_consent_state", PEC.INVITED)
    dl.save(owner_p)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.reject_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
    )

    assert result.em_before == EM.PROPOSED
    assert result.em_after == EM.NONE
    assert result.case_changed is True

    owner_participant = cast(CaseParticipant, dl.read(owner_participant_id))
    assert owner_participant.embargo_consent_state == PEC.DECLINED.value


@pytest.mark.spec("MSM-07-004")
def test_reject_embargo_invite_signatory_owner_rejecting_first_proposal_declines(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """With no embargo in force, a SIGNATORY owner's ER is a DECLINE — there is no
    active embargo for the refusal to leave the owner bound to.

    (A participant reaches SIGNATORY without an active embargo only through
    implicit consent, CM-14-005; the case-level state is what the rule reads.)
    """
    owner, dl = owner_and_dl
    case, participants = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
    owner_participant_id = participants[0].id_
    embargo = _make_embargo(dl, case.id_)
    case.proposed_embargoes = [embargo.id_]
    dl.save(case)
    _seed_consent(dl, owner_participant_id, PEC.SIGNATORY, [embargo.id_])

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.reject_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
    )

    assert result.em_before == EM.PROPOSED
    assert result.em_after == EM.NONE
    # A proposed, non-active embargo: a SIGNATORY keeps its state (MSM-07-004).
    assert _pec_of(dl, owner_participant_id) == PEC.SIGNATORY.value
    assert _accepted_ids_of(dl, owner_participant_id) == []


def test_reject_embargo_invite_owner_revise_stays_active(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Owner rejects from REVISE (EJ): EM → ACTIVE under the prior terms."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.REVISE)
    active = _make_embargo(dl, case.id_)
    revision = _make_embargo(dl, case.id_, days=90)
    case.active_embargo = active.id_
    case.proposed_embargoes = [revision.id_]
    dl.save(case)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.reject_embargo_invite(
        case_id=case.id_,
        embargo_id=revision.id_,
        actor_id=owner.id_,
    )

    assert result.em_before == EM.REVISE
    assert result.em_after == EM.ACTIVE
    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.active_embargo_id == active.id_
    assert updated.proposed_embargoes == []


def test_reject_embargo_invite_non_owner_strict(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Non-owner rejecting: only PEC updated, EM state unchanged."""
    owner, dl = owner_and_dl
    finder = _make_actor(dl, "Finder Org")
    case, _ = _make_case(
        dl,
        owner.id_,
        extra_participant_ids=[finder.id_],
        em_state=EM.PROPOSED,
    )
    embargo = _make_embargo(dl, case.id_)
    case.proposed_embargoes = [embargo.id_]
    dl.save(case)

    # Seed finder to INVITED so DECLINE transition is valid
    finder_participant_id = case.actor_participant_index.get(finder.id_)
    assert finder_participant_id is not None
    finder_p = cast(CaseParticipant, dl.read(finder_participant_id))
    object.__setattr__(finder_p, "embargo_consent_state", PEC.INVITED)
    dl.save(finder_p)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.reject_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=finder.id_,
    )

    assert result.em_after == EM.PROPOSED  # EM unchanged

    finder_participant = cast(CaseParticipant, dl.read(finder_participant_id))
    assert finder_participant.embargo_consent_state == PEC.DECLINED.value


@pytest.mark.spec("MSM-07-004")
@pytest.mark.spec("CM-18-003")
def test_reject_embargo_invite_signatory_non_owner_transitions_to_declined(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """SIGNATORY non-owner rejecting the *active* embargo withdraws → DECLINED (ADR-0093)."""
    owner, dl = owner_and_dl
    finder = _make_actor(dl, "Finder Org")
    case, _ = _make_case(
        dl,
        owner.id_,
        extra_participant_ids=[finder.id_],
        em_state=EM.ACTIVE,
    )
    embargo = _make_embargo(dl, case.id_)
    case.active_embargo = embargo.id_
    dl.save(case)

    # Seed finder to SIGNATORY via proper FSM path (UNBOUND → SIGNATORY).
    finder_participant_id = case.actor_participant_index.get(finder.id_)
    assert finder_participant_id is not None
    finder_p = cast(CaseParticipant, dl.read(finder_participant_id))
    finder_p.apply_pec_transition(PEC_Trigger.ACCEPT)
    finder_p.accepted_embargo_ids = [embargo.id_]
    dl.save(finder_p)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.reject_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=finder.id_,
    )

    assert result.em_after == EM.ACTIVE  # case-level EM unchanged (VP-13-009)

    finder_participant = cast(CaseParticipant, dl.read(finder_participant_id))
    assert finder_participant.embargo_consent_state == PEC.DECLINED.value
    # embargo_adherence derives from consent state: False when not SIGNATORY
    ps = finder_participant.participant_status
    assert ps is not None
    assert ps.embargo_adherence is False


def test_reject_embargo_invite_strict_invalid_state_raises(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Reject from invalid EM state (NONE) raises in STRICT mode."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.NONE)
    embargo = _make_embargo(dl, case.id_)
    case.proposed_embargoes = [embargo.id_]
    dl.save(case)

    lifecycle = EmbargoLifecycle(persistence=dl)
    with pytest.raises(VultronInvalidStateTransitionError):
        lifecycle.reject_embargo_invite(
            case_id=case.id_,
            embargo_id=embargo.id_,
            actor_id=owner.id_,
        )


def test_reject_embargo_invite_observed_invalid_no_raise(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """OBSERVED mode: invalid start state syncs to fallback without raising."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.NONE)
    embargo = _make_embargo(dl, case.id_)
    case.proposed_embargoes = [embargo.id_]
    dl.save(case)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.reject_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
        transition_mode=TransitionMode.OBSERVED,
    )

    assert result.em_after == EM.NONE


# ---------------------------------------------------------------------------
# Tests: a decided proposal leaves the open-proposal records (EP-08-003)
# ---------------------------------------------------------------------------


@pytest.mark.spec("EP-08-003")
def test_owner_accept_prunes_the_proposal_and_a_re_accept_changes_nothing(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """The owner's accept decides the proposal; an idempotent re-accept is a no-op.

    ``proposed_embargoes`` and ``pending_embargo_proposal_index`` both drop the
    entry on the first accept.  The second accept finds nothing to prune and
    reports the case unchanged apart from consent bookkeeping.
    """
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
    embargo = _make_embargo(dl, case.id_)
    case.proposed_embargoes.append(embargo.id_)
    case.pending_embargo_proposal_index[embargo.id_] = "urn:proposal:1"
    dl.save(case)

    lifecycle = EmbargoLifecycle(persistence=dl)
    lifecycle.accept_embargo_invite(
        case_id=case.id_, embargo_id=embargo.id_, actor_id=owner.id_
    )
    first = cast(VulnerabilityCase, dl.read(case.id_))
    assert first.current_status.em.state == EM.ACTIVE
    assert first.proposed_embargoes == []
    assert first.pending_embargo_proposal_index == {}

    second_result = lifecycle.accept_embargo_invite(
        case_id=case.id_, embargo_id=embargo.id_, actor_id=owner.id_
    )
    second = cast(VulnerabilityCase, dl.read(case.id_))
    assert second_result.em_after == EM.ACTIVE
    assert second_result.case_embargo_changed is False
    assert second.proposed_embargoes == []
    assert second.pending_embargo_proposal_index == {}


@pytest.mark.spec("EP-08-003")
def test_participant_accept_is_consent_and_prunes_nothing(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A non-owner's accept records consent; the proposal stays open."""
    owner, dl = owner_and_dl
    participant = _make_actor(dl, "Participant")
    case, _ = _make_case(
        dl,
        owner.id_,
        extra_participant_ids=[participant.id_],
        em_state=EM.PROPOSED,
    )
    embargo = _make_embargo(dl, case.id_)
    case.proposed_embargoes.append(embargo.id_)
    case.pending_embargo_proposal_index[embargo.id_] = "urn:proposal:1"
    dl.save(case)

    EmbargoLifecycle(persistence=dl).accept_embargo_invite(
        case_id=case.id_, embargo_id=embargo.id_, actor_id=participant.id_
    )

    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.current_status.em.state == EM.PROPOSED
    assert updated.proposed_embargoes == [embargo.id_]
    assert updated.pending_embargo_proposal_index == {
        embargo.id_: "urn:proposal:1"
    }


# ---------------------------------------------------------------------------
# Tests: the owner decides a revision without waiting (EP-09-005, EP-09-006)
# ---------------------------------------------------------------------------


@pytest.mark.spec("EP-09-005")
@pytest.mark.spec("EP-09-006")
def test_owner_may_activate_a_revision_before_anyone_else_answers(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Nothing blocks the owner's decision on an open revision (EP-09-005).

    A participant proposes B while A is active; no other participant has
    answered the relayed Invite; the owner's accept activates B anyway.  The
    SHOULD in EP-09-006 (wait for some answers to gauge consensus) is actor
    policy at the owner's accept/reject call-out, not a protocol gate, which
    is exactly what this test pins: the lifecycle service imposes no quorum,
    no vote and no waiting period.
    """
    owner, dl = owner_and_dl
    proposer = _make_actor(dl, "Proposer")
    bystander = _make_actor(dl, "Bystander")
    case, _ = _make_case(
        dl,
        owner.id_,
        extra_participant_ids=[proposer.id_, bystander.id_],
        em_state=EM.ACTIVE,
    )
    active = _make_embargo(dl, case.id_)
    case.active_embargo = active.id_
    dl.save(case)
    revision = _make_embargo(dl, case.id_)

    lifecycle = EmbargoLifecycle(persistence=dl)
    proposed = lifecycle.propose_embargo(
        case_id=case.id_, embargo_id=revision.id_, actor_id=proposer.id_
    )
    assert proposed.em_after == EM.REVISE

    decided = lifecycle.accept_embargo_invite(
        case_id=case.id_, embargo_id=revision.id_, actor_id=owner.id_
    )

    assert decided.em_after == EM.ACTIVE
    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.active_embargo_id == revision.id_


# ---------------------------------------------------------------------------
# Tests: consent is per embargo; activation re-evaluates it (ADR-0093)
# ---------------------------------------------------------------------------


def _revision_case(
    dl: SqliteDataLayer,
    owner: as_Service,
    *,
    revision_days: int,
) -> tuple[VulnerabilityCase, dict[str, str], str, str]:
    """Case at REVISE: A (45d) active, B (*revision_days*) proposed.

    Participants and their seeded consent (all signatories hold A):

    - ``owner``: SIGNATORY, [A]
    - ``lacking``: SIGNATORY, [A]            — has not accepted B
    - ``accepted``: SIGNATORY, [A, B]        — accepted B while REVISE
    - ``invited_with_b``: INVITED, [B]       — accepted B, never bound by A
    - ``lapsed_plain``: LAPSED, []           — lapsed earlier, no B
    - ``declined``: DECLINED, []

    Returns the case, ``{label: participant_id}``, A's id and B's id.
    """
    actors = {
        label: _make_actor(dl, label)
        for label in (
            "lacking",
            "accepted",
            "invited_with_b",
            "lapsed_plain",
            "declined",
        )
    }
    case, participants = _make_case(
        dl,
        owner.id_,
        extra_participant_ids=[a.id_ for a in actors.values()],
        em_state=EM.REVISE,
    )
    ids = {"owner": participants[0].id_}
    for (label, _actor), participant in zip(
        actors.items(), participants[1:], strict=True
    ):
        ids[label] = participant.id_
    active = _make_embargo(dl, case.id_)
    revision = _make_embargo(dl, case.id_, days=revision_days)
    case.active_embargo = active.id_
    case.proposed_embargoes = [revision.id_]
    case.pending_embargo_proposal_index = {
        revision.id_: f"{case.id_}/embargo_proposals/revision"
    }
    dl.save(case)

    _seed_consent(dl, ids["owner"], PEC.SIGNATORY, [active.id_])
    _seed_consent(dl, ids["lacking"], PEC.SIGNATORY, [active.id_])
    _seed_consent(
        dl, ids["accepted"], PEC.SIGNATORY, [active.id_, revision.id_]
    )
    _seed_consent(dl, ids["invited_with_b"], PEC.INVITED, [revision.id_])
    _seed_consent(dl, ids["lapsed_plain"], PEC.LAPSED, [])
    _seed_consent(dl, ids["declined"], PEC.DECLINED, [])
    return case, ids, active.id_, revision.id_


@pytest.mark.spec("EP-05-001")
@pytest.mark.spec("MSM-07-005")
@pytest.mark.spec("CM-10-001")
def test_owner_activating_a_shorter_revision_carries_every_signatory_over(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """B ends before A: every signatory to A gains B; nobody lapses.

    Agreeing to N days is agreeing to every shorter period (containment).  A
    non-signatory that already accepted B becomes SIGNATORY; a LAPSED or
    DECLINED participant without B is untouched.
    """
    owner, dl = owner_and_dl
    case, ids, active_id, revision_id = _revision_case(
        dl, owner, revision_days=30
    )

    result = EmbargoLifecycle(persistence=dl).accept_embargo_invite(
        case_id=case.id_, embargo_id=revision_id, actor_id=owner.id_
    )

    assert result.em_before == EM.REVISE
    assert result.em_after == EM.ACTIVE
    assert result.case_embargo_changed is True
    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.active_embargo_id == revision_id
    assert updated.proposed_embargoes == []
    assert updated.pending_embargo_proposal_index == {}

    for label in ("owner", "lacking", "accepted"):
        assert _pec_of(dl, ids[label]) == PEC.SIGNATORY.value, label
        assert revision_id in _accepted_ids_of(dl, ids[label]), label
    assert _pec_of(dl, ids["invited_with_b"]) == PEC.SIGNATORY.value
    assert _pec_of(dl, ids["lapsed_plain"]) == PEC.LAPSED.value
    assert _pec_of(dl, ids["declined"]) == PEC.DECLINED.value
    # Only the invitee's *state* moved; carry-over is a list write.
    assert [
        (c.participant_id, c.pec_after) for c in result.participant_changes
    ] == [(ids["invited_with_b"], PEC.SIGNATORY.value)]


@pytest.mark.spec("EP-05-001")
@pytest.mark.spec("MSM-07-005")
@pytest.mark.spec("CM-18-002")
@pytest.mark.spec("CM-18-001")
def test_owner_activating_a_longer_revision_lapses_signatories_lacking_it(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """B ends after A: a SIGNATORY without B → LAPSED via REVISE; with B stays.

    LAPSED then means exactly CM-18-001's definition — was a signatory to the
    previous active embargo, which the owner replaced with longer terms this
    participant has not accepted.  The owner has just accepted B and is never
    lapsed by its own activation.
    """
    owner, dl = owner_and_dl
    case, ids, active_id, revision_id = _revision_case(
        dl, owner, revision_days=90
    )

    result = EmbargoLifecycle(persistence=dl).accept_embargo_invite(
        case_id=case.id_, embargo_id=revision_id, actor_id=owner.id_
    )

    assert result.em_after == EM.ACTIVE
    assert _pec_of(dl, ids["owner"]) == PEC.SIGNATORY.value
    assert revision_id in _accepted_ids_of(dl, ids["owner"])
    assert _pec_of(dl, ids["lacking"]) == PEC.LAPSED.value
    assert _accepted_ids_of(dl, ids["lacking"]) == [active_id]
    assert _pec_of(dl, ids["accepted"]) == PEC.SIGNATORY.value
    assert _pec_of(dl, ids["invited_with_b"]) == PEC.SIGNATORY.value
    assert _pec_of(dl, ids["lapsed_plain"]) == PEC.LAPSED.value
    assert _pec_of(dl, ids["declined"]) == PEC.DECLINED.value
    moves = {
        c.participant_id: (c.pec_before, c.pec_after)
        for c in result.participant_changes
    }
    assert moves == {
        ids["lacking"]: (PEC.SIGNATORY.value, PEC.LAPSED.value),
        ids["invited_with_b"]: (PEC.INVITED.value, PEC.SIGNATORY.value),
    }


@pytest.mark.spec("EP-05-001")
@pytest.mark.spec("MSM-07-005")
def test_activation_cascade_runs_in_observed_mode_too(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A replica syncing the owner's EC lapses the same signatories the manager did."""
    owner, dl = owner_and_dl
    case, ids, _active_id, revision_id = _revision_case(
        dl, owner, revision_days=90
    )

    result = EmbargoLifecycle(persistence=dl).accept_embargo_invite(
        case_id=case.id_,
        embargo_id=revision_id,
        actor_id=owner.id_,
        transition_mode=TransitionMode.OBSERVED,
    )

    assert result.em_after == EM.ACTIVE
    assert _pec_of(dl, ids["lacking"]) == PEC.LAPSED.value
    assert _pec_of(dl, ids["accepted"]) == PEC.SIGNATORY.value


@pytest.mark.spec("EP-05-001")
def test_revise_to_active_without_changing_the_active_embargo_cascades_nothing(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """REVISE → ACTIVE that keeps A active re-evaluates nobody.

    The cascade is keyed on ``active_embargo`` changing, not on the EM
    transition: an owner's accept that names the embargo already in force
    (an idempotent re-accept while a revision is open) leaves every record
    alone.
    """
    owner, dl = owner_and_dl
    case, ids, active_id, _revision_id = _revision_case(
        dl, owner, revision_days=90
    )

    result = EmbargoLifecycle(persistence=dl).accept_embargo_invite(
        case_id=case.id_, embargo_id=active_id, actor_id=owner.id_
    )

    assert result.em_before == EM.REVISE
    assert result.em_after == EM.ACTIVE
    assert result.case_embargo_changed is False
    assert result.participant_changes == []
    assert _pec_of(dl, ids["lacking"]) == PEC.SIGNATORY.value
    assert _pec_of(dl, ids["invited_with_b"]) == PEC.INVITED.value
    assert cast(VulnerabilityCase, dl.read(case.id_)).active_embargo_id == (
        active_id
    )


@pytest.mark.spec("MSM-07-003")
def test_signatory_accepting_a_proposed_revision_records_the_id_only(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A non-owner SIGNATORY's accept of proposed B: list gains B, state unchanged.

    They were and remain a signatory to A, the embargo in force (MSM-07-003,
    ADR-0093 point 3); the EM machine does not move for a non-owner.
    """
    owner, dl = owner_and_dl
    case, ids, active_id, revision_id = _revision_case(
        dl, owner, revision_days=90
    )
    lacking_actor = next(
        a
        for a, p in case.actor_participant_index.items()
        if p == ids["lacking"]
    )

    result = EmbargoLifecycle(persistence=dl).accept_embargo_invite(
        case_id=case.id_, embargo_id=revision_id, actor_id=lacking_actor
    )

    assert result.em_after == EM.REVISE
    assert result.participant_changes == []
    assert _pec_of(dl, ids["lacking"]) == PEC.SIGNATORY.value
    assert _accepted_ids_of(dl, ids["lacking"]) == [active_id, revision_id]
    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.active_embargo_id == active_id
    assert updated.proposed_embargoes == [revision_id]


@pytest.mark.spec("MSM-07-003")
def test_non_signatory_accepting_a_proposed_revision_waits_for_activation(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """An INVITED participant accepting proposed B stays INVITED with B listed;
    it becomes SIGNATORY when the owner activates B."""
    owner, dl = owner_and_dl
    case, ids, _active_id, revision_id = _revision_case(
        dl, owner, revision_days=90
    )
    _seed_consent(dl, ids["invited_with_b"], PEC.INVITED, [])
    invitee_actor = next(
        a
        for a, p in case.actor_participant_index.items()
        if p == ids["invited_with_b"]
    )
    lifecycle = EmbargoLifecycle(persistence=dl)

    accepted = lifecycle.accept_embargo_invite(
        case_id=case.id_, embargo_id=revision_id, actor_id=invitee_actor
    )
    assert accepted.participant_changes == []
    assert _pec_of(dl, ids["invited_with_b"]) == PEC.INVITED.value
    assert _accepted_ids_of(dl, ids["invited_with_b"]) == [revision_id]

    lifecycle.accept_embargo_invite(
        case_id=case.id_, embargo_id=revision_id, actor_id=owner.id_
    )
    assert _pec_of(dl, ids["invited_with_b"]) == PEC.SIGNATORY.value


@pytest.mark.spec("MSM-07-004")
def test_owner_rejecting_a_revision_changes_no_participant_record(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """EJ returns EM to ACTIVE under A; nobody's state or list moves, the owner's included."""
    owner, dl = owner_and_dl
    case, ids, active_id, revision_id = _revision_case(
        dl, owner, revision_days=90
    )
    before = {
        label: (_pec_of(dl, pid), _accepted_ids_of(dl, pid))
        for label, pid in ids.items()
    }

    result = EmbargoLifecycle(persistence=dl).reject_embargo_invite(
        case_id=case.id_, embargo_id=revision_id, actor_id=owner.id_
    )

    assert result.em_before == EM.REVISE
    assert result.em_after == EM.ACTIVE
    assert result.participant_changes == []
    after = {
        label: (_pec_of(dl, pid), _accepted_ids_of(dl, pid))
        for label, pid in ids.items()
    }
    assert after == before
    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.active_embargo_id == active_id
    assert updated.proposed_embargoes == []


@pytest.mark.spec("MSM-07-004")
def test_signatory_rejecting_a_proposed_revision_keeps_its_consent_to_the_active_embargo(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Refusing B is not withdrawing from A: B leaves the list, state stays SIGNATORY."""
    owner, dl = owner_and_dl
    case, ids, active_id, revision_id = _revision_case(
        dl, owner, revision_days=90
    )
    accepted_actor = next(
        a
        for a, p in case.actor_participant_index.items()
        if p == ids["accepted"]
    )

    result = EmbargoLifecycle(persistence=dl).reject_embargo_invite(
        case_id=case.id_, embargo_id=revision_id, actor_id=accepted_actor
    )

    assert result.em_after == EM.REVISE
    assert result.participant_changes == []
    assert _pec_of(dl, ids["accepted"]) == PEC.SIGNATORY.value
    assert _accepted_ids_of(dl, ids["accepted"]) == [active_id]
    # A participant's Reject is consent, not a decision: B stays open.
    assert cast(VulnerabilityCase, dl.read(case.id_)).proposed_embargoes == [
        revision_id
    ]


@pytest.mark.spec("MSM-07-004")
def test_non_signatory_rejecting_a_proposed_revision_declines(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """INVITED → DECLINED: there is no consent to A for the refusal to leave intact."""
    owner, dl = owner_and_dl
    case, ids, _active_id, revision_id = _revision_case(
        dl, owner, revision_days=90
    )
    invitee_actor = next(
        a
        for a, p in case.actor_participant_index.items()
        if p == ids["invited_with_b"]
    )

    result = EmbargoLifecycle(persistence=dl).reject_embargo_invite(
        case_id=case.id_, embargo_id=revision_id, actor_id=invitee_actor
    )

    assert [
        (c.pec_before, c.pec_after) for c in result.participant_changes
    ] == [(PEC.INVITED.value, PEC.DECLINED.value)]
    assert _accepted_ids_of(dl, ids["invited_with_b"]) == []


@pytest.mark.spec("MSM-07-004")
@pytest.mark.spec("CM-18-003")
def test_signatory_rejecting_the_active_embargo_while_revise_withdraws(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A Reject naming A itself is withdrawal even with a revision open."""
    owner, dl = owner_and_dl
    case, ids, active_id, _revision_id = _revision_case(
        dl, owner, revision_days=90
    )
    lacking_actor = next(
        a
        for a, p in case.actor_participant_index.items()
        if p == ids["lacking"]
    )

    result = EmbargoLifecycle(persistence=dl).reject_embargo_invite(
        case_id=case.id_, embargo_id=active_id, actor_id=lacking_actor
    )

    assert result.em_after == EM.REVISE
    assert [
        (c.pec_before, c.pec_after) for c in result.participant_changes
    ] == [(PEC.SIGNATORY.value, PEC.DECLINED.value)]
    assert _accepted_ids_of(dl, ids["lacking"]) == []


def test_reject_naming_an_unknown_embargo_raises(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Neither active nor proposed on the case: a protocol error, not a consent change."""
    owner, dl = owner_and_dl
    case, ids, _active_id, _revision_id = _revision_case(
        dl, owner, revision_days=90
    )
    stranger = _make_embargo(dl, case.id_, days=10)
    before = _pec_of(dl, ids["owner"])

    with pytest.raises(VultronValidationError, match="neither the active"):
        EmbargoLifecycle(persistence=dl).reject_embargo_invite(
            case_id=case.id_, embargo_id=stranger.id_, actor_id=owner.id_
        )

    assert _pec_of(dl, ids["owner"]) == before
    assert cast(
        VulnerabilityCase, dl.read(case.id_)
    ).current_status.em.state == (EM.REVISE)
