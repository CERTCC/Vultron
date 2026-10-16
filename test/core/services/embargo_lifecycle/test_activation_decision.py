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

"""The decide half of an activation: every change named, nothing written (#4716).

``EmbargoLifecycle.decide_activation`` returns the ``ACTIVATE`` step, the
owner's agreement its ``Accept`` states and one ``CARRY_OVER`` row per
signatory a shorter revision keeps (EP-05-001, MSM-07-008, ADR-0124).
"""

from typing import cast

import pytest

from test.support.embargo_register import (
    activate,
    propose,
    write_consent_rows,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.embargo_case_file import read_embargo_case_file
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_apply import (
    EmbargoCaseFile,
    RegisterStepKind,
)
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.core.services.embargo_lifecycle.activation_decision import (
    carry_over_changes,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronNotFoundError,
)

from .conftest import (
    UNHELD_EMBARGO_ID,
    _consents_of,
    _make_actor,
    _make_case,
    _make_embargo,
    _seed_consent,
)

_S = EmbargoConsentState


def _store() -> SqliteDataLayer:
    return SqliteDataLayer(
        "sqlite:///:memory:", actor_id="https://example.org/actors/manager"
    )


def _revising_case(dl: SqliteDataLayer, *, revision_days: int):
    """An active embargo every participant agreed to, and one revision."""
    owner = _make_actor(dl, "Owner")
    signatory = _make_actor(dl, "Signatory")
    case, participants = _make_case(dl, owner.id_, [signatory.id_])
    active = _make_embargo(dl, case.id_, days=60)
    revision = _make_embargo(dl, case.id_, days=revision_days)
    activate(case, active.id_)
    propose(case, revision.id_)
    dl.save(case)
    write_consent_rows(dl, case)
    for participant in participants:
        _seed_consent(dl, participant.id_, active.id_, _S.AGREED)
    return case, participants, active.id_, revision.id_


def _decide(dl: SqliteDataLayer, case_id: str, embargo_id: str):
    return EmbargoLifecycle(persistence=dl).decide_activation(
        read_embargo_case_file(dl, case_id), embargo_id
    )


@pytest.mark.spec("EP-05-001")
@pytest.mark.spec("MSM-07-008")
def test_a_shorter_revision_names_the_step_the_owner_and_each_carry_over():
    dl = _store()
    case, participants, _active, revision = _revising_case(
        dl, revision_days=30
    )
    owner_p, signatory_p = participants

    decision = _decide(dl, case.id_, revision)

    assert decision.step.kind is RegisterStepKind.ACTIVATE
    assert decision.step.embargo_id == revision
    assert decision.owner_agreement is not None
    assert decision.owner_agreement.actor_id == owner_p.attributed_to
    assert [c.actor_id for c in decision.carry_overs] == [
        signatory_p.attributed_to
    ]
    assert all(c.row.state is _S.AGREED for c in decision.consent_rows)
    assert (decision.em_before, decision.em_after) == (EM.REVISE, EM.ACTIVE)


@pytest.mark.spec("EP-05-001")
def test_a_longer_revision_carries_nobody_over():
    dl = _store()
    case, _participants, _active, revision = _revising_case(
        dl, revision_days=90
    )

    decision = _decide(dl, case.id_, revision)

    assert decision.carry_overs == ()
    assert decision.owner_agreement is not None


@pytest.mark.spec("CM-18-001")
def test_a_missing_row_for_the_replaced_embargo_raises():
    """Every register entry has a row on every participant (ADR-0122)."""
    dl = _store()
    case, participants, active, revision = _revising_case(dl, revision_days=30)
    case_file = read_embargo_case_file(dl, case.id_)
    signatory_id = participants[1].attributed_to
    assert signatory_id is not None
    signatory = case_file.participants[signatory_id]
    stripped = signatory.model_copy(
        update={
            "embargo_consents": [
                r for r in signatory.embargo_consents if r.embargo_id != active
            ]
        }
    )
    case_file = EmbargoCaseFile(
        case=case_file.case,
        participants={**case_file.participants, signatory_id: stripped},
    )

    with pytest.raises(VultronNotFoundError):
        carry_over_changes(
            case_file,
            previous_embargo_id=active,
            revised_embargo_id=revision,
        )


def test_the_decision_writes_nothing():
    dl = _store()
    case, participants, _active, revision = _revising_case(
        dl, revision_days=30
    )
    before_case = cast(VulnerabilityCase, dl.read(case.id_)).model_dump()
    before_rows = [_consents_of(dl, p.id_) for p in participants]

    _decide(dl, case.id_, revision)

    assert (
        cast(VulnerabilityCase, dl.read(case.id_)).model_dump() == before_case
    )
    assert [_consents_of(dl, p.id_) for p in participants] == before_rows


@pytest.mark.spec("MSM-07-008")
def test_an_embargo_that_is_not_an_open_proposal_is_refused():
    dl = _store()
    case, _participants, active, _revision = _revising_case(
        dl, revision_days=30
    )

    with pytest.raises(VultronInvalidStateTransitionError):
        _decide(dl, case.id_, active)


@pytest.mark.spec("EMB-02-002")
def test_pxa_set_is_refused():
    dl = _store()
    case, _participants, _active, revision = _revising_case(
        dl, revision_days=30
    )
    stored = cast(VulnerabilityCase, dl.read(case.id_))
    stored.current_status.pxa.state = CS_pxa.Pxa
    dl.save(stored)

    with pytest.raises(VultronInvalidStateTransitionError):
        _decide(dl, case.id_, revision)


@pytest.mark.spec("EMB-18-003")
def test_an_unreadable_activated_embargo_is_refused():
    dl = _store()
    owner = _make_actor(dl, "Owner")
    case, _participants = _make_case(dl, owner.id_)
    propose(case, UNHELD_EMBARGO_ID)
    dl.save(case)
    write_consent_rows(dl, case)

    with pytest.raises(VultronNotFoundError):
        _decide(dl, case.id_, UNHELD_EMBARGO_ID)
