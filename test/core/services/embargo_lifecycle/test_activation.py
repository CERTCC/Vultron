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
forgotten (EP-08-004), no consent written.  Activation: EM to ACTIVE, the proposal
that carried the embargo decided (EP-08-003), and — when it replaces an
embargo already in force — the EP-05-001 containment carry-over.
"""

from typing import cast

import pytest

from test.support.embargo_register import activate, propose
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    TransitionMode,
)
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import TerminationReason
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


@pytest.mark.spec("EP-08-003")
def test_activate_embargo_prunes_the_proposal_from_both_records(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Activation decides the proposal that carried the embargo.

    ``activate_embargo`` is the received-side ``Add(EmbargoEvent)`` path
    (case creation uses ``initialize_creation_embargo``); after it the
    embargo is active and no longer an open proposal in either record
    (EP-08-003, #3470).
    """
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)
    embargo = _make_embargo(dl, case.id_)
    other = _make_embargo(dl, case.id_)
    propose(case, embargo.id_, other.id_)
    case.pending_embargo_proposal_index = {
        embargo.id_: f"{case.id_}/embargo_proposals/1",
        other.id_: f"{case.id_}/embargo_proposals/2",
    }
    dl.save(case)

    result = EmbargoLifecycle(persistence=dl).activate_embargo(
        case_id=case.id_, embargo_id=embargo.id_, actor_id=owner.id_
    )

    # The other proposal is still open, so it is now a revision of the
    # embargo in force: EM derives REVISE (ADR-0122).
    assert result.em_after == EM.REVISE
    activated = cast(VulnerabilityCase, dl.read(case.id_))
    assert activated.active_embargo_id == embargo.id_
    # The decided proposal left both records; the other stays open.
    assert activated.proposed_embargo_ids == [other.id_]
    assert activated.pending_embargo_proposal_index == {
        other.id_: f"{case.id_}/embargo_proposals/2"
    }


