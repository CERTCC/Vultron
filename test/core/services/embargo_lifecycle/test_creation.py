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

"""initialize_creation_embargo (creation.py): propose + activate, one write.

At case creation the PROPOSE and ACCEPT triggers are applied together and
only ``EM.ACTIVE`` is persisted (EP-04-002); any refusal leaves the case at
``EM.NONE`` so a redelivered proposal can finish it (EP-04-012, #4123).
"""

from typing import Any, cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronNotFoundError,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service

from .conftest import (
    UNHELD_EMBARGO_ID,
    _accepted_ids_of,
    _make_actor,
    _make_case,
    _make_embargo,
    _pec_of,
)

pytestmark = [pytest.mark.spec("EP-04-002"), pytest.mark.spec("EP-04-012")]


def _stored_case(dl: SqliteDataLayer, case_id: str) -> VulnerabilityCase:
    return cast(VulnerabilityCase, dl.read(case_id))


def _assert_untouched(dl: SqliteDataLayer, case_id: str) -> None:
    case = _stored_case(dl, case_id)
    assert case.current_status.em.state == EM.NONE
    assert case.active_embargo_id is None
    assert case.proposed_embargoes == []


def test_none_to_active_in_one_case_write(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)
    embargo = _make_embargo(dl, case.id_)
    saved_states: list[EM] = []
    save = dl.save

    def recording_save(obj: Any) -> Any:
        if isinstance(obj, VulnerabilityCase):
            saved_states.append(obj.current_status.em.state)
        return save(obj)

    monkeypatch.setattr(dl, "save", recording_save)

    result = EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
        case_id=case.id_, embargo_id=embargo.id_, actor_id=owner.id_
    )

    # EM.PROPOSED is never handed to the store (EP-04-002).
    assert saved_states == [EM.ACTIVE]
    assert (result.em_before, result.em_after) == (EM.NONE, EM.ACTIVE)
    stored = _stored_case(dl, case.id_)
    assert stored.current_status.em.state == EM.ACTIVE
    assert stored.active_embargo_id == embargo.id_
    # Activation decides the proposal at once, so none is left open.
    assert stored.proposed_embargoes == []


def test_consent_matches_propose_then_activate(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """The proposer records its consent; every holder becomes SIGNATORY.

    Same effects as ``propose_embargo`` followed by ``activate_embargo``
    (ADR-0093, EP-05-001): a participant that did not propose is untouched.
    """
    owner, dl = owner_and_dl
    other = _make_actor(dl, "Finder")
    case, (owner_p, other_p) = _make_case(
        dl, owner.id_, extra_participant_ids=[other.id_]
    )
    embargo = _make_embargo(dl, case.id_)

    EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
        case_id=case.id_, embargo_id=embargo.id_, actor_id=owner.id_
    )

    assert _accepted_ids_of(dl, owner_p.id_) == [embargo.id_]
    assert _pec_of(dl, owner_p.id_) == PEC.SIGNATORY.value
    assert _accepted_ids_of(dl, other_p.id_) == []
    assert _pec_of(dl, other_p.id_) == PEC.UNBOUND.value


def test_a_proposer_with_no_participant_record_records_no_consent(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """The CASE_MANAGER on the creation path need not be a participant."""
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)
    embargo = _make_embargo(dl, case.id_)

    EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id="https://example.org/actors/not-a-participant",
    )

    assert _stored_case(dl, case.id_).active_embargo_id == embargo.id_
    owner_record = cast(CaseParticipant, dl.read(owner_p.id_))
    assert owner_record.accepted_embargo_ids == []


@pytest.mark.parametrize(
    "em_state", [state for state in EM if state != EM.NONE]
)
def test_a_case_that_has_left_none_is_refused_unchanged(
    owner_and_dl: tuple[as_Service, SqliteDataLayer], em_state: EM
) -> None:
    """Creation runs only from NONE — PROPOSE then ACCEPT is also legal from
    ACTIVE (via REVISE), so the machine alone would not refuse it."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_, em_state=em_state)
    embargo = _make_embargo(dl, case.id_)

    with pytest.raises(VultronInvalidStateTransitionError, match="not NONE"):
        EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
            case_id=case.id_, embargo_id=embargo.id_, actor_id=owner.id_
        )

    stored = _stored_case(dl, case.id_)
    assert stored.current_status.em.state == em_state
    assert stored.active_embargo_id is None


def test_a_none_case_with_an_attached_embargo_is_refused_unchanged(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Creation never replaces an attached embargo, even at NONE (CSB-16)."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)
    attached = _make_embargo(dl, case.id_)
    case.set_embargo(attached.id_)
    dl.save(case)
    embargo = _make_embargo(dl, case.id_)

    with pytest.raises(
        VultronInvalidStateTransitionError, match="already attached"
    ):
        EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
            case_id=case.id_, embargo_id=embargo.id_, actor_id=owner.id_
        )

    stored = _stored_case(dl, case.id_)
    assert stored.current_status.em.state == EM.NONE
    assert stored.active_embargo_id == attached.id_


def test_a_stale_proposed_listing_is_discarded_in_the_same_write(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Activation decides the proposal that carried the id (EP-08-003)."""
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)
    embargo = _make_embargo(dl, case.id_)
    case.proposed_embargoes.append(embargo.id_)
    dl.save(case)

    EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
        case_id=case.id_, embargo_id=embargo.id_, actor_id=owner.id_
    )

    stored = _stored_case(dl, case.id_)
    assert stored.active_embargo_id == embargo.id_
    assert stored.proposed_embargoes == []


@pytest.mark.spec("EMB-01-002")
def test_pxa_set_is_refused_before_any_write(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    owner, dl = owner_and_dl
    case, _ = _make_case(dl, owner.id_)
    case.append_case_status(pxa_state=CS_pxa.Pxa)
    dl.save(case)
    embargo = _make_embargo(dl, case.id_)

    with pytest.raises(VultronInvalidStateTransitionError):
        EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
            case_id=case.id_, embargo_id=embargo.id_, actor_id=owner.id_
        )

    _assert_untouched(dl, case.id_)


@pytest.mark.spec("EMB-18-003")
def test_an_unheld_embargo_is_refused_before_any_write(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    owner, dl = owner_and_dl
    case, (owner_p,) = _make_case(dl, owner.id_)

    with pytest.raises(VultronNotFoundError):
        EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
            case_id=case.id_, embargo_id=UNHELD_EMBARGO_ID, actor_id=owner.id_
        )

    _assert_untouched(dl, case.id_)
    assert _accepted_ids_of(dl, owner_p.id_) == []
