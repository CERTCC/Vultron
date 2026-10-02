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


"""terminate_active_embargo and activate_embargo (activation.py).

Termination: EM to EXITED, active embargo cleared, every open proposal
forgotten (EP-08-004), PEC reset.  Activation: EM to ACTIVE, the proposal
that carried the embargo decided (EP-08-003), and — when it replaces an
embargo already in force — the EP-05-001 consent re-evaluation.
"""

from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    TransitionMode,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronNotFoundError,
    VultronValidationError,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service

from .conftest import (
    UNHELD_EMBARGO_ID,
    _accepted_ids_of,
    _assert_activation_wrote_nothing,
    _case_awaiting_activation,
    _make_actor,
    _make_case,
    _make_embargo,
    _pec_of,
    _seed_consent,
)


@pytest.mark.spec("EP-08-003")
def test_activate_embargo_prunes_the_proposal_from_both_records(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Activation decides the proposal that carried the embargo.

    ``activate_embargo`` is the received-side ``Add(EmbargoEvent)`` path
    (case creation uses ``initialize_creation_embargo``); after it the embargo is active and no longer an open
    proposal in either record (EP-08-003, #3470).
    """
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.PROPOSED)
    embargo = _make_embargo(dl, case.id_)
    other = _make_embargo(dl, case.id_)
    case.proposed_embargoes = [embargo.id_, other.id_]
    case.pending_embargo_proposal_index = {
        embargo.id_: f"{case.id_}/embargo_proposals/1",
        other.id_: f"{case.id_}/embargo_proposals/2",
    }
    dl.save(case)

    result = EmbargoLifecycle(persistence=dl).activate_embargo(
        case_id=case.id_, embargo_id=embargo.id_, actor_id=owner.id_
    )

    assert result.em_after == EM.ACTIVE
    activated = cast(VulnerabilityCase, dl.read(case.id_))
    assert activated.active_embargo_id == embargo.id_
    # The decided proposal left both records; the other stays open.
    assert activated.proposed_embargoes == [other.id_]
    assert activated.pending_embargo_proposal_index == {
        other.id_: f"{case.id_}/embargo_proposals/2"
    }


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
    object.__setattr__(
        owner_participant, "embargo_consent_state", PEC.SIGNATORY
    )
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
        refreshed_owner_participant.embargo_consent_state == PEC.UNBOUND.value
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


@pytest.mark.spec("EP-08-004")
def test_terminate_clears_every_open_revision_of_the_terminated_embargo(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Termination decides every open proposal (EP-08-004).

    A case has one active embargo, so every proposal open while EM is ACTIVE
    or REVISE is a revision of it, and a revision of an embargo that no longer
    exists cannot be accepted.  Both open-proposal records are empty after
    teardown with a revision pending.
    """
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.REVISE)
    active = _make_embargo(dl, case.id_)
    revision = _make_embargo(dl, case.id_)
    case.active_embargo = active.id_
    case.proposed_embargoes = [revision.id_]
    case.pending_embargo_proposal_index = {
        revision.id_: f"{case.id_}/embargo_proposals/revision",
    }
    dl.save(case)

    result = EmbargoLifecycle(persistence=dl).terminate_active_embargo(
        case_id=case.id_, actor_id=owner.id_
    )

    assert result.em_after == EM.EXITED
    torn_down = cast(VulnerabilityCase, dl.read(case.id_))
    assert torn_down.active_embargo is None
    assert torn_down.proposed_embargoes == []
    assert torn_down.pending_embargo_proposal_index == {}


@pytest.mark.spec("EP-08-004")
def test_terminate_in_observed_mode_clears_every_open_revision_too(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """The replica path: the teardown replay node runs this in OBSERVED mode.

    ``ClearActiveEmbargoNode`` / ``ApplyEmbargoTeardownNode`` call
    ``terminate_active_embargo(transition_mode=OBSERVED)``, so the rule that
    termination decides every open proposal holds on every replica with no
    node of its own — this pins that the mode makes no difference.
    """
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.ACTIVE)
    active = _make_embargo(dl, case.id_)
    revision_a = _make_embargo(dl, case.id_, days=60)
    revision_b = _make_embargo(dl, case.id_, days=90)
    case.active_embargo = active.id_
    case.proposed_embargoes = [revision_a.id_, revision_b.id_]
    case.pending_embargo_proposal_index = {
        revision_a.id_: f"{case.id_}/embargo_proposals/a",
        revision_b.id_: f"{case.id_}/embargo_proposals/b",
    }
    dl.save(case)

    result = EmbargoLifecycle(persistence=dl).terminate_active_embargo(
        case_id=case.id_,
        actor_id=owner.id_,
        transition_mode=TransitionMode.OBSERVED,
    )

    assert result.em_after == EM.EXITED
    torn_down = cast(VulnerabilityCase, dl.read(case.id_))
    assert torn_down.active_embargo is None
    assert torn_down.proposed_embargoes == []
    assert torn_down.pending_embargo_proposal_index == {}


@pytest.mark.spec("EP-05-001")
@pytest.mark.spec("MSM-07-005")
def test_activate_embargo_replacing_a_longer_one_carries_signatories_over(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """``activate_embargo`` runs the same cascade as the owner's accept (shorter arm)."""
    owner, dl = owner_and_dl
    signer = _make_actor(dl, "Signer")
    case, (owner_p, signer_p) = _make_case(
        dl, owner.id_, extra_participant_ids=[signer.id_], em_state=EM.REVISE
    )
    active = _make_embargo(dl, case.id_)
    revision = _make_embargo(dl, case.id_, days=30)
    case.active_embargo = active.id_
    case.proposed_embargoes = [revision.id_]
    dl.save(case)
    _seed_consent(dl, owner_p.id_, PEC.SIGNATORY, [active.id_])
    _seed_consent(dl, signer_p.id_, PEC.SIGNATORY, [active.id_])

    result = EmbargoLifecycle(persistence=dl).activate_embargo(
        case_id=case.id_, embargo_id=revision.id_, actor_id=owner.id_
    )

    assert result.em_after == EM.ACTIVE
    assert result.participant_changes == []
    for pid in (owner_p.id_, signer_p.id_):
        assert _pec_of(dl, pid) == PEC.SIGNATORY.value
        assert _accepted_ids_of(dl, pid) == [active.id_, revision.id_]


@pytest.mark.spec("EP-05-001")
@pytest.mark.spec("MSM-07-005")
def test_activate_embargo_replacing_a_shorter_one_lapses_non_acceptors(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """``activate_embargo`` (longer arm, OBSERVED — a replica syncing an Add)."""
    owner, dl = owner_and_dl
    signer = _make_actor(dl, "Signer")
    acceptor = _make_actor(dl, "Acceptor")
    case, (owner_p, signer_p, acceptor_p) = _make_case(
        dl,
        owner.id_,
        extra_participant_ids=[signer.id_, acceptor.id_],
        em_state=EM.REVISE,
    )
    active = _make_embargo(dl, case.id_)
    revision = _make_embargo(dl, case.id_, days=90)
    case.active_embargo = active.id_
    case.proposed_embargoes = [revision.id_]
    dl.save(case)
    _seed_consent(dl, owner_p.id_, PEC.SIGNATORY, [active.id_, revision.id_])
    _seed_consent(dl, signer_p.id_, PEC.SIGNATORY, [active.id_])
    _seed_consent(
        dl, acceptor_p.id_, PEC.SIGNATORY, [active.id_, revision.id_]
    )

    result = EmbargoLifecycle(persistence=dl).activate_embargo(
        case_id=case.id_,
        embargo_id=revision.id_,
        actor_id=owner.id_,
        transition_mode=TransitionMode.OBSERVED,
    )

    assert result.em_after == EM.ACTIVE
    assert [
        (c.participant_id, c.pec_after) for c in result.participant_changes
    ] == [(signer_p.id_, PEC.LAPSED.value)]
    assert _pec_of(dl, owner_p.id_) == PEC.SIGNATORY.value
    assert _pec_of(dl, acceptor_p.id_) == PEC.SIGNATORY.value
    assert _pec_of(dl, signer_p.id_) == PEC.LAPSED.value


def test_activate_embargo_first_activation_re_evaluates_nobody(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """PROPOSED → ACTIVE replaces nothing, so there is no A to compare B against.

    Nobody here holds B either, so nobody advances; see the next test for the
    holder of B that a first activation does advance.
    """
    owner, dl = owner_and_dl
    signer = _make_actor(dl, "Signer")
    case, (_owner_p, signer_p) = _make_case(
        dl, owner.id_, extra_participant_ids=[signer.id_], em_state=EM.PROPOSED
    )
    embargo = _make_embargo(dl, case.id_)
    _seed_consent(dl, signer_p.id_, PEC.INVITED, [])

    result = EmbargoLifecycle(persistence=dl).activate_embargo(
        case_id=case.id_, embargo_id=embargo.id_, actor_id=owner.id_
    )

    assert result.em_after == EM.ACTIVE
    assert result.participant_changes == []
    assert _pec_of(dl, signer_p.id_) == PEC.INVITED.value


@pytest.mark.spec("EP-05-001")
@pytest.mark.spec("MSM-07-005")
def test_activate_embargo_first_activation_advances_the_holders_of_the_new_id(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A first activation has no A-vs-B arm, but a holder of B is a signatory now.

    The proposer of a first embargo holds its id list-only (MSM-07-005); once
    the owner activates it the proposer has accepted the embargo in force and
    advances, so the content gate (CM-10-004) and its state agree.
    """
    owner, dl = owner_and_dl
    proposer = _make_actor(dl, "Proposer")
    other = _make_actor(dl, "Other")
    case, (_owner_p, proposer_p, other_p) = _make_case(
        dl,
        owner.id_,
        extra_participant_ids=[proposer.id_, other.id_],
        em_state=EM.PROPOSED,
    )
    embargo = _make_embargo(dl, case.id_)
    _seed_consent(dl, proposer_p.id_, PEC.UNBOUND, [embargo.id_])
    _seed_consent(dl, other_p.id_, PEC.INVITED, [])

    result = EmbargoLifecycle(persistence=dl).activate_embargo(
        case_id=case.id_, embargo_id=embargo.id_, actor_id=owner.id_
    )

    assert result.em_after == EM.ACTIVE
    assert [c.participant_id for c in result.participant_changes] == [
        proposer_p.id_
    ]
    assert _pec_of(dl, proposer_p.id_) == PEC.SIGNATORY.value
    assert _pec_of(dl, other_p.id_) == PEC.INVITED.value


@pytest.mark.spec("EP-05-001")
def test_activate_embargo_records_the_owners_acceptance_before_the_cascade(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Activating B is the owner's decision, so the owner never lapses by it.

    A replica syncing an announced activation (``SetEmbargoActiveNode``,
    OBSERVED) sees the owner SIGNATORY to A with no B in its list; the owner
    gains B and stays SIGNATORY while a silent signatory lapses.
    """
    owner, dl = owner_and_dl
    signer = _make_actor(dl, "Signer")
    case, (owner_p, signer_p) = _make_case(
        dl, owner.id_, extra_participant_ids=[signer.id_], em_state=EM.REVISE
    )
    active = _make_embargo(dl, case.id_)
    revision = _make_embargo(dl, case.id_, days=90)
    case.active_embargo = active.id_
    case.proposed_embargoes = [revision.id_]
    dl.save(case)
    _seed_consent(dl, owner_p.id_, PEC.SIGNATORY, [active.id_])
    _seed_consent(dl, signer_p.id_, PEC.SIGNATORY, [active.id_])

    result = EmbargoLifecycle(persistence=dl).activate_embargo(
        case_id=case.id_,
        embargo_id=revision.id_,
        actor_id="https://example.org/actors/replica",
        transition_mode=TransitionMode.OBSERVED,
    )

    assert _pec_of(dl, owner_p.id_) == PEC.SIGNATORY.value
    assert _accepted_ids_of(dl, owner_p.id_) == [active.id_, revision.id_]
    assert _pec_of(dl, signer_p.id_) == PEC.LAPSED.value
    assert [
        (c.participant_id, c.pec_after) for c in result.participant_changes
    ] == [(signer_p.id_, PEC.LAPSED.value)]


@pytest.mark.spec("EMB-18-003")
@pytest.mark.parametrize(
    "mode", [TransitionMode.STRICT, TransitionMode.OBSERVED], ids=str
)
def test_activate_embargo_with_an_unreadable_previous_embargo_changes_nothing(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    mode: TransitionMode,
) -> None:
    """The A-vs-B read fails closed *before* EM or active_embargo move."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=EM.REVISE)
    revision = _make_embargo(dl, case.id_, days=90)
    case.active_embargo = "https://example.org/embargoes/not-replicated"
    case.proposed_embargoes = [revision.id_]
    dl.save(case)

    with pytest.raises(VultronNotFoundError):
        EmbargoLifecycle(persistence=dl).activate_embargo(
            case_id=case.id_,
            embargo_id=revision.id_,
            actor_id=owner.id_,
            transition_mode=mode,
        )

    untouched = cast(VulnerabilityCase, dl.read(case.id_))
    assert untouched.current_status.em.state == EM.REVISE
    assert untouched.active_embargo_id == (
        "https://example.org/embargoes/not-replicated"
    )
    assert untouched.proposed_embargoes == [revision.id_]


@pytest.mark.spec("EMB-18-003")
@pytest.mark.parametrize(
    "mode", [TransitionMode.STRICT, TransitionMode.OBSERVED], ids=str
)
@pytest.mark.parametrize(
    "replaces", [False, True], ids=["first-activation", "revision"]
)
def test_activation_of_an_unheld_embargo_writes_nothing(
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
        EmbargoLifecycle(persistence=dl).activate_embargo(
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
def test_activation_of_a_non_embargo_record_writes_nothing(
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
        EmbargoLifecycle(persistence=dl).activate_embargo(
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
