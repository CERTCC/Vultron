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

STRICT mode refuses propose, the case owner's activation and its
rejection of a revision once any of P/X/A is set;
OBSERVED mode bypasses the guard; the service always stores the case whose
register step it applied, so the stored EM is the derived one (#2712,
ADR-0122).  Both live in base.py."""

from typing import cast

import pytest

from test.support.embargo_register import (
    activate,
    propose,
    write_consent_rows,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    TransitionMode,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import TerminationReason
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState as ECS,
)
from vultron.errors import VultronInvalidStateTransitionError
from vultron.wire.as2.vocab.base.objects.actors import as_Service

from .conftest import (
    _PXA_INELIGIBLE_STATES,
    _consent_of,
    _make_actor,
    _make_case,
    _make_embargo,
    _seed_consent,
)


@pytest.mark.parametrize("pxa_state", _PXA_INELIGIBLE_STATES)
def test_propose_embargo_strict_raises_when_pxa_set(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    pxa_state: CS_pxa,
) -> None:
    """STRICT propose raises when any of P/X/A is set (EMB-01-002)."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)
    case.append_case_status(pxa_state=pxa_state)
    dl.save(case)
    write_consent_rows(dl, case)
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
    case, _ = _make_case(dl, owner.id_)
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
    case, _ = _make_case(dl, owner.id_)
    case.append_case_status(pxa_state=pxa_state)
    dl.save(case)
    write_consent_rows(dl, case)
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
def test_activate_embargo_strict_raises_when_pxa_set(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    pxa_state: CS_pxa,
) -> None:
    """STRICT activation raises when any of P/X/A is set (EMB-02-002)."""
    owner, dl = owner_and_dl
    case, participants = _make_case(dl, owner.id_)
    case.append_case_status(pxa_state=pxa_state)
    embargo = _make_embargo(dl, case.id_)
    propose(case, embargo.id_)
    dl.save(case)
    write_consent_rows(dl, case)

    # Seed owner's row to INVITED so the consent transition would be valid
    _seed_consent(dl, participants[0].id_, embargo.id_, ECS.INVITED)

    lifecycle = EmbargoLifecycle(persistence=dl)
    with pytest.raises(VultronInvalidStateTransitionError):
        lifecycle.activate_embargo(
            case_id=case.id_,
            embargo_id=embargo.id_,
            actor_id=owner.id_,
        )


