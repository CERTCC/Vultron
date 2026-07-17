"""Boundary tests for EmbargoLifecycle operations.

These tests exercise the service through a real in-memory SqliteDataLayer so
that persistence invariants are validated without mocking internals.

Coverage required by #746 AC-5 (propose_embargo STRICT) and #747 AC-1 to AC-7:
  - propose_embargo STRICT (original) and OBSERVED mode
  - accept_embargo_invite STRICT and OBSERVED, owner vs. non-owner
  - reject_embargo_invite STRICT and OBSERVED, owner vs. non-owner
  - terminate_active_embargo STRICT and OBSERVED, PEC cascade
  - record_participant_consent for ACCEPT, DECLINE, INVITE, RESET triggers

Coverage added by #1454 (AC-1 to AC-3): P/X/A embargo-eligibility guards
  - propose_embargo STRICT raises when pxa_state != pxa (all P/X/A variants)
  - propose_embargo OBSERVED bypasses guard
  - accept_embargo_invite STRICT raises when pxa_state != pxa
  - accept_embargo_invite OBSERVED bypasses guard
"""

from collections.abc import Generator
from typing import cast

import pytest

# noqa: F401 — imported for vocabulary registration side-effect
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    EmbargoLifecycleResult,
    TransitionMode,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC, PEC_Trigger
from vultron.enums.roles import CVDRole
from vultron.errors import VultronInvalidStateTransitionError
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.core.use_cases._helpers import _as_id
from vultron.core.models.case_participant import (
    CaseParticipant,
    FinderParticipant,
    VendorParticipant,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_actor(dl: SqliteDataLayer, name: str) -> as_Service:
    actor = as_Service(name=name)
    dl.create(actor)
    return actor


def _make_case(
    dl: SqliteDataLayer,
    owner_id: str,
    extra_participant_ids: list[str] | None = None,
    em_state: EM = EM.NONE,
) -> tuple[as_VulnerabilityCase, list[CaseParticipant]]:
    """Create a as_VulnerabilityCase with an owner participant.

    Returns the case and the list of CaseParticipant objects created.
    """
    case = as_VulnerabilityCase(
        name="Test embargo case",
        attributed_to=owner_id,
    )
    case.current_status.em_state = em_state

    owner_participant = VendorParticipant(
        attributed_to=owner_id,
        context=case.id_,
        embargo_consent_state=PEC.NO_EMBARGO,
    )
    owner_participant.add_role(CVDRole.CASE_MANAGER)

    participants: list[CaseParticipant] = [owner_participant]
    case.case_participants = [owner_participant.id_]
    case.actor_participant_index = {owner_id: owner_participant.id_}

    for pid in extra_participant_ids or []:
        p = FinderParticipant(
            attributed_to=pid,
            context=case.id_,
            embargo_consent_state=PEC.NO_EMBARGO,
        )
        case.case_participants.append(p.id_)
        case.actor_participant_index[pid] = p.id_
        participants.append(p)

    dl.create(case)
    for participant in participants:
        dl.create(participant)

    return case, participants


def _make_embargo(dl: SqliteDataLayer, case_id: str) -> as_EmbargoEvent:
    embargo = as_EmbargoEvent(context=case_id)
    dl.create(embargo)
    return embargo


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def owner_and_dl() -> (
    Generator[tuple[as_Service, SqliteDataLayer], None, None]
):
    owner = as_Service(name="Owner Org")
    reset_datalayer(owner.id_)
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=owner.id_)
    dl.clear_all()
    dl.create(owner)
    try:
        yield owner, dl
    finally:
        dl.close()
        reset_datalayer(owner.id_)


# ---------------------------------------------------------------------------
# Tests: valid transitions
# ---------------------------------------------------------------------------


