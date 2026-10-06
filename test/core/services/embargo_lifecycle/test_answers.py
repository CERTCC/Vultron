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
of ADR-0093 and ADR-0122: the containment carry-over at activation
(EP-05-001, MSM-07-005), a
signatory's answer to a *proposed* revision (MSM-07-003), and which embargo
a Reject names (MSM-07-004)."""

from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    TransitionMode,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState as ECS,
)
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronNotFoundError,
    VultronValidationError,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service

from .conftest import (
    UNHELD_EMBARGO_ID,
    _assert_activation_wrote_nothing,
    _case_awaiting_activation,
    _consent_of,
    _consents_of,
    _has_lapsed,
    _is_signatory,
    _make_actor,
    _make_case,
    _make_embargo,
    _seed_consent,
)

# ---------------------------------------------------------------------------
# Tests: accept_embargo_invite
# ---------------------------------------------------------------------------


def test_accept_embargo_invite_owner_strict_valid(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Owner accepts an embargo invite: PROPOSED → ACTIVE, its row ACCEPTED."""
    owner, dl = owner_and_dl
    case, participants = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
    owner_participant_id = participants[0].id_
    embargo = _make_embargo(dl, case.id_)

    # Seed owner's row to INVITED so ACCEPT transition is valid
    _seed_consent(dl, owner_participant_id, embargo.id_, ECS.INVITED)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.accept_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
    )

    assert result.em_before == EM.PROPOSED
    assert result.em_after == EM.ACTIVE
    assert result.case_embargo_changed is True

    assert _consent_of(dl, owner_participant_id, embargo.id_) == "ACCEPTED"
    assert _is_signatory(dl, case.id_, owner_participant_id)


