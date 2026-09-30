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


"""terminate_active_embargo — EM to EXITED, active embargo cleared, PEC reset
(activation.py)."""

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
from vultron.errors import VultronInvalidStateTransitionError
from vultron.wire.as2.vocab.base.objects.actors import as_Service

from .conftest import (
    _make_actor,
    _make_case,
    _make_embargo,
)


@pytest.mark.spec("EP-08-003")
def test_activate_embargo_prunes_the_proposal_from_both_records(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Activation decides the proposal that carried the embargo.

    ``activate_embargo`` is the received-side ``Add(EmbargoEvent)`` and the
    case-creation path; after it the embargo is active and no longer an open
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


@pytest.mark.xfail(
    strict=True,
    reason=(
        "EP-08-004: termination prunes only the terminated embargo's own "
        "entry and leaves open revisions of it in both records. Tracked by "
        "#3914 (Concern #3836, ADR-0113)."
    ),
)
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