def test_propose_embargo_none_to_proposed(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """propose_embargo from NO_EMBARGO transitions case to PROPOSED."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.NONE)
    embargo = _make_embargo(dl, case.id_)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.propose_embargo(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
    )

    assert isinstance(result, EmbargoLifecycleResult)
    assert result.em_before == EM.NONE
    assert result.em_after == EM.PROPOSED
    assert result.case_changed is True
    assert result.case_embargo_changed is False
    assert result.pec_reset is False
    assert result.participant_changes == []

    updated = cast(as_VulnerabilityCase, dl.read(case.id_))
    assert updated.current_status.em_state == EM.PROPOSED
    assert embargo.id_ in updated.proposed_embargoes


def test_propose_embargo_idempotent_repropse(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """propose_embargo from PROPOSED → PROPOSED is valid (counter-proposal).

    Calling with the same embargo_id twice must not duplicate the entry in
    proposed_embargoes.
    """
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
    embargo = _make_embargo(dl, case.id_)

    # Seed the case as already having this embargo proposed
    case.proposed_embargoes.append(embargo.id_)
    dl.save(case)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.propose_embargo(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
    )

    assert result.em_before == EM.PROPOSED
    assert result.em_after == EM.PROPOSED
    # EM state did not change, embargo_id already present → nothing mutated
    assert result.case_changed is False

    updated = cast(as_VulnerabilityCase, dl.read(case.id_))
    # Must not have been duplicated
    assert updated.proposed_embargoes.count(embargo.id_) == 1


def test_propose_embargo_active_to_revise_cascades_pec(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """propose_embargo from ACTIVE transitions to REVISE and cascades PEC.

    Participants in SIGNATORY state must be transitioned to LAPSED.
    """
    owner, dl = owner_and_dl
    finder = _make_actor(dl, "Finder Org")
    case, participants = _make_case(
        dl, owner.id_, extra_participant_ids=[finder.id_], em_state=EM.ACTIVE
    )
    # Set both participants to SIGNATORY (active embargo consent)
    for p in participants:
        p.embargo_consent_state = PEC.SIGNATORY
        dl.save(p)

    embargo = _make_embargo(dl, case.id_)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.propose_embargo(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
    )

    assert result.em_before == EM.ACTIVE
    assert result.em_after == EM.REVISE
    assert result.case_changed is True
    assert len(result.participant_changes) == 2  # both signatories lapsed
    for change in result.participant_changes:
        assert change.pec_before == PEC.SIGNATORY.value
        assert change.pec_after == PEC.LAPSED.value

    # DataLayer state matches
    updated = cast(as_VulnerabilityCase, dl.read(case.id_))
    assert updated.current_status.em_state == EM.REVISE
    for p in participants:
        updated_p = cast(CaseParticipant, dl.read(p.id_))
        assert updated_p.embargo_consent_state == PEC.LAPSED.value


def test_propose_embargo_revise_to_revise_no_pec_cascade(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """propose_embargo from REVISE → REVISE does not cascade PEC."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.REVISE)
    embargo = _make_embargo(dl, case.id_)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.propose_embargo(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
    )

    assert result.em_before == EM.REVISE
    assert result.em_after == EM.REVISE
    assert result.participant_changes == []


# ---------------------------------------------------------------------------
# Tests: invalid transitions
# ---------------------------------------------------------------------------


def test_propose_embargo_invalid_state_raises(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """propose_embargo from EXITED raises VultronInvalidStateTransitionError."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.EXITED)
    embargo = _make_embargo(dl, case.id_)

    lifecycle = EmbargoLifecycle(persistence=dl)
    with pytest.raises(VultronInvalidStateTransitionError):
        lifecycle.propose_embargo(
            case_id=case.id_,
            embargo_id=embargo.id_,
            actor_id=owner.id_,
        )


def test_propose_embargo_observed_mode_syncs_invalid_state(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """OBSERVED mode on an invalid start state force-syncs to PROPOSED (no raise)."""
    owner, dl = owner_and_dl
    # EXITED cannot normally transition to PROPOSED; OBSERVED syncs anyway
    case, _ = _make_case(dl, owner.id_, em_state=EM.EXITED)
    embargo = _make_embargo(dl, case.id_)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.propose_embargo(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
        transition_mode=TransitionMode.OBSERVED,
    )

    # Must not raise; OBSERVED falls back to PROPOSED
    assert result.em_after == EM.PROPOSED


# ---------------------------------------------------------------------------
# Tests: owner vs. non-owner
# ---------------------------------------------------------------------------


def test_propose_embargo_owner_succeeds(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """The case owner can propose an embargo."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.NONE)
    embargo = _make_embargo(dl, case.id_)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.propose_embargo(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
    )

    assert result.em_after == EM.PROPOSED


def test_propose_embargo_non_owner_succeeds(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A non-owner participant can also propose an embargo (no ownership gate).

    The EmbargoLifecycle service enforces EM state validity but does not
    restrict who may propose.  Ownership gates on outbound activity sending
    are the caller's responsibility.
    """
    owner, dl = owner_and_dl
    finder = _make_actor(dl, "Finder Org")
    case, _ = _make_case(
        dl, owner.id_, extra_participant_ids=[finder.id_], em_state=EM.NONE
    )
    embargo = _make_embargo(dl, case.id_)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.propose_embargo(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=finder.id_,  # non-owner
    )

    assert result.em_after == EM.PROPOSED


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
    owner_p.embargo_consent_state = PEC.INVITED
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
    finder_p.embargo_consent_state = PEC.INVITED
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
    refreshed_case = cast(as_VulnerabilityCase, dl.read(case.id_))
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
    owner_p.embargo_consent_state = PEC.INVITED
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
    """Owner rejects from PROPOSED: EM → NO_EMBARGO, PEC updated."""
    owner, dl = owner_and_dl
    case, participants = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
    owner_participant_id = participants[0].id_
    embargo = _make_embargo(dl, case.id_)

    # Seed owner to INVITED so DECLINE transition is valid
    owner_p = cast(CaseParticipant, dl.read(owner_participant_id))
    owner_p.embargo_consent_state = PEC.INVITED
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


def test_reject_embargo_invite_owner_revise_stays_active(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Owner rejects from REVISE: EM → ACTIVE (not terminated)."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.REVISE)
    embargo = _make_embargo(dl, case.id_)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.reject_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
    )

    assert result.em_before == EM.REVISE
    assert result.em_after == EM.ACTIVE


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

    # Seed finder to INVITED so DECLINE transition is valid
    finder_participant_id = case.actor_participant_index.get(finder.id_)
    assert finder_participant_id is not None
    finder_p = cast(CaseParticipant, dl.read(finder_participant_id))
    finder_p.embargo_consent_state = PEC.INVITED
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


def test_reject_embargo_invite_strict_invalid_state_raises(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Reject from invalid EM state (NO_EMBARGO) raises in STRICT mode."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.NONE)
    embargo = _make_embargo(dl, case.id_)

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

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.reject_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
        transition_mode=TransitionMode.OBSERVED,
    )

    assert result.em_after == EM.NONE


# ---------------------------------------------------------------------------
# Tests: terminate_active_embargo
# ---------------------------------------------------------------------------


def test_terminate_active_embargo_strict_active_to_exited(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Terminate from ACTIVE: EM → EXITED, PEC of all participants reset."""
    owner, dl = owner_and_dl
    finder = _make_actor(dl, "Finder Org")
    case, participants = _make_case(
        dl,
        owner.id_,
        extra_participant_ids=[finder.id_],
        em_state=EM.ACTIVE,
    )
    owner_participant_id = participants[0].id_
    embargo = _make_embargo(dl, case.id_)
    case.active_embargo = embargo.id_
    dl.save(case)

    # Set owner PEC to SIGNATORY to verify it gets reset
    owner_participant = cast(CaseParticipant, dl.read(owner_participant_id))
    owner_participant.embargo_consent_state = PEC.SIGNATORY
    dl.save(owner_participant)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.terminate_active_embargo(
        case_id=case.id_,
        actor_id=owner.id_,
    )

    assert result.em_before == EM.ACTIVE
    assert result.em_after == EM.EXITED
    assert result.pec_reset is True

    refreshed_owner_participant = cast(
        CaseParticipant, dl.read(owner_participant_id)
    )
    assert (
        refreshed_owner_participant.embargo_consent_state
        == PEC.NO_EMBARGO.value
    )


def test_terminate_active_embargo_strict_revise_to_exited(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Terminate from REVISE: EM → EXITED."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.REVISE)
    embargo = _make_embargo(dl, case.id_)
    case.active_embargo = embargo.id_
    dl.save(case)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.terminate_active_embargo(
        case_id=case.id_,
        actor_id=owner.id_,
    )

    assert result.em_after == EM.EXITED


def test_terminate_active_embargo_strict_no_active_embargo_raises(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """STRICT terminate with no active_embargo raises VultronInvalidStateTransitionError."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.ACTIVE)
    # active_embargo deliberately not set on the case

    lifecycle = EmbargoLifecycle(persistence=dl)
    with pytest.raises(VultronInvalidStateTransitionError):
        lifecycle.terminate_active_embargo(
            case_id=case.id_,
            actor_id=owner.id_,
        )


def test_terminate_active_embargo_strict_invalid_em_state_raises(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """STRICT terminate from PROPOSED (not ACTIVE/REVISE) raises."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
    embargo = _make_embargo(dl, case.id_)
    case.active_embargo = embargo.id_
    dl.save(case)

    lifecycle = EmbargoLifecycle(persistence=dl)
    with pytest.raises(VultronInvalidStateTransitionError):
        lifecycle.terminate_active_embargo(
            case_id=case.id_,
            actor_id=owner.id_,
        )


def test_terminate_active_embargo_observed_invalid_no_raise(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """OBSERVED mode: invalid EM state syncs to EXITED without raising."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
    embargo = _make_embargo(dl, case.id_)
    case.active_embargo = embargo.id_
    dl.save(case)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.terminate_active_embargo(
        case_id=case.id_,
        actor_id=owner.id_,
        transition_mode=TransitionMode.OBSERVED,
    )

    assert result.em_after == EM.EXITED


# ---------------------------------------------------------------------------
# Tests: record_participant_consent
# ---------------------------------------------------------------------------


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
    owner_p.embargo_consent_state = PEC.INVITED
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
    owner_p.embargo_consent_state = PEC.LAPSED
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


# ---------------------------------------------------------------------------
# Tests: P/X/A embargo-eligibility guards (#1454)
# ---------------------------------------------------------------------------

# All non-pxa CS_pxa states trigger the guard.
_PXA_INELIGIBLE_STATES = [
    CS_pxa.Pxa,  # public aware
    CS_pxa.pXa,  # exploit published
    CS_pxa.pxA,  # attacks observed
    CS_pxa.PXa,  # public + exploit
    CS_pxa.PxA,  # public + attacks
    CS_pxa.pXA,  # exploit + attacks
    CS_pxa.PXA,  # all three set
]


@pytest.mark.parametrize("pxa_state", _PXA_INELIGIBLE_STATES)
def test_propose_embargo_strict_raises_when_pxa_set(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    pxa_state: CS_pxa,
) -> None:
    """STRICT propose raises when any of P/X/A is set (EMB-01-002)."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.NONE)
    case.current_status.pxa_state = pxa_state
    dl.save(case)
    embargo = _make_embargo(dl, case.id_)

    lifecycle = EmbargoLifecycle(persistence=dl)
    with pytest.raises(VultronInvalidStateTransitionError):
        lifecycle.propose_embargo(
            case_id=case.id_,
            embargo_id=embargo.id_,
            actor_id=owner.id_,
        )


def test_propose_embargo_strict_allowed_when_pxa_clear(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """STRICT propose succeeds when pxa_state is fully clear (pxa)."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.NONE)
    # pxa_state defaults to CS_pxa.pxa — no mutation needed
    embargo = _make_embargo(dl, case.id_)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.propose_embargo(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
    )

    assert result.em_after == EM.PROPOSED


@pytest.mark.parametrize("pxa_state", _PXA_INELIGIBLE_STATES)
def test_propose_embargo_observed_bypasses_pxa_guard(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    pxa_state: CS_pxa,
) -> None:
    """OBSERVED mode bypasses P/X/A guard and syncs to PROPOSED."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.NONE)
    case.current_status.pxa_state = pxa_state
    dl.save(case)
    embargo = _make_embargo(dl, case.id_)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.propose_embargo(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
        transition_mode=TransitionMode.OBSERVED,
    )

    assert result.em_after == EM.PROPOSED


@pytest.mark.parametrize("pxa_state", _PXA_INELIGIBLE_STATES)
def test_accept_embargo_invite_strict_raises_when_pxa_set(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    pxa_state: CS_pxa,
) -> None:
    """STRICT accept raises when any of P/X/A is set (EMB-02-002)."""
    owner, dl = owner_and_dl
    case, participants = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
    case.current_status.pxa_state = pxa_state
    dl.save(case)
    embargo = _make_embargo(dl, case.id_)

    # Seed owner to INVITED so the PEC transition would be valid
    owner_p = cast(CaseParticipant, dl.read(participants[0].id_))
    owner_p.embargo_consent_state = PEC.INVITED
    dl.save(owner_p)

    lifecycle = EmbargoLifecycle(persistence=dl)
    with pytest.raises(VultronInvalidStateTransitionError):
        lifecycle.accept_embargo_invite(
            case_id=case.id_,
            embargo_id=embargo.id_,
            actor_id=owner.id_,
        )


def test_accept_embargo_invite_strict_allowed_when_pxa_clear(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """STRICT accept succeeds when pxa_state is fully clear (pxa)."""
    owner, dl = owner_and_dl
    case, participants = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
    embargo = _make_embargo(dl, case.id_)

    owner_p = cast(CaseParticipant, dl.read(participants[0].id_))
    owner_p.embargo_consent_state = PEC.INVITED
    dl.save(owner_p)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.accept_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
    )

    assert result.em_after == EM.ACTIVE


@pytest.mark.parametrize("pxa_state", _PXA_INELIGIBLE_STATES)
def test_accept_embargo_invite_observed_bypasses_pxa_guard(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    pxa_state: CS_pxa,
) -> None:
    """OBSERVED mode bypasses P/X/A guard and syncs to ACTIVE."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
    case.current_status.pxa_state = pxa_state
    dl.save(case)
    embargo = _make_embargo(dl, case.id_)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.accept_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
        transition_mode=TransitionMode.OBSERVED,
    )

    assert result.em_after == EM.ACTIVE


@pytest.mark.parametrize("pxa_state", _PXA_INELIGIBLE_STATES)
def test_accept_embargo_invite_strict_non_owner_pxa_set_does_not_raise(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    pxa_state: CS_pxa,
) -> None:
    """Non-owner STRICT accept with P/X/A set still records PEC (no guard)."""
    owner, dl = owner_and_dl
    finder = _make_actor(dl, "Finder Org")
    case, _ = _make_case(
        dl, owner.id_, extra_participant_ids=[finder.id_], em_state=EM.PROPOSED
    )
    case.current_status.pxa_state = pxa_state
    dl.save(case)
    embargo = _make_embargo(dl, case.id_)

    finder_participant_id = case.actor_participant_index.get(finder.id_)
    assert finder_participant_id is not None
    finder_p = cast(CaseParticipant, dl.read(finder_participant_id))
    finder_p.embargo_consent_state = PEC.INVITED
    dl.save(finder_p)

    lifecycle = EmbargoLifecycle(persistence=dl)
    # Non-owner: does NOT drive EM state, guard must NOT raise (EMB-02-002)
    result = lifecycle.accept_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=finder.id_,
    )

    assert result.em_after == EM.PROPOSED  # EM unchanged
    refreshed = cast(CaseParticipant, dl.read(finder_participant_id))
    assert refreshed.embargo_consent_state == PEC.SIGNATORY.value


# ---------------------------------------------------------------------------
# Tests: reject_embargo_invite P/X/A guard (EMB-04-002)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pxa_state", _PXA_INELIGIBLE_STATES)
def test_reject_embargo_invite_strict_revise_pxa_raises(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    pxa_state: CS_pxa,
) -> None:
    """STRICT reject from REVISE+PXA raises (EMB-04-002: must terminate, not revert)."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.REVISE)
    case.current_status.pxa_state = pxa_state
    dl.save(case)
    embargo = _make_embargo(dl, case.id_)

    lifecycle = EmbargoLifecycle(persistence=dl)
    with pytest.raises(VultronInvalidStateTransitionError):
        lifecycle.reject_embargo_invite(
            case_id=case.id_,
            embargo_id=embargo.id_,
            actor_id=owner.id_,
        )


def test_reject_embargo_invite_strict_proposed_pxa_allowed(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """STRICT reject from PROPOSED+PXA is allowed (PROPOSED→NO_EMBARGO, no active embargo)."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
    case.current_status.pxa_state = CS_pxa.Pxa  # public aware
    dl.save(case)
    embargo = _make_embargo(dl, case.id_)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.reject_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
    )

    assert result.em_after == EM.NONE


@pytest.mark.parametrize("pxa_state", _PXA_INELIGIBLE_STATES)
def test_reject_embargo_invite_observed_revise_pxa_bypasses_guard(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    pxa_state: CS_pxa,
) -> None:
    """OBSERVED reject from REVISE+PXA bypasses the guard (state-sync)."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.REVISE)
    case.current_status.pxa_state = pxa_state
    dl.save(case)
    embargo = _make_embargo(dl, case.id_)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.reject_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
        transition_mode=TransitionMode.OBSERVED,
    )

    assert result.em_after == EM.ACTIVE
