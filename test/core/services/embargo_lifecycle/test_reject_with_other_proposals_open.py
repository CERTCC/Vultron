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
"""``reject_embargo_invite`` when the owner decides one of several proposals.

Several proposals may be open at once, each decided on its own (EP-08-001).
The owner's ``reject_embargo_proposal`` of one rejects that one (EP-08-003,
ADR-0122); EM leaves
``PROPOSED``/``REVISE`` only when no proposal is left awaiting an answer.
"""

from typing import cast

import pytest

from test.support.embargo_register import activate, propose
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState as ECS,
)
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronValidationError,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service

from .conftest import (
    _consents_of,
    _make_actor,
    _make_case,
    _make_embargo,
    _seed_consent,
)


def _case_with_two_open(
    dl: SqliteDataLayer, owner_id: str, em_state: EM
) -> tuple[VulnerabilityCase, str, str, str | None]:
    """A case at *em_state* with proposals r1 and r2 open (and e1 if REVISE)."""
    case, _ = _make_case(dl, owner_id)
    active_id = None
    if em_state is EM.REVISE:
        active_id = _make_embargo(dl, case.id_).id_
        activate(case, active_id)
    r1 = _make_embargo(dl, case.id_, days=90).id_
    r2 = _make_embargo(dl, case.id_, days=120).id_
    propose(case, r1, r2)
    dl.save(case)
    assert case.em_state is em_state
    return case, r1, r2, active_id


@pytest.mark.spec("EP-08-001")
@pytest.mark.spec("EP-08-003")
@pytest.mark.parametrize("em_state", [EM.REVISE, EM.PROPOSED])
def test_owner_rejecting_one_of_two_open_proposals_keeps_the_em_state(
    owner_and_dl: tuple[as_Service, SqliteDataLayer], em_state: EM
) -> None:
    owner, dl = owner_and_dl
    case, r1, r2, active_id = _case_with_two_open(dl, owner.id_, em_state)

    result = EmbargoLifecycle(persistence=dl).reject_embargo_proposal(
        case_id=case.id_, embargo_id=r1, actor_id=owner.id_
    )

    assert result.em_after == em_state
    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.em_state == em_state
    assert updated.current_status.em.state == em_state
    assert updated.proposed_embargo_ids == [r2]
    assert updated.active_embargo_id == active_id


@pytest.mark.spec("EP-08-003")
def test_owner_rejecting_the_last_open_revision_returns_to_active(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    owner, dl = owner_and_dl
    case, r1, r2, active_id = _case_with_two_open(dl, owner.id_, EM.REVISE)
    lifecycle = EmbargoLifecycle(persistence=dl)
    lifecycle.reject_embargo_proposal(
        case_id=case.id_, embargo_id=r1, actor_id=owner.id_
    )

    result = lifecycle.reject_embargo_proposal(
        case_id=case.id_, embargo_id=r2, actor_id=owner.id_
    )

    assert result.em_after == EM.ACTIVE
    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.proposed_embargo_ids == []
    assert updated.active_embargo_id == active_id


@pytest.mark.spec("EMB-04-002")
@pytest.mark.spec("EP-08-001")
def test_owner_rejecting_one_of_two_revisions_with_pxa_set_is_allowed(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """The P/X/A guard bars only a Reject that returns the case to ACTIVE.

    With another revision still open, EM stays ``REVISE``: the case is not
    kept on the prior terms, so there is nothing for EMB-04-002 to refuse.
    """
    owner, dl = owner_and_dl
    case, r1, r2, active_id = _case_with_two_open(dl, owner.id_, EM.REVISE)
    case.append_case_status(pxa_state=CS_pxa.Pxa)
    dl.save(case)
    lifecycle = EmbargoLifecycle(persistence=dl)

    result = lifecycle.reject_embargo_proposal(
        case_id=case.id_, embargo_id=r1, actor_id=owner.id_
    )

    assert result.em_after == EM.REVISE
    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.proposed_embargo_ids == [r2]
    assert updated.active_embargo_id == active_id
    with pytest.raises(VultronInvalidStateTransitionError):
        lifecycle.reject_embargo_proposal(
            case_id=case.id_, embargo_id=r2, actor_id=owner.id_
        )


@pytest.mark.spec("MSM-07-004")
def test_the_owners_rejection_writes_no_consent(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """``Reject(EmbargoEvent, target=Case)`` decides; it changes no row (ADR-0122).

    Neither the owner's nor any invitee's row moves: refusing terms as a
    participant is a separate ``Reject(Invite(EmbargoEvent))``.
    """
    owner, dl = owner_and_dl
    finder = _make_actor(dl, "Finder Org")
    case, (owner_p, _finder_p) = _make_case(
        dl, owner.id_, extra_participant_ids=[finder.id_]
    )
    embargo = _make_embargo(dl, case.id_)
    propose(case, embargo.id_)
    dl.save(case)
    finder_pid = case.actor_participant_index[finder.id_]
    _seed_consent(dl, finder_pid, embargo.id_, ECS.INVITED)
    _seed_consent(dl, owner_p.id_, embargo.id_, ECS.INVITED)

    result = EmbargoLifecycle(persistence=dl).reject_embargo_proposal(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=owner.id_,
    )

    assert result.em_after == EM.NONE
    assert result.participant_changes == []
    assert _consents_of(dl, finder_pid) == {embargo.id_: "INVITED"}
    assert _consents_of(dl, owner_p.id_) == {embargo.id_: "INVITED"}


def test_strict_rejection_of_a_non_open_proposal_raises_and_writes_nothing(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """The embargo in force is no proposal: STRICT refuses before any write."""
    owner, dl = owner_and_dl
    case, r1, r2, active_id = _case_with_two_open(dl, owner.id_, EM.REVISE)
    assert active_id is not None

    with pytest.raises(VultronValidationError, match="not an open proposal"):
        EmbargoLifecycle(persistence=dl).reject_embargo_proposal(
            case_id=case.id_, embargo_id=active_id, actor_id=owner.id_
        )

    untouched = cast(VulnerabilityCase, dl.read(case.id_))
    assert untouched.em_state == EM.REVISE
    assert untouched.proposed_embargo_ids == [r1, r2]
    assert untouched.active_embargo_id == active_id
