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

``Add(EmbargoEvent)[target=VulnerabilityCase]`` activates a proposal and
``Reject(EmbargoEvent)[target=VulnerabilityCase]`` rejects it.  The CASE_MANAGER applies
either only when it names an open proposal and nothing refuses it; a
refusal is decided before the commit, so nothing is ledgered for it
(CLP-10-009, SYNC-12-001).  The non-owner sender, door check and missing ids
are pinned in ``test_sender_entitlement.py``, ``test_embargo_door_check.py``
and ``test_embargo_disposition.py``.
"""

from typing import Any, cast

import pytest

from test.core.use_cases.received.conftest import (
    assert_only_refusal_notice,
    queued_bodies,
    refusal_notices_since,
    seed_case_manager_participant,
    seed_case_owner_participant,
)
from test.support.act_runner import run_in_act
from test.support.embargo_register import activate, propose
from test.support.owner_decision import (
    seeded_activation,
    seeded_proposal_rejection,
)
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
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

_CASE_ID = "https://example.org/cases/owner-decision"
_MANAGER = "https://example.org/users/coord"
_OWNER = "https://example.org/users/vendor"

_DECISIONS = [
    pytest.param(
        seeded_activation,
        ActivateEmbargoOnCaseReceivedUseCase,
        id="activate",
    ),
    pytest.param(
        seeded_proposal_rejection,
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
    # Both trees emit: the refusal notice (CLP-05-001), and after the
    # commit a termination or a re-issued stub Invite.
    ports: dict[str, Any] = {
        "sync_port": SyncActivityAdapter(dl),
        "wire_render_port": As2WireRenderAdapter(),
        "trigger_activity": TriggerActivityAdapter(dl),
    }
    event = make_payload(activity, receiving_actor_id=receiver, at=dl)
    return run_in_act(use_case(dl, event, **ports))


def _case(dl: SqliteDataLayer) -> VulnerabilityCase:
    return cast(VulnerabilityCase, dl.read(_CASE_ID))


def _owner(dl: SqliteDataLayer) -> CaseParticipant:
    participant = dl.read(_case(dl).actor_participant_index[_OWNER])
    assert isinstance(participant, CaseParticipant)
    return participant


def _ledger(dl: SqliteDataLayer) -> list[str]:
    return [
        str(entry.semantic_type)
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
        seeded_activation,
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


def _participant_states(dl: SqliteDataLayer) -> dict[str, list[tuple]]:
    """Each participant's RM and VFD status history, keyed by its actor."""
    states: dict[str, list[tuple]] = {}
    for actor_id, participant_id in _case(dl).actor_participant_index.items():
        participant = dl.read(participant_id)
        assert isinstance(participant, CaseParticipant)
        states[actor_id] = [
            (status.id_, status.rm.state, status.vf, status.d)
            for status in participant.participant_statuses
        ]
    return states


@pytest.mark.spec("CM-04-010")
def test_an_embargo_activation_changes_no_participant_state(make_payload):
    """An EM transition is case-level: no participant's RM or VFD moves."""
    dl, _case_obj, embargo = _store()
    before = _participant_states(dl)
    assert any(before.values()), "the seeded participants carry statuses"

    result = _receive(
        dl,
        make_payload,
        seeded_activation,
        ActivateEmbargoOnCaseReceivedUseCase,
        embargo,
    )

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    assert _case(dl).em_state == EM.ACTIVE
    assert _participant_states(dl) == before