def test_accept_embargo_invite_non_owner_strict(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Non-owner accepting invite: only its row updated, EM state unchanged."""
    owner, dl = owner_and_dl
    finder = _make_actor(dl, "Finder Org")
    case, _ = _make_case(
        dl,
        owner.id_,
        extra_participant_ids=[finder.id_],
        em_state=EM.PROPOSED,
    )
    embargo = _make_embargo(dl, case.id_)

    # Seed finder's row to INVITED so ACCEPT transition is valid
    finder_participant_id = case.actor_participant_index.get(finder.id_)
    assert finder_participant_id is not None
    _seed_consent(dl, finder_participant_id, embargo.id_, ECS.INVITED)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.accept_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=finder.id_,  # non-owner
    )

    # EM must not change: only owner drives the EM machine
    assert result.em_after == EM.PROPOSED
    assert result.case_embargo_changed is False

    assert _consent_of(dl, finder_participant_id, embargo.id_) == "ACCEPTED"


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
    """Accepting the same embargo twice is idempotent for the consent row."""
    owner, dl = owner_and_dl
    case, participants = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
    owner_participant_id = participants[0].id_
    embargo = _make_embargo(dl, case.id_)

    # Seed as INVITED so first ACCEPT is valid
    _seed_consent(dl, owner_participant_id, embargo.id_, ECS.INVITED)

    lifecycle = EmbargoLifecycle(persistence=dl)
    lifecycle.accept_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
    )
    # Second call: EM now ACTIVE; owner is non-owner w.r.t. EM gate (ACTIVE can't accept again)
    # The consent side should still be idempotent
    lifecycle.accept_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
        transition_mode=TransitionMode.OBSERVED,
    )

    # one row, ACCEPTED, no duplicates
    assert _consents_of(dl, owner_participant_id) == {embargo.id_: "ACCEPTED"}
    owner_participant = cast(CaseParticipant, dl.read(owner_participant_id))
    assert len(owner_participant.embargo_consents) == 1


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

    # Seed owner's row to INVITED so DECLINE transition is valid
    _seed_consent(dl, owner_participant_id, embargo.id_, ECS.INVITED)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.reject_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
    )

    assert result.em_before == EM.PROPOSED
    assert result.em_after == EM.NONE
    assert result.case_changed is True

    assert _consent_of(dl, owner_participant_id, embargo.id_) == "DECLINED"


@pytest.mark.spec("MSM-07-004")
def test_reject_embargo_invite_signatory_owner_rejecting_first_proposal_declines(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """With no embargo in force, a Reject is withdrawal from any state.

    A participant holds ACCEPTED on a proposal before any embargo is active
    (the proposer, an early acceptor).  Rejecting the only proposal leaves
    nothing in force to stay signatory to, so the owner's own row for it
    becomes DECLINED (MSM-07-004).
    """
    owner, dl = owner_and_dl
    case, participants = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
    owner_participant_id = participants[0].id_
    embargo = _make_embargo(dl, case.id_)
    case.proposed_embargoes = [embargo.id_]
    dl.save(case)
    _seed_consent(dl, owner_participant_id, embargo.id_, ECS.ACCEPTED)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.reject_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
    )

    assert result.em_before == EM.PROPOSED
    assert result.em_after == EM.NONE
    assert [
        (c.consent_before, c.consent_after) for c in result.participant_changes
    ] == [("ACCEPTED", "DECLINED")]
    assert _consents_of(dl, owner_participant_id) == {embargo.id_: "DECLINED"}


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
    """Non-owner rejecting: only its row updated, EM state unchanged."""
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

    # Seed finder's row to INVITED so DECLINE transition is valid
    finder_participant_id = case.actor_participant_index.get(finder.id_)
    assert finder_participant_id is not None
    _seed_consent(dl, finder_participant_id, embargo.id_, ECS.INVITED)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.reject_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=finder.id_,
    )

    assert result.em_after == EM.PROPOSED  # EM unchanged

    assert _consent_of(dl, finder_participant_id, embargo.id_) == "DECLINED"


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

    # Seed finder as a signatory of the active embargo.
    finder_participant_id = case.actor_participant_index.get(finder.id_)
    assert finder_participant_id is not None
    _seed_consent(dl, finder_participant_id, embargo.id_, ECS.ACCEPTED)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.reject_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=finder.id_,
    )

    assert result.em_after == EM.ACTIVE  # case-level EM unchanged (VP-13-009)

    assert _consent_of(dl, finder_participant_id, embargo.id_) == "DECLINED"
    assert not _is_signatory(dl, case.id_, finder_participant_id)


def test_reject_embargo_invite_strict_invalid_state_raises(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Reject from invalid EM state (NONE) raises in STRICT mode — and writes nothing.

    The EM guard runs before the consent write, so a refused transition
    leaves the owner's rows exactly as they were.
    """
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_, em_state=EM.NONE)
    embargo = _make_embargo(dl, case.id_)
    case.proposed_embargoes = [embargo.id_]
    dl.save(case)
    _seed_consent(dl, owner_p.id_, embargo.id_, ECS.INVITED)

    lifecycle = EmbargoLifecycle(persistence=dl)
    with pytest.raises(VultronInvalidStateTransitionError):
        lifecycle.reject_embargo_invite(
            case_id=case.id_,
            embargo_id=embargo.id_,
            actor_id=owner.id_,
        )

    assert _consents_of(dl, owner_p.id_) == {embargo.id_: "INVITED"}


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
    participant_pid = case.actor_participant_index[participant.id_]
    assert _consents_of(dl, participant_pid) == {embargo.id_: "ACCEPTED"}


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
# Tests: consent is per embargo; activation carries it over (ADR-0122)
# ---------------------------------------------------------------------------


#: An embargo an earlier revision replaced; its signatories may still hold it.
OLD_EMBARGO_ID = "https://example.org/embargoes/replaced-earlier"


