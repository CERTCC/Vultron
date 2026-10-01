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


"""The P/X/A embargo-eligibility guard (#1454) and the EM driver's write contract.

STRICT mode refuses propose/accept/reject-revision once any of P/X/A is set;
OBSERVED mode bypasses the guard; the service always writes em_state even
when em_before is supplied (#2712).  Both live in base.py."""

from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    TransitionMode,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.errors import VultronInvalidStateTransitionError
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.core.models.case_participant import CaseParticipant

from .conftest import (
    _PXA_INELIGIBLE_STATES,
    _make_actor,
    _make_case,
    _make_embargo,
)


@pytest.mark.parametrize("pxa_state", _PXA_INELIGIBLE_STATES)
def test_propose_embargo_strict_raises_when_pxa_set(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    pxa_state: CS_pxa,
) -> None:
    """STRICT propose raises when any of P/X/A is set (EMB-01-002)."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.NONE)
    case.append_case_status(pxa_state=pxa_state)
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
    case.append_case_status(pxa_state=pxa_state)
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
    case.append_case_status(pxa_state=pxa_state)
    dl.save(case)
    embargo = _make_embargo(dl, case.id_)

    # Seed owner to INVITED so the PEC transition would be valid
    owner_p = cast(CaseParticipant, dl.read(participants[0].id_))
    object.__setattr__(owner_p, "embargo_consent_state", PEC.INVITED)
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
    object.__setattr__(owner_p, "embargo_consent_state", PEC.INVITED)
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
    case.append_case_status(pxa_state=pxa_state)
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
    case.append_case_status(pxa_state=pxa_state)
    dl.save(case)
    embargo = _make_embargo(dl, case.id_)

    finder_participant_id = case.actor_participant_index.get(finder.id_)
    assert finder_participant_id is not None
    finder_p = cast(CaseParticipant, dl.read(finder_participant_id))
    object.__setattr__(finder_p, "embargo_consent_state", PEC.INVITED)
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
    case.append_case_status(pxa_state=pxa_state)
    active = _make_embargo(dl, case.id_)
    embargo = _make_embargo(dl, case.id_, days=90)
    case.active_embargo = active.id_
    case.proposed_embargoes = [embargo.id_]
    dl.save(case)

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
    """STRICT reject from PROPOSED+PXA is allowed (PROPOSED→NONE, no active embargo)."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
    case.append_case_status(pxa_state=CS_pxa.Pxa)  # public aware
    embargo = _make_embargo(dl, case.id_)
    case.proposed_embargoes = [embargo.id_]
    dl.save(case)

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
    case.append_case_status(pxa_state=pxa_state)
    active = _make_embargo(dl, case.id_)
    embargo = _make_embargo(dl, case.id_, days=90)
    case.active_embargo = active.id_
    case.proposed_embargoes = [embargo.id_]
    dl.save(case)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.reject_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
        transition_mode=TransitionMode.OBSERVED,
    )

    assert result.em_after == EM.ACTIVE


# ---------------------------------------------------------------------------
# Issue #2712: service always writes em_state (caller_owns_em_io removed)
# ---------------------------------------------------------------------------


class TestServiceAlwaysWritesEmState:
    """Service always writes em_state — caller_owns_em_io pattern retired (#2712)."""

    def test_propose_writes_em_state_when_em_before_supplied(
        self,
        owner_and_dl: tuple[as_Service, SqliteDataLayer],
    ) -> None:
        """propose_embargo always writes em_state even when em_before is supplied."""
        owner, dl = owner_and_dl
        case, _ = _make_case(dl, owner.id_, em_state=EM.NONE)
        embargo = _make_embargo(dl, case.id_)

        lifecycle = EmbargoLifecycle(persistence=dl)
        result = lifecycle.propose_embargo(
            case_id=case.id_,
            embargo_id=embargo.id_,
            actor_id=owner.id_,
            transition_mode=TransitionMode.STRICT,
            em_before=EM.NONE,
        )

        assert result.em_after == EM.PROPOSED
        refreshed = cast(VulnerabilityCase, dl.read(case.id_))
        assert refreshed.current_status.em.state == EM.PROPOSED

    def test_reject_writes_em_state_when_em_before_supplied(
        self,
        owner_and_dl: tuple[as_Service, SqliteDataLayer],
    ) -> None:
        """reject_embargo_invite always writes em_state even when em_before is supplied."""
        owner, dl = owner_and_dl
        case, _ = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
        embargo = _make_embargo(dl, case.id_)
        case.proposed_embargoes = [embargo.id_]
        dl.save(case)

        lifecycle = EmbargoLifecycle(persistence=dl)
        result = lifecycle.reject_embargo_invite(
            case_id=case.id_,
            embargo_id=embargo.id_,
            actor_id=owner.id_,
            transition_mode=TransitionMode.STRICT,
            em_before=EM.PROPOSED,
        )

        assert result.em_after == EM.NONE
        refreshed = cast(VulnerabilityCase, dl.read(case.id_))
        assert refreshed.current_status.em.state == EM.NONE

    def test_terminate_writes_em_state_when_em_before_supplied(
        self,
        owner_and_dl: tuple[as_Service, SqliteDataLayer],
    ) -> None:
        """terminate_active_embargo always writes em_state even when em_before is supplied."""
        owner, dl = owner_and_dl
        case, _ = _make_case(dl, owner.id_, em_state=EM.ACTIVE)
        embargo = _make_embargo(dl, case.id_)
        case.active_embargo = embargo.id_
        dl.save(case)

        lifecycle = EmbargoLifecycle(persistence=dl)
        result = lifecycle.terminate_active_embargo(
            case_id=case.id_,
            actor_id=owner.id_,
            transition_mode=TransitionMode.STRICT,
            em_before=EM.ACTIVE,
        )

        assert result.em_after == EM.EXITED
        refreshed = cast(VulnerabilityCase, dl.read(case.id_))
        assert refreshed.current_status.em.state == EM.EXITED