@pytest.mark.spec("EP-09-005")
@pytest.mark.spec("EP-08-001")
@pytest.mark.parametrize(
    ("active", "em_after"),
    [(False, EM.NONE), (True, EM.ACTIVE)],
    ids=["er", "ej"],
)
@pytest.mark.spec("MSM-07-031")
def test_the_case_manager_applies_and_commits_the_owners_rejection(
    make_payload, active, em_after
):
    dl, _case_obj, embargo = _store(active=active)
    before = _owner(dl).embargo_consents

    result = _receive(
        dl,
        make_payload,
        seeded_proposal_rejection,
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
@pytest.mark.spec("MSM-07-029")
@pytest.mark.spec("MSM-07-033")
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
@pytest.mark.spec("MSM-07-029")
def test_an_activation_with_pxa_set_is_refused_uncommitted(make_payload):
    dl, _case_obj, embargo = _store()
    case = _case(dl)
    case.current_status.pxa.state = CS_pxa.Pxa
    dl.save(case)

    result = _receive(
        dl,
        make_payload,
        seeded_activation,
        ActivateEmbargoOnCaseReceivedUseCase,
        embargo,
    )

    assert result.disposition is HandlerDisposition.REFUSED
    assert "EMB-02-002" in (result.reason or "")
    assert _case(dl).em_state == EM.PROPOSED
    assert _ledger(dl) == []


@pytest.mark.spec("EMB-05-002")
@pytest.mark.spec("EMB-02-002")
@pytest.mark.parametrize(
    "pxa", [CS_pxa.Pxa, CS_pxa.pXa, CS_pxa.pxA], ids=["P", "X", "A"]
)
def test_an_accepted_revision_with_pxa_set_is_refused_without_et(
    make_payload, pxa
):
    """The owner's EC of a revision after P/X/A changes nothing.

    The CASE_MANAGER refuses the activation before committing it and emits
    no ET: the embargo in force and the open revision stay as they were,
    since the P/X/A teardown ends the embargo (RSH-03-001).
    """
    dl, _case_obj, embargo = _store(active=True)
    case = _case(dl)
    prior_id = case.active_embargo_id
    assert case.em_state == EM.REVISE
    case.current_status.pxa.state = pxa
    dl.save(case)
    outbox_before = list(dl.outbox_list())

    result = _receive(
        dl,
        make_payload,
        seeded_activation,
        ActivateEmbargoOnCaseReceivedUseCase,
        embargo,
    )

    assert result.disposition is HandlerDisposition.REFUSED
    assert "EMB-02-002" in (result.reason or "")
    # Only the refusal notice is sent: no ET, and no announcement of an
    # activation (CLP-05-001).
    assert len(refusal_notices_since(dl, outbox_before, _OWNER)) == 1
    after = _case(dl)
    assert after.em_state == EM.REVISE
    assert after.active_embargo_id == prior_id
    assert after.proposed_embargo_ids == [embargo.id_]
    # No entry at all: neither the revision's activation nor a termination.
    assert _ledger(dl) == []


def _seed_owner_row(
    dl: SqliteDataLayer, embargo_id: str, triggers: list[PEC_Trigger]
) -> None:
    """Move the owner's row for *embargo_id* by *triggers*, in order."""
    owner = _owner(dl)
    entry_status = _case(dl).embargo_register_status(embargo_id)
    for trigger in triggers:
        owner.apply_pec_transition(
            embargo_id, trigger, entry_status=entry_status
        )
    dl.save(owner)


@pytest.mark.spec("MSM-07-037")
@pytest.mark.spec("CLP-05-001")
@pytest.mark.spec("CLP-10-009")
def test_an_activation_the_owner_declined_is_refused_uncommitted(
    make_payload,
):
    """An owner that declined a proposal accepts its Invite before activating.

    The activation would otherwise be both the case's decision and a change
    of the owner's own answer, so it is refused before the commit: nothing is
    ledgered, the embargo stays proposed, the owner's row stays DECLINED, and
    the one thing sent is the refusal notice, whose reason tells the owner to
    accept the invitation first (MSM-07-037, ADR-0180).
    """
    dl, _case_obj, embargo = _store()
    _seed_owner_row(dl, embargo.id_, [PEC_Trigger.DECLINE])
    register_before = _case(dl).embargo_register

    result = _receive(
        dl,
        make_payload,
        seeded_activation,
        ActivateEmbargoOnCaseReceivedUseCase,
        embargo,
    )

    assert result.disposition is HandlerDisposition.REFUSED, result.reason
    assert "MSM-07-037" in (result.reason or "")
    assert _case(dl).em_state == EM.PROPOSED
    assert _case(dl).proposed_embargo_ids == [embargo.id_]
    assert _case(dl).embargo_register == register_before
    assert _owner(dl).consent_for(embargo.id_) == EmbargoConsentState.DECLINED
    assert _ledger(dl) == []
    (queued,) = queued_bodies(dl)
    refused = queued["object"]
    assert isinstance(refused, dict)
    notice = assert_only_refusal_notice(dl, refused["id"], _OWNER)
    assert "Accept the invitation to the embargo first" in str(
        notice["summary"]
    )


@pytest.mark.spec("MSM-07-028")
@pytest.mark.parametrize(
    "triggers",
    [
        [],
        [PEC_Trigger.INVITE],
        [PEC_Trigger.INVITE, PEC_Trigger.TIME_OUT],
        [PEC_Trigger.AGREE],
    ],
    ids=["uninvited", "invited", "timed-out", "agreed"],
)
def test_an_activation_from_an_owner_that_gave_no_decline_is_admitted(
    make_payload, triggers
):
    """A row with no decline is admitted, and the owner's row ends AGREED.

    ``UNINVITED``, ``INVITED`` and ``TIMED_OUT`` hold no answer the owner
    gave, so the activation agrees for it; an ``AGREED`` row stays as it is
    (MSM-07-028).
    """
    dl, _case_obj, embargo = _store()
    _seed_owner_row(dl, embargo.id_, triggers)

    result = _receive(
        dl,
        make_payload,
        seeded_activation,
        ActivateEmbargoOnCaseReceivedUseCase,
        embargo,
    )

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    assert _case(dl).active_embargo_id == embargo.id_
    assert _owner(dl).consent_for(embargo.id_) == EmbargoConsentState.AGREED
    assert _ledger(dl) == ["activate_embargo_on_case"]


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