def _revision_case(
    dl: SqliteDataLayer,
    owner: as_Service,
    *,
    revision_days: int,
) -> tuple[VulnerabilityCase, dict[str, str], str, str]:
    """Case at REVISE: A (45d) active, B (*revision_days*) proposed.

    Participants and their seeded consent rows:

    - ``owner``: ACCEPTED(A)
    - ``lacking``: ACCEPTED(A)              — has not accepted B
    - ``accepted``: ACCEPTED(A), ACCEPTED(B) — accepted B while REVISE
    - ``invited_with_b``: ACCEPTED(B)       — accepted B, never bound by A
    - ``lapsed_plain``: ACCEPTED(OLD)       — bound by an earlier embargo only
    - ``declined``: DECLINED(A)

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

    _seed_consent(dl, ids["owner"], active.id_, ECS.ACCEPTED)
    _seed_consent(dl, ids["lacking"], active.id_, ECS.ACCEPTED)
    _seed_consent(dl, ids["accepted"], active.id_, ECS.ACCEPTED)
    _seed_consent(dl, ids["accepted"], revision.id_, ECS.ACCEPTED)
    _seed_consent(dl, ids["invited_with_b"], revision.id_, ECS.ACCEPTED)
    _seed_consent(dl, ids["lapsed_plain"], OLD_EMBARGO_ID, ECS.ACCEPTED)
    _seed_consent(dl, ids["declined"], active.id_, ECS.DECLINED)
    return case, ids, active.id_, revision.id_


@pytest.mark.spec("EP-05-001")
@pytest.mark.spec("MSM-07-005")
@pytest.mark.spec("CM-10-001")
def test_owner_activating_a_shorter_revision_carries_every_signatory_over(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """B ends before A: every signatory to A gains B; nobody lapses.

    Agreeing to N days is agreeing to every shorter period (containment).  A
    participant that already accepted B is a signatory with no further write;
    one bound only by an earlier embargo, and one that declined A, are
    untouched.
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

    for label in ("owner", "lacking", "accepted", "invited_with_b"):
        assert _consent_of(dl, ids[label], revision_id) == "ACCEPTED", label
        assert _is_signatory(dl, case.id_, ids[label]), label
        assert not _has_lapsed(dl, case.id_, ids[label]), label
    assert _consents_of(dl, ids["lacking"]) == {
        active_id: "ACCEPTED",
        revision_id: "ACCEPTED",
    }
    assert _consents_of(dl, ids["lapsed_plain"]) == {
        OLD_EMBARGO_ID: "ACCEPTED"
    }
    assert _has_lapsed(dl, case.id_, ids["lapsed_plain"])
    assert _consents_of(dl, ids["declined"]) == {active_id: "DECLINED"}
    assert not _is_signatory(dl, case.id_, ids["declined"])
    # Only the rows that actually moved are reported: the owner's own
    # acceptance and the carried-over silent signatory.
    assert {
        (c.participant_id, c.consent_before, c.consent_after)
        for c in result.participant_changes
    } == {
        (ids["owner"], None, "ACCEPTED"),
        (ids["lacking"], None, "ACCEPTED"),
    }


