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


"""``propose_embargo`` (proposals.py).

Covers valid and invalid EM transitions in STRICT and OBSERVED mode, owner
versus non-owner proposers, idempotency, and the one consent effect a
proposal has: the proposer's own ``accepted_embargo_ids`` gains the proposed
id, while nobody's consent *state* changes (EP-05-002).  Also covers
``abandon_embargo_proposals``, the P/X/A abandonment of every open proposal
(EMB-16-001).  The answers to a proposal are tested in ``test_answers.py``."""

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
from vultron.core.states.participant_embargo_consent import PEC
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronValidationError,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service

from .conftest import (
    _accepted_ids_of,
    _force_pec,
    _make_actor,
    _make_case,
    _make_embargo,
    _pec_of,
    _seed_consent,
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


@pytest.mark.spec("EP-05-002")
@pytest.mark.spec("MSM-07-005")
@pytest.mark.spec("CM-18-002")
def test_propose_embargo_active_to_revise_changes_no_consent(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """propose_embargo from ACTIVE moves EM to REVISE and lapses nobody.

    A revision *proposal* changes no participant's consent (EP-05-002,
    ADR-0093): the prior embargo is still in force, so every signatory to it
    stays SIGNATORY.  Proposing terms is consenting to them, so the
    proposer's ``accepted_embargo_ids`` gains the proposed id — list only.
    """
    owner, dl = owner_and_dl
    finder = _make_actor(dl, "Finder Org")
    case, participants = _make_case(
        dl, owner.id_, extra_participant_ids=[finder.id_], em_state=EM.ACTIVE
    )
    active = _make_embargo(dl, case.id_)
    case.active_embargo = active.id_
    dl.save(case)
    for p in participants:
        _seed_consent(dl, p.id_, PEC.SIGNATORY, [active.id_])

    revision = _make_embargo(dl, case.id_, days=90)

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.propose_embargo(
        case_id=case.id_,
        embargo_id=revision.id_,
        actor_id=finder.id_,
    )

    assert result.em_before == EM.ACTIVE
    assert result.em_after == EM.REVISE
    assert result.case_changed is True
    assert result.participant_changes == []

    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.current_status.em.state == EM.REVISE
    owner_p, finder_p = participants
    for p in participants:
        assert _pec_of(dl, p.id_) == PEC.SIGNATORY.value
    # The proposer consented to its own terms; nobody else's list moved.
    assert _accepted_ids_of(dl, finder_p.id_) == [active.id_, revision.id_]
    assert _accepted_ids_of(dl, owner_p.id_) == [active.id_]


@pytest.mark.spec("EP-05-002")
@pytest.mark.spec("MSM-07-005")
def test_propose_embargo_revise_to_revise_changes_no_consent(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A counter-revision (REVISE → REVISE) changes nobody's consent state either.

    The proposer's list gains the counter-proposed id; a signatory stays a
    signatory; an invitee stays invited.
    """
    owner, dl = owner_and_dl
    finder = _make_actor(dl, "Finder Org")
    invitee = _make_actor(dl, "Invitee Org")
    case, participants = _make_case(
        dl,
        owner.id_,
        extra_participant_ids=[finder.id_, invitee.id_],
        em_state=EM.REVISE,
    )
    owner_p, finder_p, invitee_p = participants
    active = _make_embargo(dl, case.id_)
    first_revision = _make_embargo(dl, case.id_, days=90)
    case.active_embargo = active.id_
    case.proposed_embargoes = [first_revision.id_]
    dl.save(case)
    _seed_consent(dl, owner_p.id_, PEC.SIGNATORY, [active.id_])
    _seed_consent(dl, finder_p.id_, PEC.SIGNATORY, [active.id_])
    _force_pec(dl, invitee_p.id_, PEC.INVITED)

    counter = _make_embargo(dl, case.id_, days=60)
    result = EmbargoLifecycle(persistence=dl).propose_embargo(
        case_id=case.id_, embargo_id=counter.id_, actor_id=finder.id_
    )

    assert result.em_before == EM.REVISE
    assert result.em_after == EM.REVISE
    assert result.participant_changes == []
    assert _pec_of(dl, owner_p.id_) == PEC.SIGNATORY.value
    assert _pec_of(dl, finder_p.id_) == PEC.SIGNATORY.value
    assert _pec_of(dl, invitee_p.id_) == PEC.INVITED.value
    assert _accepted_ids_of(dl, finder_p.id_) == [active.id_, counter.id_]
    assert _accepted_ids_of(dl, owner_p.id_) == [active.id_]
    assert _accepted_ids_of(dl, invitee_p.id_) == []
    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.proposed_embargoes == [first_revision.id_, counter.id_]


def test_propose_embargo_by_a_non_participant_records_no_consent(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A proposer with no participant record (the creation default) has nothing to record."""
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_, em_state=EM.NONE)
    embargo = _make_embargo(dl, case.id_)

    result = EmbargoLifecycle(persistence=dl).propose_embargo(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id="https://example.org/actors/case-actor",
    )

    assert result.em_after == EM.PROPOSED
    assert _accepted_ids_of(dl, owner_p.id_) == []


@pytest.mark.spec("CM-18-003")
def test_propose_embargo_by_a_declined_participant_records_no_consent(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A DECLINED proposer holds no consent until re-invited (#4003).

    Recording its proposal on its list would let the content gate admit it
    once the owner activated the terms, while its state stayed DECLINED.
    """
    owner, dl = owner_and_dl
    proposer = _make_actor(dl, "Proposer")
    case, (_owner_p, proposer_p) = _make_case(
        dl, owner.id_, extra_participant_ids=[proposer.id_], em_state=EM.NONE
    )
    _force_pec(dl, proposer_p.id_, PEC.DECLINED)
    embargo = _make_embargo(dl, case.id_)

    result = EmbargoLifecycle(persistence=dl).propose_embargo(
        case_id=case.id_, embargo_id=embargo.id_, actor_id=proposer.id_
    )

    assert result.em_after == EM.PROPOSED
    assert _pec_of(dl, proposer_p.id_) == PEC.DECLINED.value
    assert _accepted_ids_of(dl, proposer_p.id_) == []


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
# abandon_embargo_proposals (EMB-16-001, #4131)
# ---------------------------------------------------------------------------


def _case_with_open_proposals(
    dl: SqliteDataLayer, owner_id: str, n: int, em_state: EM = EM.PROPOSED
) -> tuple[VulnerabilityCase, list[str]]:
    """A case at *em_state* with *n* open, indexed proposals."""
    case, _ = _make_case(dl, owner_id, em_state=em_state)
    ids = [
        _make_embargo(dl, case.id_, days=30 * (i + 1)).id_ for i in range(n)
    ]
    case.proposed_embargoes = list(ids)
    case.pending_embargo_proposal_index = {
        embargo_id: f"{embargo_id}/invite" for embargo_id in ids
    }
    dl.save(case)
    return case, ids


@pytest.mark.spec("EMB-16-001")
def test_abandon_every_open_proposal_returns_em_to_none(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    owner, dl = owner_and_dl
    case, ids = _case_with_open_proposals(dl, owner.id_, 2)

    result = EmbargoLifecycle(persistence=dl).abandon_embargo_proposals(
        case_id=case.id_, embargo_ids=ids, actor_id=owner.id_
    )

    assert (result.em_before, result.em_after) == (EM.PROPOSED, EM.NONE)
    assert result.case_changed is True
    assert result.participant_changes == []
    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.current_status.em.state == EM.NONE
    assert updated.proposed_embargo_ids == []
    assert updated.pending_embargo_proposal_index == {}


@pytest.mark.spec("EMB-16-001")
def test_abandon_changes_no_consent(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Nobody answered, so nobody's consent record moves (MSM-07-004)."""
    owner, dl = owner_and_dl
    case, ids = _case_with_open_proposals(dl, owner.id_, 1)
    (owner_pid,) = case.actor_participant_index.values()
    _force_pec(dl, owner_pid, PEC.INVITED)

    EmbargoLifecycle(persistence=dl).abandon_embargo_proposals(
        case_id=case.id_, embargo_ids=ids, actor_id=owner.id_
    )

    assert _pec_of(dl, owner_pid) == PEC.INVITED


@pytest.mark.spec("EMB-16-001")
@pytest.mark.spec("EP-09-007")
def test_observed_abandonment_of_one_keeps_em_until_the_last(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A replica replays one entry per proposal and reaches NONE with the
    last; a repeated entry is a no-op."""
    owner, dl = owner_and_dl
    case, (first, second) = _case_with_open_proposals(dl, owner.id_, 2)
    lifecycle = EmbargoLifecycle(persistence=dl)

    def _observe(embargo_id: str) -> EmbargoLifecycleResult:
        return lifecycle.abandon_embargo_proposals(
            case_id=case.id_,
            embargo_ids=[embargo_id],
            transition_mode=TransitionMode.OBSERVED,
        )

    assert _observe(first).em_after == EM.PROPOSED
    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.proposed_embargo_ids == [second]

    assert _observe(second).em_after == EM.NONE
    repeated = _observe(second)
    assert (repeated.em_after, repeated.case_changed) == (EM.NONE, False)


@pytest.mark.spec("EMB-18-003")
@pytest.mark.parametrize("embargo_ids", [[], ["urn:uuid:not-open"]])
def test_strict_abandonment_of_no_open_proposal_is_refused(
    owner_and_dl: tuple[as_Service, SqliteDataLayer], embargo_ids: list[str]
) -> None:
    owner, dl = owner_and_dl
    case, ids = _case_with_open_proposals(dl, owner.id_, 1)

    with pytest.raises(VultronValidationError):
        EmbargoLifecycle(persistence=dl).abandon_embargo_proposals(
            case_id=case.id_, embargo_ids=[*embargo_ids], actor_id=owner.id_
        )

    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.proposed_embargo_ids == ids
    assert updated.current_status.em.state == EM.PROPOSED


@pytest.mark.spec("EMB-18-003")
def test_strict_abandonment_outside_proposed_is_refused(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """In REVISE the open proposals are revisions of an embargo in force;
    the P/X/A cascade terminates it instead (EMB-07-002)."""
    owner, dl = owner_and_dl
    case, ids = _case_with_open_proposals(dl, owner.id_, 1, EM.REVISE)

    with pytest.raises(VultronInvalidStateTransitionError):
        EmbargoLifecycle(persistence=dl).abandon_embargo_proposals(
            case_id=case.id_, embargo_ids=ids, actor_id=owner.id_
        )

    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.proposed_embargo_ids == ids