@pytest.mark.spec("CM-18-016", "MSM-07-006")
def test_terminate_active_embargo_strict_active_to_exited(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Terminate from ACTIVE: EM -> EXITED and no consent row is written.

    Nobody is a signatory afterwards because no embargo is active; the rows
    stay exactly as they were (CM-18-016) and nobody has lapsed.
    """
    owner, dl = owner_and_dl
    finder = _make_actor(dl, "Finder Org")
    case, participants = _make_case(
        dl,
        owner.id_,
        extra_participant_ids=[finder.id_],
    )
    owner_participant_id, finder_participant_id = (p.id_ for p in participants)
    embargo = _make_embargo(dl, case.id_)
    activate(case, embargo.id_)
    dl.save(case)
    _seed_consent(dl, owner_participant_id, embargo.id_, ECS.ACCEPTED)
    _seed_consent(dl, finder_participant_id, embargo.id_, ECS.INVITED)
    assert _is_signatory(dl, case.id_, owner_participant_id)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.terminate_active_embargo(
        reason=TerminationReason.EARLY,
        case_id=case.id_,
        actor_id=owner.id_,
    )

    assert result.em_before == EM.ACTIVE
    assert result.em_after == EM.EXITED
    assert result.participant_changes == []
    assert _consents_of(dl, owner_participant_id) == {embargo.id_: "ACCEPTED"}
    assert _consents_of(dl, finder_participant_id) == {embargo.id_: "INVITED"}
    for pid in (owner_participant_id, finder_participant_id):
        assert not _is_signatory(dl, case.id_, pid)
        assert not _has_lapsed(dl, case.id_, pid)


def test_terminate_active_embargo_strict_revise_to_exited(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Terminate from REVISE: EM → EXITED."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)
    embargo = _make_embargo(dl, case.id_)
    activate(case, embargo.id_)
    dl.save(case)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.terminate_active_embargo(
        reason=TerminationReason.EARLY,
        case_id=case.id_,
        actor_id=owner.id_,
    )

    assert result.em_after == EM.EXITED


def test_terminate_active_embargo_strict_no_active_embargo_raises(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """STRICT terminate with no embargo at all (EM NONE) raises."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)

    lifecycle = EmbargoLifecycle(persistence=dl)
    with pytest.raises(VultronInvalidStateTransitionError):
        lifecycle.terminate_active_embargo(
            reason=TerminationReason.EARLY,
            case_id=case.id_,
            actor_id=owner.id_,
        )


def test_terminate_active_embargo_strict_proposed_only_raises(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """STRICT terminate from PROPOSED (nothing in force) raises, case unchanged."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)
    embargo = _make_embargo(dl, case.id_)
    propose(case, embargo.id_)
    dl.save(case)

    lifecycle = EmbargoLifecycle(persistence=dl)
    with pytest.raises(VultronInvalidStateTransitionError):
        lifecycle.terminate_active_embargo(
            reason=TerminationReason.EARLY,
            case_id=case.id_,
            actor_id=owner.id_,
        )

    untouched = cast(VulnerabilityCase, dl.read(case.id_))
    assert untouched.em_state == EM.PROPOSED
    assert untouched.proposed_embargo_ids == [embargo.id_]


def test_terminate_active_embargo_observed_with_nothing_in_force_changes_nothing(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """OBSERVED mode: no active embargo is logged and skipped, never forced.

    The register is never driven into a state its rules refuse (ADR-0122):
    with only an open proposal there is nothing to terminate, so the replica
    keeps its proposal and EM stays PROPOSED rather than syncing to EXITED.
    """
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)
    embargo = _make_embargo(dl, case.id_)
    propose(case, embargo.id_)
    dl.save(case)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.terminate_active_embargo(
        reason=TerminationReason.EARLY,
        case_id=case.id_,
        actor_id=owner.id_,
        transition_mode=TransitionMode.OBSERVED,
    )

    assert result.em_after == EM.PROPOSED
    assert not result.case_changed
    untouched = cast(VulnerabilityCase, dl.read(case.id_))
    assert untouched.em_state == EM.PROPOSED
    assert untouched.proposed_embargo_ids == [embargo.id_]


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
    case, _ = _make_case(dl, owner.id_)
    active = _make_embargo(dl, case.id_)
    revision = _make_embargo(dl, case.id_)
    activate(case, active.id_)
    propose(case, revision.id_)
    case.pending_embargo_proposal_index = {
        revision.id_: f"{case.id_}/embargo_proposals/revision",
    }
    dl.save(case)

    result = EmbargoLifecycle(persistence=dl).terminate_active_embargo(
        reason=TerminationReason.EARLY, case_id=case.id_, actor_id=owner.id_
    )

    assert result.em_after == EM.EXITED
    torn_down = cast(VulnerabilityCase, dl.read(case.id_))
    assert torn_down.active_embargo is None
    assert torn_down.proposed_embargo_ids == []
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
    case, _ = _make_case(dl, owner.id_)
    active = _make_embargo(dl, case.id_)
    revision_a = _make_embargo(dl, case.id_, days=60)
    revision_b = _make_embargo(dl, case.id_, days=90)
    activate(case, active.id_)
    propose(case, revision_a.id_, revision_b.id_)
    case.pending_embargo_proposal_index = {
        revision_a.id_: f"{case.id_}/embargo_proposals/a",
        revision_b.id_: f"{case.id_}/embargo_proposals/b",
    }
    dl.save(case)

    result = EmbargoLifecycle(persistence=dl).terminate_active_embargo(
        reason=TerminationReason.EARLY,
        case_id=case.id_,
        actor_id=owner.id_,
        transition_mode=TransitionMode.OBSERVED,
    )

    assert result.em_after == EM.EXITED
    torn_down = cast(VulnerabilityCase, dl.read(case.id_))
    assert torn_down.active_embargo is None
    assert torn_down.proposed_embargo_ids == []
    assert torn_down.pending_embargo_proposal_index == {}


@pytest.mark.spec("EP-05-001")
@pytest.mark.spec("MSM-07-005")
def test_activate_embargo_replacing_a_longer_one_carries_signatories_over(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """``activate_embargo`` runs the containment carry-over (shorter arm).

    A B ending before A asks nothing new of a signatory to A, so both the
    owner and the silent signatory gain ACCEPTED(B); each change is reported.
    """
    owner, dl = owner_and_dl
    signer = _make_actor(dl, "Signer")
    case, (owner_p, signer_p) = _make_case(
        dl, owner.id_, extra_participant_ids=[signer.id_]
    )
    active = _make_embargo(dl, case.id_)
    revision = _make_embargo(dl, case.id_, days=30)
    activate(case, active.id_)
    propose(case, revision.id_)
    dl.save(case)
    _seed_consent(dl, owner_p.id_, active.id_, ECS.ACCEPTED)
    _seed_consent(dl, signer_p.id_, active.id_, ECS.ACCEPTED)

    result = EmbargoLifecycle(persistence=dl).activate_embargo(
        case_id=case.id_, embargo_id=revision.id_, actor_id=owner.id_
    )

    assert result.em_after == EM.ACTIVE
    assert {
        (c.participant_id, c.embargo_id, c.consent_before, c.consent_after)
        for c in result.participant_changes
    } == {
        (pid, revision.id_, None, "ACCEPTED")
        for pid in (owner_p.id_, signer_p.id_)
    }
    for pid in (owner_p.id_, signer_p.id_):
        assert _consents_of(dl, pid) == {
            active.id_: "ACCEPTED",
            revision.id_: "ACCEPTED",
        }
        assert _is_signatory(dl, case.id_, pid)


@pytest.mark.spec("EP-05-001")
@pytest.mark.spec("MSM-07-005")
@pytest.mark.spec("CM-18-016")
def test_activate_embargo_replacing_a_shorter_one_lapses_non_acceptors(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Longer arm, OBSERVED (a replica syncing an Add): nothing is written.

    The owner already holds ACCEPTED(B), so no row changes at all.  The
    signatory that never accepted B is no longer a signatory and
    ``has_lapsed`` holds by derivation; the early acceptor stays bound.
    """
    owner, dl = owner_and_dl
    signer = _make_actor(dl, "Signer")
    acceptor = _make_actor(dl, "Acceptor")
    case, (owner_p, signer_p, acceptor_p) = _make_case(
        dl,
        owner.id_,
        extra_participant_ids=[signer.id_, acceptor.id_],
    )
    active = _make_embargo(dl, case.id_)
    revision = _make_embargo(dl, case.id_, days=90)
    activate(case, active.id_)
    propose(case, revision.id_)
    dl.save(case)
    for p in (owner_p, signer_p, acceptor_p):
        _seed_consent(dl, p.id_, active.id_, ECS.ACCEPTED)
    _seed_consent(dl, owner_p.id_, revision.id_, ECS.ACCEPTED)
    _seed_consent(dl, acceptor_p.id_, revision.id_, ECS.ACCEPTED)

    result = EmbargoLifecycle(persistence=dl).activate_embargo(
        case_id=case.id_,
        embargo_id=revision.id_,
        actor_id=owner.id_,
        transition_mode=TransitionMode.OBSERVED,
    )

    assert result.em_after == EM.ACTIVE
    assert result.participant_changes == []
    assert _consents_of(dl, signer_p.id_) == {active.id_: "ACCEPTED"}
    assert _is_signatory(dl, case.id_, owner_p.id_)
    assert _is_signatory(dl, case.id_, acceptor_p.id_)
    assert not _is_signatory(dl, case.id_, signer_p.id_)
    assert _has_lapsed(dl, case.id_, signer_p.id_)


@pytest.mark.spec("EP-05-001")
@pytest.mark.spec("CM-18-016")
def test_activate_embargo_first_activation_writes_only_the_owners_agreement(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """PROPOSED -> ACTIVE writes only the owner's agreement.

    The activation is the case owner's decision, so its row for B becomes
    ACCEPTED (ADR-0122).  Holders of ACCEPTED(B) (the proposer, an early
    acceptor) are signatories by lookup with no advance step; a merely
    INVITED participant is not, and has not lapsed either.
    """
    owner, dl = owner_and_dl
    proposer = _make_actor(dl, "Proposer")
    invitee = _make_actor(dl, "Invitee")
    case, (owner_p, proposer_p, invitee_p) = _make_case(
        dl,
        owner.id_,
        extra_participant_ids=[proposer.id_, invitee.id_],
    )
    embargo = _make_embargo(dl, case.id_)
    propose(case, embargo.id_)
    dl.save(case)
    _seed_consent(dl, proposer_p.id_, embargo.id_, ECS.ACCEPTED)
    _seed_consent(dl, invitee_p.id_, embargo.id_, ECS.INVITED)

    result = EmbargoLifecycle(persistence=dl).activate_embargo(
        case_id=case.id_, embargo_id=embargo.id_, actor_id=owner.id_
    )

    assert result.em_after == EM.ACTIVE
    assert [
        (c.participant_id, c.consent_before, c.consent_after)
        for c in result.participant_changes
    ] == [(owner_p.id_, None, "ACCEPTED")]
    assert _consents_of(dl, owner_p.id_) == {embargo.id_: "ACCEPTED"}
    assert _is_signatory(dl, case.id_, owner_p.id_)
    assert _consents_of(dl, proposer_p.id_) == {embargo.id_: "ACCEPTED"}
    assert _consents_of(dl, invitee_p.id_) == {embargo.id_: "INVITED"}
    assert _is_signatory(dl, case.id_, proposer_p.id_)
    assert not _is_signatory(dl, case.id_, invitee_p.id_)
    assert not _has_lapsed(dl, case.id_, invitee_p.id_)


@pytest.mark.spec("EP-05-001")
def test_activate_embargo_records_the_owners_acceptance_of_a_longer_revision(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Activating B is the owner's decision, so the owner never lapses by it.

    A replica syncing an announced activation (``SetEmbargoActiveNode``,
    OBSERVED) sees the owner ACCEPTED on A with no row for B; the owner gains
    ACCEPTED(B) and stays a signatory while a silent signatory lapses by
    derivation.  The owner's row is the only one written.
    """
    owner, dl = owner_and_dl
    signer = _make_actor(dl, "Signer")
    case, (owner_p, signer_p) = _make_case(
        dl, owner.id_, extra_participant_ids=[signer.id_]
    )
    active = _make_embargo(dl, case.id_)
    revision = _make_embargo(dl, case.id_, days=90)
    activate(case, active.id_)
    propose(case, revision.id_)
    dl.save(case)
    _seed_consent(dl, owner_p.id_, active.id_, ECS.ACCEPTED)
    _seed_consent(dl, signer_p.id_, active.id_, ECS.ACCEPTED)

    result = EmbargoLifecycle(persistence=dl).activate_embargo(
        case_id=case.id_,
        embargo_id=revision.id_,
        actor_id="https://example.org/actors/replica",
        transition_mode=TransitionMode.OBSERVED,
    )

    assert _consents_of(dl, owner_p.id_) == {
        active.id_: "ACCEPTED",
        revision.id_: "ACCEPTED",
    }
    assert _is_signatory(dl, case.id_, owner_p.id_)
    assert _consents_of(dl, signer_p.id_) == {active.id_: "ACCEPTED"}
    assert _has_lapsed(dl, case.id_, signer_p.id_)
    assert [
        (c.participant_id, c.embargo_id, c.consent_after)
        for c in result.participant_changes
    ] == [(owner_p.id_, revision.id_, "ACCEPTED")]


@pytest.mark.spec("EP-05-001")
def test_activate_embargo_of_equal_terms_carries_signatories_over(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Equal end times count as "no later": the carry-over applies."""
    owner, dl = owner_and_dl
    signer = _make_actor(dl, "Signer")
    case, (owner_p, signer_p) = _make_case(
        dl, owner.id_, extra_participant_ids=[signer.id_]
    )
    active = _make_embargo(dl, case.id_)
    same = _make_embargo(dl, case.id_, end_time=active.end_time)
    activate(case, active.id_)
    propose(case, same.id_)
    dl.save(case)
    _seed_consent(dl, signer_p.id_, active.id_, ECS.ACCEPTED)

    EmbargoLifecycle(persistence=dl).activate_embargo(
        case_id=case.id_, embargo_id=same.id_, actor_id=owner.id_
    )

    assert _consent_of(dl, signer_p.id_, same.id_) == "ACCEPTED"
    assert _is_signatory(dl, case.id_, signer_p.id_)
    assert _is_signatory(dl, case.id_, owner_p.id_)


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
    case, _ = _make_case(dl, owner.id_)
    revision = _make_embargo(dl, case.id_, days=90)
    activate(case, "https://example.org/embargoes/not-replicated")
    propose(case, revision.id_)
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
    assert untouched.proposed_embargo_ids == [revision.id_]


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