@pytest.mark.spec("EP-05-001")
@pytest.mark.spec("MSM-07-005")
@pytest.mark.spec("CM-18-002")
@pytest.mark.spec("CM-18-001")
@pytest.mark.spec("CM-18-016")
def test_owner_activating_a_longer_revision_lapses_signatories_lacking_it(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """B ends after A: a signatory without B lapses by derivation; nothing is written.

    ``has_lapsed`` then means exactly CM-18-001's definition — it accepted an
    earlier embargo, which the owner replaced with longer terms this
    participant has not accepted.  The owner has just accepted B and is never
    lapsed by its own activation.  No row is written for anyone else
    (CM-18-016).
    """
    owner, dl = owner_and_dl
    case, ids, active_id, revision_id = _revision_case(
        dl, owner, revision_days=90
    )
    before = {
        label: _consents_of(dl, pid)
        for label, pid in ids.items()
        if label != "owner"
    }

    result = EmbargoLifecycle(persistence=dl).accept_embargo_invite(
        case_id=case.id_, embargo_id=revision_id, actor_id=owner.id_
    )

    assert result.em_after == EM.ACTIVE
    assert _consents_of(dl, ids["owner"]) == {
        active_id: "ACCEPTED",
        revision_id: "ACCEPTED",
    }
    assert _is_signatory(dl, case.id_, ids["owner"])
    for label in ("accepted", "invited_with_b"):
        assert _is_signatory(dl, case.id_, ids[label]), label
    for label in ("lacking", "lapsed_plain"):
        assert _has_lapsed(dl, case.id_, ids[label]), label
        assert not _is_signatory(dl, case.id_, ids[label]), label
    assert not _has_lapsed(dl, case.id_, ids["declined"])
    assert not _is_signatory(dl, case.id_, ids["declined"])
    # Nobody but the owner has a row written.
    assert {
        label: _consents_of(dl, pid)
        for label, pid in ids.items()
        if label != "owner"
    } == before
    assert [
        (c.participant_id, c.embargo_id, c.consent_after)
        for c in result.participant_changes
    ] == [(ids["owner"], revision_id, "ACCEPTED")]


@pytest.mark.spec("EP-05-001")
@pytest.mark.spec("MSM-07-005")
def test_activation_cascade_runs_in_observed_mode_too(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A replica syncing the owner's EC derives the same lapses the manager did."""
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
    assert _has_lapsed(dl, case.id_, ids["lacking"])
    assert _is_signatory(dl, case.id_, ids["accepted"])


@pytest.mark.spec("EP-05-001")
def test_revise_to_active_without_changing_the_active_embargo_cascades_nothing(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """REVISE → ACTIVE that keeps A active carries nobody over.

    The carry-over is keyed on ``active_embargo`` changing, not on the EM
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
    assert _is_signatory(dl, case.id_, ids["lacking"])
    assert _consent_of(dl, ids["lacking"], _revision_id) is None
    assert cast(VulnerabilityCase, dl.read(case.id_)).active_embargo_id == (
        active_id
    )


@pytest.mark.spec("MSM-07-003")
def test_signatory_accepting_a_proposed_revision_marks_only_the_revision_row(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A non-owner signatory's accept of proposed B: row(B) ACCEPTED, A untouched.

    They were and remain a signatory to A, the embargo in force (MSM-07-003,
    ADR-0093 point 3); the EM machine does not move for a non-owner.  The
    new row is reported as a participant change.
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
    assert [
        (c.embargo_id, c.consent_before, c.consent_after)
        for c in result.participant_changes
    ] == [(revision_id, None, "ACCEPTED")]
    assert _consents_of(dl, ids["lacking"]) == {
        active_id: "ACCEPTED",
        revision_id: "ACCEPTED",
    }
    assert _is_signatory(dl, case.id_, ids["lacking"])
    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.active_embargo_id == active_id
    assert updated.proposed_embargoes == [revision_id]


@pytest.mark.spec("MSM-07-003")
def test_non_signatory_accepting_a_proposed_revision_waits_for_activation(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """An INVITED participant accepting proposed B holds ACCEPTED(B) at once.

    Accept always marks that embargo's row; there is no advance at accept
    time.  It is not a signatory while A is in force (A has no accepting
    row), and becomes one by lookup when the owner activates B.
    """
    owner, dl = owner_and_dl
    case, ids, _active_id, revision_id = _revision_case(
        dl, owner, revision_days=90
    )
    _seed_consent(dl, ids["invited_with_b"], revision_id, ECS.INVITED)
    invitee_actor = next(
        a
        for a, p in case.actor_participant_index.items()
        if p == ids["invited_with_b"]
    )
    lifecycle = EmbargoLifecycle(persistence=dl)

    accepted = lifecycle.accept_embargo_invite(
        case_id=case.id_, embargo_id=revision_id, actor_id=invitee_actor
    )
    assert [
        (c.consent_before, c.consent_after)
        for c in accepted.participant_changes
    ] == [("INVITED", "ACCEPTED")]
    assert _consents_of(dl, ids["invited_with_b"]) == {revision_id: "ACCEPTED"}
    assert not _is_signatory(dl, case.id_, ids["invited_with_b"])

    lifecycle.accept_embargo_invite(
        case_id=case.id_, embargo_id=revision_id, actor_id=owner.id_
    )
    assert _is_signatory(dl, case.id_, ids["invited_with_b"])


@pytest.mark.spec("MSM-07-004")
def test_owner_rejecting_a_revision_changes_no_participant_record(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """EJ returns EM to ACTIVE under A; no row moves, the owner's included."""
    owner, dl = owner_and_dl
    case, ids, active_id, revision_id = _revision_case(
        dl, owner, revision_days=90
    )
    before = {label: _consents_of(dl, pid) for label, pid in ids.items()}

    result = EmbargoLifecycle(persistence=dl).reject_embargo_invite(
        case_id=case.id_, embargo_id=revision_id, actor_id=owner.id_
    )

    assert result.em_before == EM.REVISE
    assert result.em_after == EM.ACTIVE
    assert result.participant_changes == []
    after = {label: _consents_of(dl, pid) for label, pid in ids.items()}
    assert after == before
    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.active_embargo_id == active_id
    assert updated.proposed_embargoes == []


@pytest.mark.spec("MSM-07-004")
def test_signatory_rejecting_a_proposed_revision_keeps_its_consent_to_the_active_embargo(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Refusing B is not withdrawing from A: row(B) DECLINED, still a signatory."""
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
    assert [
        (c.embargo_id, c.consent_before, c.consent_after)
        for c in result.participant_changes
    ] == [(revision_id, "ACCEPTED", "DECLINED")]
    assert _consents_of(dl, ids["accepted"]) == {
        active_id: "ACCEPTED",
        revision_id: "DECLINED",
    }
    assert _is_signatory(dl, case.id_, ids["accepted"])
    # A participant's Reject is consent, not a decision: B stays open.
    assert cast(VulnerabilityCase, dl.read(case.id_)).proposed_embargoes == [
        revision_id
    ]


@pytest.mark.spec("MSM-07-004")
def test_non_signatory_rejecting_a_proposed_revision_declines(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """ACCEPTED(B) → DECLINED(B): there is no consent to A for the refusal to leave intact."""
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
        (c.consent_before, c.consent_after) for c in result.participant_changes
    ] == [("ACCEPTED", "DECLINED")]
    assert _consents_of(dl, ids["invited_with_b"]) == {revision_id: "DECLINED"}


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
        (c.embargo_id, c.consent_before, c.consent_after)
        for c in result.participant_changes
    ] == [(active_id, "ACCEPTED", "DECLINED")]
    assert _consents_of(dl, ids["lacking"]) == {active_id: "DECLINED"}
    assert not _is_signatory(dl, case.id_, ids["lacking"])


def test_reject_naming_an_unknown_embargo_raises(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Neither active nor proposed on the case: a protocol error, not a consent change."""
    owner, dl = owner_and_dl
    case, ids, _active_id, _revision_id = _revision_case(
        dl, owner, revision_days=90
    )
    stranger = _make_embargo(dl, case.id_, days=10)
    before = _consents_of(dl, ids["owner"])

    with pytest.raises(VultronValidationError, match="neither the active"):
        EmbargoLifecycle(persistence=dl).reject_embargo_invite(
            case_id=case.id_, embargo_id=stranger.id_, actor_id=owner.id_
        )

    assert _consents_of(dl, ids["owner"]) == before
    assert cast(
        VulnerabilityCase, dl.read(case.id_)
    ).current_status.em.state == (EM.REVISE)


# ---------------------------------------------------------------------------
# Tests: a first activation needs no advance (holders of ACCEPTED(B) are
# signatories by lookup); a DECLINED participant holds no consent (#4003)
# ---------------------------------------------------------------------------


@pytest.mark.spec("EP-05-001")
@pytest.mark.spec("MSM-07-005")
def test_owner_accepting_a_first_proposal_makes_its_non_owner_proposer_a_signatory(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A proposer holds ACCEPTED(B) from proposing; no advance is needed.

    ``PROPOSED → ACTIVE`` replaces nothing, so there is no A-vs-B arm and no
    write for the proposer: its ACCEPTED(B) row already makes it a signatory
    once B is the embargo in force, and the content gate (CM-10-004) reads
    the same lookup.  Only the owner's own acceptance is a new row.
    """
    owner, dl = owner_and_dl
    proposer = _make_actor(dl, "Proposer")
    case, (owner_p, proposer_p) = _make_case(
        dl, owner.id_, extra_participant_ids=[proposer.id_], em_state=EM.NONE
    )
    embargo = _make_embargo(dl, case.id_)
    lifecycle = EmbargoLifecycle(persistence=dl)
    lifecycle.propose_embargo(
        case_id=case.id_, embargo_id=embargo.id_, actor_id=proposer.id_
    )
    assert _consents_of(dl, proposer_p.id_) == {embargo.id_: "ACCEPTED"}
    assert not _is_signatory(dl, case.id_, proposer_p.id_)

    result = lifecycle.accept_embargo_invite(
        case_id=case.id_, embargo_id=embargo.id_, actor_id=owner.id_
    )

    assert result.em_after == EM.ACTIVE
    assert [c.participant_id for c in result.participant_changes] == [
        owner_p.id_
    ]
    assert _consents_of(dl, proposer_p.id_) == {embargo.id_: "ACCEPTED"}
    assert _is_signatory(dl, case.id_, owner_p.id_)
    assert _is_signatory(dl, case.id_, proposer_p.id_)


@pytest.mark.spec("EP-05-001")
@pytest.mark.spec("EMB-18-003")
@pytest.mark.parametrize(
    "mode", [TransitionMode.STRICT, TransitionMode.OBSERVED], ids=str
)
def test_owner_accept_with_an_unreadable_previous_embargo_changes_nothing(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    mode: TransitionMode,
) -> None:
    """The A-vs-B read fails closed *before* EM, active_embargo or any consent row moves."""
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_, em_state=EM.REVISE)
    revision = _make_embargo(dl, case.id_, days=90)
    missing = "https://example.org/embargoes/not-replicated"
    case.active_embargo = missing
    case.proposed_embargoes = [revision.id_]
    dl.save(case)
    _seed_consent(dl, owner_p.id_, missing, ECS.ACCEPTED)

    with pytest.raises(VultronNotFoundError):
        EmbargoLifecycle(persistence=dl).accept_embargo_invite(
            case_id=case.id_,
            embargo_id=revision.id_,
            actor_id=owner.id_,
            transition_mode=mode,
        )

    untouched = cast(VulnerabilityCase, dl.read(case.id_))
    assert untouched.current_status.em.state == EM.REVISE
    assert untouched.active_embargo_id == missing
    assert untouched.proposed_embargoes == [revision.id_]
    assert _consents_of(dl, owner_p.id_) == {missing: "ACCEPTED"}


@pytest.mark.spec("MSM-07-004")
def test_withdrawal_from_the_active_embargo_leaves_its_revisions_too(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A signatory holding ACCEPTED on A and B that rejects active A declines both.

    Every open proposal is a revision of the one active embargo (ADR-0113),
    so leaving A is leaving B — otherwise the owner's later activation of B
    would find a withdrawn actor holding ACCEPTED(B), and the content gate
    (CM-10-004) would admit it (#4003).
    """
    owner, dl = owner_and_dl
    signer = _make_actor(dl, "Signer")
    case, (_owner_p, signer_p) = _make_case(
        dl, owner.id_, extra_participant_ids=[signer.id_], em_state=EM.REVISE
    )
    active = _make_embargo(dl, case.id_)
    revision = _make_embargo(dl, case.id_, days=90)
    case.active_embargo = active.id_
    case.proposed_embargoes = [revision.id_]
    dl.save(case)
    _seed_consent(dl, signer_p.id_, active.id_, ECS.ACCEPTED)
    _seed_consent(dl, signer_p.id_, revision.id_, ECS.ACCEPTED)
    lifecycle = EmbargoLifecycle(persistence=dl)

    withdrawn = lifecycle.reject_embargo_invite(
        case_id=case.id_, embargo_id=active.id_, actor_id=signer.id_
    )

    assert withdrawn.em_after == EM.REVISE
    assert _consents_of(dl, signer_p.id_) == {
        active.id_: "DECLINED",
        revision.id_: "DECLINED",
    }

    # The owner activates B: the withdrawn signer holds no accepting row.
    lifecycle.accept_embargo_invite(
        case_id=case.id_, embargo_id=revision.id_, actor_id=owner.id_
    )
    assert _consents_of(dl, signer_p.id_) == {
        active.id_: "DECLINED",
        revision.id_: "DECLINED",
    }
    assert not _is_signatory(dl, case.id_, signer_p.id_)
    assert not _has_lapsed(dl, case.id_, signer_p.id_)


@pytest.mark.spec("MSM-07-003")
@pytest.mark.spec("CM-18-003")
def test_declined_participant_accepting_records_nothing(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """ACCEPT is not legal from DECLINED, so no row changes (#4003)."""
    owner, dl = owner_and_dl
    decliner = _make_actor(dl, "Decliner")
    case, (_owner_p, decliner_p) = _make_case(
        dl, owner.id_, extra_participant_ids=[decliner.id_], em_state=EM.ACTIVE
    )
    active = _make_embargo(dl, case.id_)
    case.active_embargo = active.id_
    dl.save(case)
    _seed_consent(dl, decliner_p.id_, active.id_, ECS.DECLINED)

    result = EmbargoLifecycle(persistence=dl).accept_embargo_invite(
        case_id=case.id_, embargo_id=active.id_, actor_id=decliner.id_
    )

    assert result.participant_changes == []
    assert result.case_changed is False
    assert _consents_of(dl, decliner_p.id_) == {active.id_: "DECLINED"}
    assert not _is_signatory(dl, case.id_, decliner_p.id_)


@pytest.mark.spec("EMB-18-003")
@pytest.mark.parametrize(
    "mode", [TransitionMode.STRICT, TransitionMode.OBSERVED], ids=str
)
@pytest.mark.parametrize(
    "replaces", [False, True], ids=["first-activation", "revision"]
)
def test_owner_accept_of_an_unheld_embargo_writes_nothing(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    mode: TransitionMode,
    replaces: bool,
) -> None:
    """The activated embargo is read first: an unheld one raises, no write."""
    owner, dl = owner_and_dl
    case, owner_p, active_id = _case_awaiting_activation(
        dl, owner.id_, replaces=replaces, activated_id=UNHELD_EMBARGO_ID
    )

    with pytest.raises(VultronNotFoundError) as excinfo:
        EmbargoLifecycle(persistence=dl).accept_embargo_invite(
            case_id=case.id_,
            embargo_id=UNHELD_EMBARGO_ID,
            actor_id=owner.id_,
            transition_mode=mode,
        )

    assert excinfo.value.resource_id == UNHELD_EMBARGO_ID
    _assert_activation_wrote_nothing(
        dl,
        case,
        owner_p,
        active_id=active_id,
        activated_id=UNHELD_EMBARGO_ID,
    )


@pytest.mark.spec("EMB-18-003")
@pytest.mark.parametrize(
    "mode", [TransitionMode.STRICT, TransitionMode.OBSERVED], ids=str
)
@pytest.mark.parametrize(
    "replaces", [False, True], ids=["first-activation", "revision"]
)
def test_owner_accept_of_a_non_embargo_record_writes_nothing(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    mode: TransitionMode,
    replaces: bool,
) -> None:
    """An id that resolves to something other than an EmbargoEvent fails closed."""
    owner, dl = owner_and_dl
    stranger = _make_actor(dl, "not an embargo")
    case, owner_p, active_id = _case_awaiting_activation(
        dl, owner.id_, replaces=replaces, activated_id=stranger.id_
    )

    with pytest.raises(VultronValidationError):
        EmbargoLifecycle(persistence=dl).accept_embargo_invite(
            case_id=case.id_,
            embargo_id=stranger.id_,
            actor_id=owner.id_,
            transition_mode=mode,
        )

    _assert_activation_wrote_nothing(
        dl,
        case,
        owner_p,
        active_id=active_id,
        activated_id=stranger.id_,
    )


@pytest.mark.spec("MSM-07-004")
@pytest.mark.spec("MSM-07-006")
def test_participant_accept_after_the_embargo_exited_records_nothing(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Once EM is EXITED a late Accept binds nothing (ADR-0118)."""
    owner, dl = owner_and_dl
    late = _make_actor(dl, "Late")
    case, (_owner_p, late_p) = _make_case(
        dl, owner.id_, extra_participant_ids=[late.id_], em_state=EM.EXITED
    )
    embargo = _make_embargo(dl, case.id_)

    result = EmbargoLifecycle(persistence=dl).accept_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=late.id_,
        transition_mode=TransitionMode.OBSERVED,
    )

    assert result.participant_changes == []
    assert result.em_after == EM.EXITED
    assert _consents_of(dl, late_p.id_) == {}