def test_activate_embargo_strict_allowed_when_pxa_clear(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """STRICT activation succeeds when pxa_state is fully clear (pxa)."""
    owner, dl = owner_and_dl
    case, participants = _make_case(dl, owner.id_)
    embargo = _make_embargo(dl, case.id_)
    propose(case, embargo.id_)
    dl.save(case)
    write_consent_rows(dl, case)

    _seed_consent(dl, participants[0].id_, embargo.id_, ECS.INVITED)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.activate_embargo(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
    )

    assert result.em_after == EM.ACTIVE


@pytest.mark.parametrize("pxa_state", _PXA_INELIGIBLE_STATES)
def test_activate_embargo_observed_bypasses_pxa_guard(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    pxa_state: CS_pxa,
) -> None:
    """OBSERVED mode bypasses P/X/A guard and syncs to ACTIVE."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)
    case.append_case_status(pxa_state=pxa_state)
    embargo = _make_embargo(dl, case.id_)
    propose(case, embargo.id_)
    dl.save(case)
    write_consent_rows(dl, case)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.activate_embargo(
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
    """Non-owner STRICT accept with P/X/A set still records consent (no guard)."""
    owner, dl = owner_and_dl
    finder = _make_actor(dl, "Finder Org")
    case, _ = _make_case(dl, owner.id_, extra_participant_ids=[finder.id_])
    case.append_case_status(pxa_state=pxa_state)
    embargo = _make_embargo(dl, case.id_)
    propose(case, embargo.id_)
    dl.save(case)
    write_consent_rows(dl, case)

    finder_participant_id = case.actor_participant_index.get(finder.id_)
    assert finder_participant_id is not None
    _seed_consent(dl, finder_participant_id, embargo.id_, ECS.INVITED)

    lifecycle = EmbargoLifecycle(persistence=dl)
    # An Accept(Invite) drives no EM state, so the guard must NOT raise
    result = lifecycle.accept_embargo_invite(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=finder.id_,
    )

    assert result.em_after == EM.PROPOSED  # EM unchanged
    assert _consent_of(dl, finder_participant_id, embargo.id_) == "AGREED"


@pytest.mark.parametrize("pxa_state", _PXA_INELIGIBLE_STATES)
def test_owners_accept_of_an_invite_with_pxa_set_is_consent_only(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    pxa_state: CS_pxa,
) -> None:
    """The owner's Accept(Invite) moves no EM state, so P/X/A refuses nothing.

    Activation is the owner's separate decision (ADR-0122); its Accept of the
    Invite records its row and leaves the proposal open.
    """
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    case.append_case_status(pxa_state=pxa_state)
    embargo = _make_embargo(dl, case.id_)
    propose(case, embargo.id_)
    dl.save(case)
    _seed_consent(dl, owner_p.id_, embargo.id_, ECS.INVITED)

    result = EmbargoLifecycle(persistence=dl).accept_embargo_invite(
        case_id=case.id_, embargo_id=embargo.id_, actor_id=owner.id_
    )

    assert result.em_after == EM.PROPOSED
    assert _consent_of(dl, owner_p.id_, embargo.id_) == "AGREED"


# ---------------------------------------------------------------------------
# Tests: reject_embargo_proposal P/X/A guard (EMB-04-002)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pxa_state", _PXA_INELIGIBLE_STATES)
def test_reject_embargo_proposal_strict_revise_pxa_raises(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    pxa_state: CS_pxa,
) -> None:
    """STRICT reject from REVISE+PXA raises (EMB-04-002: must terminate, not revert)."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)
    case.append_case_status(pxa_state=pxa_state)
    active = _make_embargo(dl, case.id_)
    embargo = _make_embargo(dl, case.id_, days=90)
    activate(case, active.id_)
    propose(case, embargo.id_)
    dl.save(case)
    write_consent_rows(dl, case)

    lifecycle = EmbargoLifecycle(persistence=dl)
    with pytest.raises(VultronInvalidStateTransitionError):
        lifecycle.reject_embargo_proposal(
            case_id=case.id_,
            embargo_id=embargo.id_,
            actor_id=owner.id_,
        )


def test_reject_embargo_proposal_strict_proposed_pxa_allowed(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """STRICT reject from PROPOSED+PXA is allowed (PROPOSED→NONE, no active embargo)."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)
    case.append_case_status(pxa_state=CS_pxa.Pxa)  # public aware
    embargo = _make_embargo(dl, case.id_)
    propose(case, embargo.id_)
    dl.save(case)
    write_consent_rows(dl, case)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.reject_embargo_proposal(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
    )

    assert result.em_after == EM.NONE


@pytest.mark.parametrize("pxa_state", _PXA_INELIGIBLE_STATES)
def test_reject_embargo_proposal_observed_revise_pxa_bypasses_guard(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    pxa_state: CS_pxa,
) -> None:
    """OBSERVED reject from REVISE+PXA bypasses the guard (state-sync)."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)
    case.append_case_status(pxa_state=pxa_state)
    active = _make_embargo(dl, case.id_)
    embargo = _make_embargo(dl, case.id_, days=90)
    activate(case, active.id_)
    propose(case, embargo.id_)
    dl.save(case)
    write_consent_rows(dl, case)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.reject_embargo_proposal(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
        transition_mode=TransitionMode.OBSERVED,
    )

    assert result.em_after == EM.ACTIVE


# ---------------------------------------------------------------------------
# Issue #2712: the service always stores the case it changed (caller_owns_em_io
# removed); EM is derived from the stored register (ADR-0122)
# ---------------------------------------------------------------------------


class TestServiceAlwaysWritesEmState:
    """Service always stores the stepped register — caller_owns_em_io retired (#2712)."""

    def test_propose_writes_em_state(
        self,
        owner_and_dl: tuple[as_Service, SqliteDataLayer],
    ) -> None:
        """propose_embargo stores the case, so the stored EM is PROPOSED."""
        owner, dl = owner_and_dl
        case, _ = _make_case(dl, owner.id_)
        embargo = _make_embargo(dl, case.id_)

        lifecycle = EmbargoLifecycle(persistence=dl)
        result = lifecycle.propose_embargo(
            case_id=case.id_,
            embargo_id=embargo.id_,
            actor_id=owner.id_,
            transition_mode=TransitionMode.STRICT,
        )

        assert result.em_after == EM.PROPOSED
        refreshed = cast(VulnerabilityCase, dl.read(case.id_))
        assert refreshed.em_state == EM.PROPOSED
        assert refreshed.current_status.em.state == EM.PROPOSED

    def test_reject_writes_em_state(
        self,
        owner_and_dl: tuple[as_Service, SqliteDataLayer],
    ) -> None:
        """reject_embargo_proposal stores the case, so the stored EM is NONE."""
        owner, dl = owner_and_dl
        case, _ = _make_case(dl, owner.id_)
        embargo = _make_embargo(dl, case.id_)
        propose(case, embargo.id_)
        dl.save(case)
        write_consent_rows(dl, case)

        lifecycle = EmbargoLifecycle(persistence=dl)
        result = lifecycle.reject_embargo_proposal(
            case_id=case.id_,
            embargo_id=embargo.id_,
            actor_id=owner.id_,
            transition_mode=TransitionMode.STRICT,
        )

        assert result.em_after == EM.NONE
        refreshed = cast(VulnerabilityCase, dl.read(case.id_))
        assert refreshed.em_state == EM.NONE
        assert refreshed.current_status.em.state == EM.NONE

    def test_terminate_writes_em_state(
        self,
        owner_and_dl: tuple[as_Service, SqliteDataLayer],
    ) -> None:
        """terminate_active_embargo stores the case, so the stored EM is EXITED."""
        owner, dl = owner_and_dl
        case, _ = _make_case(dl, owner.id_)
        embargo = _make_embargo(dl, case.id_)
        activate(case, embargo.id_)
        dl.save(case)
        write_consent_rows(dl, case)

        lifecycle = EmbargoLifecycle(persistence=dl)
        result = lifecycle.terminate_active_embargo(
            case_id=case.id_,
            actor_id=owner.id_,
            transition_mode=TransitionMode.STRICT,
            reason=TerminationReason.EARLY,
        )

        assert result.em_after == EM.EXITED
        refreshed = cast(VulnerabilityCase, dl.read(case.id_))
        assert refreshed.em_state == EM.EXITED
        assert refreshed.current_status.em.state == EM.EXITED
