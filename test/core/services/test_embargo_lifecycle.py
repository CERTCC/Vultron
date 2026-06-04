"""Boundary tests for EmbargoLifecycle.propose_embargo (STRICT mode).

These tests exercise the service through a real in-memory SqliteDataLayer so
that persistence invariants are validated without mocking internals.

Coverage required by #746 AC-5:
  - valid transition (NO_EMBARGO → PROPOSED)
  - invalid transition raises VultronInvalidStateTransitionError
  - idempotent re-propose (PROPOSED → PROPOSED)
  - owner vs. non-owner actors (propose is not ownership-gated)
  - ACTIVE → REVISE cascade (PEC signatory → lapsed)
"""

from collections.abc import Generator
from typing import cast

import pytest

# noqa: F401 — imported for vocabulary registration side-effect
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    VulnerabilityCase,
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
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.states.roles import CVDRole
from vultron.errors import VultronInvalidStateTransitionError
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import (
    CaseParticipant,
    FinderParticipant,
    VendorParticipant,
)
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent

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
) -> tuple[VulnerabilityCase, list[CaseParticipant]]:
    """Create a VulnerabilityCase with an owner participant.

    Returns the case and the list of CaseParticipant objects created.
    """
    case = VulnerabilityCase(
        name="Test embargo case",
        attributed_to=owner_id,
    )
    case.current_status.em_state = em_state

    owner_participant = VendorParticipant(
        attributed_to=owner_id,
        context=case.id_,
        embargo_consent_state=PEC.NO_EMBARGO.value,
    )
    owner_participant.add_role(CVDRole.CASE_MANAGER)

    participants: list[CaseParticipant] = [owner_participant]
    case.case_participants = [owner_participant.id_]
    case.actor_participant_index = {owner_id: owner_participant.id_}

    for pid in extra_participant_ids or []:
        p = FinderParticipant(
            attributed_to=pid,
            context=case.id_,
            embargo_consent_state=PEC.NO_EMBARGO.value,
        )
        case.case_participants.append(p.id_)
        case.actor_participant_index[pid] = p.id_
        participants.append(p)

    dl.create(case)
    for participant in participants:
        dl.create(participant)

    return case, participants


def _make_embargo(dl: SqliteDataLayer, case_id: str) -> EmbargoEvent:
    embargo = EmbargoEvent(context=case_id)
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

    updated = cast(VulnerabilityCase, dl.read(case.id_))
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

    updated = cast(VulnerabilityCase, dl.read(case.id_))
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
        p.embargo_consent_state = PEC.SIGNATORY.value
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
    updated = cast(VulnerabilityCase, dl.read(case.id_))
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


def test_propose_embargo_observed_mode_raises_not_implemented(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """OBSERVED mode is not yet implemented and must raise NotImplementedError."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.NONE)
    embargo = _make_embargo(dl, case.id_)

    lifecycle = EmbargoLifecycle(persistence=dl)
    with pytest.raises(NotImplementedError):
        lifecycle.propose_embargo(
            case_id=case.id_,
            embargo_id=embargo.id_,
            actor_id=owner.id_,
            transition_mode=TransitionMode.OBSERVED,
        )


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
