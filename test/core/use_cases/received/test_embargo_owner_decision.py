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
"""The case owner's decision on an embargo proposal, received (ADR-0122).

``Accept(EmbargoEvent, target=Case)`` activates a proposal and
``Reject(EmbargoEvent, target=Case)`` rejects it.  The CASE_MANAGER applies
either only when it names an open proposal and nothing refuses it; a
refusal is decided before the commit, so nothing is ledgered for it
(CLP-10-009, SYNC-12-001).  The non-owner sender, door check and missing ids
are pinned in ``test_sender_entitlement.py``, ``test_embargo_door_check.py``
and ``test_embargo_disposition.py``.
"""

from typing import Any, cast

import pytest

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_owner_participant,
)
from test.support.embargo_register import activate, propose
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
    PEC_Trigger,
)
from vultron.core.use_cases.received.embargo import (
    ActivateEmbargoOnCaseReceivedUseCase,
    RejectEmbargoProposalOnCaseReceivedUseCase,
)
from vultron.wire.as2.factories import (
    activate_embargo_activity,
    reject_embargo_proposal_activity,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

_CASE_ID = "https://example.org/cases/owner-decision"
_MANAGER = "https://example.org/users/coord"
_OWNER = "https://example.org/users/vendor"

_DECISIONS = [
    pytest.param(
        activate_embargo_activity,
        ActivateEmbargoOnCaseReceivedUseCase,
        id="activate",
    ),
    pytest.param(
        reject_embargo_proposal_activity,
        RejectEmbargoProposalOnCaseReceivedUseCase,
        id="reject-proposal",
    ),
]


def _store(
    *, receiver: str = _MANAGER, proposed: bool = True, active: bool = False
) -> tuple[SqliteDataLayer, VulnerabilityCase, as_EmbargoEvent]:
    """*receiver*'s store of a case the vendor owns and the coordinator manages.

    *active* puts a prior embargo in force, so the proposal is a revision.
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=receiver)
    case = VulnerabilityCase(
        id_=_CASE_ID, name="Owner decision", attributed_to=_OWNER
    )
    embargo = as_EmbargoEvent(
        id_=f"{_CASE_ID}/embargo_events/proposal",
        context=_CASE_ID,
        end_time=days_from_now_utc(30),
    )
    if active:
        prior = as_EmbargoEvent(
            id_=f"{_CASE_ID}/embargo_events/prior",
            context=_CASE_ID,
            end_time=days_from_now_utc(60),
        )
        dl.create(prior)
        activate(case, prior.id_)
    if proposed:
        propose(case, embargo.id_)
    seed_case_manager_participant(dl, case, _MANAGER)
    seed_case_owner_participant(dl, case, _OWNER)
    dl.create(case)
    dl.create(embargo)
    return dl, case, embargo


def _receive(
    dl: SqliteDataLayer,
    make_payload: Any,
    factory: Any,
    use_case: Any,
    embargo: as_EmbargoEvent,
    *,
    receiver: str = _MANAGER,
):
    activity = factory(embargo, target=_CASE_ID, actor=_OWNER, to=[receiver])
    ports: dict[str, Any] = {
        "sync_port": SyncActivityAdapter(dl),
        "wire_render_port": As2WireRenderAdapter(),
    }
    if use_case is RejectEmbargoProposalOnCaseReceivedUseCase:
        ports["trigger_activity"] = TriggerActivityAdapter(dl)
    event = make_payload(activity, receiving_actor_id=receiver)
    return use_case(dl, event, **ports).execute()


def _case(dl: SqliteDataLayer) -> VulnerabilityCase:
    return cast(VulnerabilityCase, dl.read(_CASE_ID))


def _owner(dl: SqliteDataLayer) -> CaseParticipant:
    participant = dl.read(_case(dl).actor_participant_index[_OWNER])
    assert isinstance(participant, CaseParticipant)
    return participant


def _ledger(dl: SqliteDataLayer) -> list[str]:
    return [
        str(entry.event_type)
        for entry in dl.list_objects("CaseLedgerEntry")
        if isinstance(entry, CaseLedgerEntry)
    ]


@pytest.mark.spec("EP-09-005")
@pytest.mark.spec("MSM-07-003")
@pytest.mark.parametrize("active", [False, True], ids=["first", "revision"])
def test_the_case_manager_applies_and_commits_the_owners_activation(
    make_payload, active
):
    dl, _case_obj, embargo = _store(active=active)

    result = _receive(
        dl,
        make_payload,
        activate_embargo_activity,
        ActivateEmbargoOnCaseReceivedUseCase,
        embargo,
    )

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    case = _case(dl)
    assert case.active_embargo_id == embargo.id_
    assert case.em_state == EM.ACTIVE
    assert case.proposed_embargo_ids == []
    # The activation is the owner's agreement (ADR-0122).
    assert _owner(dl).consent_for(embargo.id_) == EmbargoConsentState.AGREED
    assert _ledger(dl) == ["activate_embargo_on_case"]


@pytest.mark.spec("EP-09-005")
@pytest.mark.spec("EP-08-001")
@pytest.mark.parametrize(
    ("active", "em_after"),
    [(False, EM.NONE), (True, EM.ACTIVE)],
    ids=["er", "ej"],
)
def test_the_case_manager_applies_and_commits_the_owners_rejection(
    make_payload, active, em_after
):
    dl, _case_obj, embargo = _store(active=active)
    before = _owner(dl).embargo_consents

    result = _receive(
        dl,
        make_payload,
        reject_embargo_proposal_activity,
        RejectEmbargoProposalOnCaseReceivedUseCase,
        embargo,
    )

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    case = _case(dl)
    assert case.em_state == em_after
    assert case.proposed_embargo_ids == []
    # The owner's decision writes no consent, its own included (ADR-0122).
    assert _owner(dl).embargo_consents == before
    assert _ledger(dl) == ["reject_embargo_proposal_on_case"]


@pytest.mark.spec("CLP-10-009")
@pytest.mark.spec("SYNC-12-001")
@pytest.mark.parametrize(("factory", "use_case"), _DECISIONS)
def test_a_decision_naming_no_open_proposal_is_refused_uncommitted(
    make_payload, factory, use_case
):
    """The embargo in force is not an open proposal: nothing to decide."""
    dl, _case_obj, _embargo = _store(proposed=False, active=True)
    in_force_id = _case(dl).active_embargo_id
    assert in_force_id is not None
    in_force = cast(as_EmbargoEvent, dl.read(in_force_id))

    result = _receive(dl, make_payload, factory, use_case, in_force)

    assert result.disposition is HandlerDisposition.REFUSED
    assert "not an open proposal" in (result.reason or "")
    assert _case(dl).active_embargo_id == in_force.id_
    assert _ledger(dl) == []


@pytest.mark.spec("EMB-02-002")
@pytest.mark.spec("CLP-10-009")
def test_an_activation_with_pxa_set_is_refused_uncommitted(make_payload):
    dl, _case_obj, embargo = _store()
    case = _case(dl)
    case.current_status.pxa.state = CS_pxa.Pxa
    dl.save(case)

    result = _receive(
        dl,
        make_payload,
        activate_embargo_activity,
        ActivateEmbargoOnCaseReceivedUseCase,
        embargo,
    )

    assert result.disposition is HandlerDisposition.REFUSED
    assert "EMB-02-002" in (result.reason or "")
    assert _case(dl).em_state == EM.PROPOSED
    assert _ledger(dl) == []


@pytest.mark.spec("CM-18-003")
@pytest.mark.spec("CLP-10-009")
def test_an_activation_the_owner_declined_is_refused_uncommitted(
    make_payload,
):
    """An owner that declined the proposal is invited again first (ADR-0122)."""
    dl, _case_obj, embargo = _store()
    owner = _owner(dl)
    owner.apply_pec_transition(
        embargo.id_,
        PEC_Trigger.DECLINE,
        entry_status=_case(dl).embargo_register_status(embargo.id_),
    )
    dl.save(owner)

    result = _receive(
        dl,
        make_payload,
        activate_embargo_activity,
        ActivateEmbargoOnCaseReceivedUseCase,
        embargo,
    )

    assert result.disposition is HandlerDisposition.REFUSED
    assert "declined" in (result.reason or "")
    assert _case(dl).em_state == EM.PROPOSED
    assert _owner(dl).consent_for(embargo.id_) == EmbargoConsentState.DECLINED
    assert _ledger(dl) == []


@pytest.mark.spec("BT-17-001")
@pytest.mark.spec("HP-01-005")
@pytest.mark.parametrize(("factory", "use_case"), _DECISIONS)
def test_a_non_manager_receiver_applies_nothing(
    make_payload, factory, use_case
):
    """Only the CASE_MANAGER applies the decision; a replica replays it."""
    bystander = "https://example.org/users/vendor-b"
    dl, _case_obj, embargo = _store(receiver=bystander)

    result = _receive(
        dl, make_payload, factory, use_case, embargo, receiver=bystander
    )

    assert result.disposition is HandlerDisposition.REFUSED
    case = _case(dl)
    assert case.em_state == EM.PROPOSED
    assert case.proposed_embargo_ids == [embargo.id_]
    assert _ledger(dl) == []
