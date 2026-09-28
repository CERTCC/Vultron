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


"""propose_embargo, accept_embargo_invite and reject_embargo_invite.

Covers valid and invalid EM transitions in STRICT and OBSERVED mode, owner
versus non-owner behaviour, idempotency, and the PEC side effects each
operation applies (proposals.py, pec.py)."""

from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    EmbargoLifecycleResult,
    TransitionMode,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC, PEC_Trigger
from vultron.errors import VultronInvalidStateTransitionError
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_participant import CaseParticipant

from .conftest import (
    _make_actor,
    _make_case,
    _make_embargo,
)


def test_propose_embargo_none_to_proposed(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """propose_embargo from NONE transitions case to PROPOSED."""
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
    assert updated.current_status.em.state == EM.PROPOSED
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
        object.__setattr__(p, "embargo_consent_state", PEC.SIGNATORY)
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
    assert updated.current_status.em.state == EM.REVISE
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
    """Owner rejects from PROPOSED: EM → NONE, PEC updated."""
    owner, dl = owner_and_dl
    case, participants = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
    owner_participant_id = participants[0].id_
    embargo = _make_embargo(dl, case.id_)

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


def test_reject_embargo_invite_signatory_from_proposed(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """SIGNATORY actor rejecting a PROPOSED embargo succeeds and moves to DECLINED.

    ADR-0093: SIGNATORY → DECLINED is a first-class PEC transition.  Before
    this ADR, the node raised VultronInvalidStateTransitionError (returned
    FAILURE); after, it returns SUCCESS and the PEC state is DECLINED.
    """
    owner, dl = owner_and_dl
    case, participants = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
    owner_participant_id = participants[0].id_
    embargo = _make_embargo(dl, case.id_)

    # Seed owner to SIGNATORY (active consent on a prior version)
    owner_p = cast(CaseParticipant, dl.read(owner_participant_id))
    owner_p.apply_pec_transition(PEC_Trigger.ACCEPT)
    dl.save(owner_p)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.reject_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
    )

    assert result.em_before == EM.PROPOSED
    assert result.em_after == EM.NONE

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


def test_reject_embargo_invite_signatory_non_owner_transitions_to_declined(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """SIGNATORY non-owner explicitly withdrawing consent → DECLINED (ADR-0093)."""
    owner, dl = owner_and_dl
    finder = _make_actor(dl, "Finder Org")
    case, _ = _make_case(
        dl,
        owner.id_,
        extra_participant_ids=[finder.id_],
        em_state=EM.ACTIVE,
    )
    embargo = _make_embargo(dl, case.id_)

    # Seed finder to SIGNATORY via proper FSM path (UNBOUND → SIGNATORY).
    finder_participant_id = case.actor_participant_index.get(finder.id_)
    assert finder_participant_id is not None
    finder_p = cast(CaseParticipant, dl.read(finder_participant_id))
    finder_p.apply_pec_transition(PEC_Trigger.ACCEPT)
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
