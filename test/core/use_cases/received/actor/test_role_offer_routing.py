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
"""A role Offer and its answer travel through the CASE_MANAGER (CM-33).

The Case Owner sends ``Offer(CaseParticipantRole)`` to the CASE_MANAGER, which
records it and forwards it to the target; the target answers the CASE_MANAGER,
which commits the answer and, on an Accept, grants the role.  None of this is
built yet, so each test is a strict ``xfail`` that fails for the reason its
requirement names.
"""

from typing import Any

import pytest

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_owner_participant,
    seed_case_participant,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.actor.accept_reject_case_participant_role import (
    AcceptCaseParticipantRoleReceivedUseCase,
    RejectCaseParticipantRoleReceivedUseCase,
)
from vultron.core.use_cases.received.actor.case_participant_role import (
    OfferCaseParticipantRoleReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    accept_case_participant_role_activity,
    offer_case_participant_role_activity,
    reject_case_participant_role_activity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_CASE_ID = "https://example.org/cases/role-offer-routing"
_CASE_MANAGER_ID = "https://example.org/actors/case-actor"
_OWNER_ID = "https://example.org/users/vendor"
_TARGET_ID = "https://example.org/users/finder"
_BYSTANDER_ID = "https://example.org/users/coordinator"
_OFFER_ID = "https://example.org/activities/role-offer"

_NOT_BUILT = "Tracked by #4672."


def _store(actor_id: str) -> SqliteDataLayer:
    """A store for *actor_id* holding the case and its four participants.

    The roster is the CASE_MANAGER, the vendor as Case Owner, the finder the
    role is offered to, and a coordinator that is neither.
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
    case = as_VulnerabilityCase(
        id_=_CASE_ID, name="Role offer routing", attributed_to=_OWNER_ID
    )
    seed_case_manager_participant(dl, case, _CASE_MANAGER_ID)
    seed_case_owner_participant(dl, case, _OWNER_ID)
    seed_case_participant(dl, case, _TARGET_ID)
    seed_case_participant(dl, case, _BYSTANDER_ID)
    dl.create(case)
    return dl


def _offer(
    role: CVDRole = CVDRole.VENDOR,
    sender: str = _OWNER_ID,
    target: str = _TARGET_ID,
    to: str = _CASE_MANAGER_ID,
) -> Any:
    return offer_case_participant_role_activity(
        role=role,
        target_actor=as_Actor(id_=target),
        case=_CASE_ID,
        actor=sender,
        to=[to],
        id_=_OFFER_ID,
    )


def _ports(dl: SqliteDataLayer) -> dict[str, Any]:
    return {
        "wire_render_port": As2WireRenderAdapter(),
        "sync_port": SyncActivityAdapter(dl),
    }


def _deliver_offer(dl: SqliteDataLayer, make_payload, offer: Any) -> Any:
    return OfferCaseParticipantRoleReceivedUseCase(
        dl,
        make_payload(offer, receiving_actor_id=dl.actor_id),
        trigger_activity=TriggerActivityAdapter(dl),
        **_ports(dl),
    ).execute()


def _deliver_answer(
    dl: SqliteDataLayer, make_payload, offer: Any, *, accept: bool, sender: str
) -> Any:
    build = (
        accept_case_participant_role_activity
        if accept
        else reject_case_participant_role_activity
    )
    use_case = (
        AcceptCaseParticipantRoleReceivedUseCase
        if accept
        else RejectCaseParticipantRoleReceivedUseCase
    )
    answer = build(offer=offer, actor=sender, to=[_CASE_MANAGER_ID])
    return use_case(
        dl, make_payload(answer, receiving_actor_id=dl.actor_id), **_ports(dl)
    ).execute()


def _event_types(dl: SqliteDataLayer) -> list[str]:
    return [
        entry.event_type
        for entry in dl.list_objects("CaseLedgerEntry")
        if isinstance(entry, CaseLedgerEntry)
    ]


def _queued(dl: SqliteDataLayer) -> list[Any]:
    return [dl.read(i) for i in dl.outbox_list()]


def _type_of(activity: Any) -> str | None:
    return getattr(getattr(activity, "type_", None), "value", None)


def _target_holds(dl: SqliteDataLayer, role: CVDRole) -> bool:
    case = dl.read_case(_CASE_ID)
    assert case is not None
    participant = dl.read(case.actor_participant_index[_TARGET_ID])
    assert isinstance(participant, CaseParticipant)
    return participant.has_role(role)


@pytest.mark.xfail(
    strict=True,
    reason=f"CM-33-001: the CASE_MANAGER accepts the Offer itself, on the"
    f" target's behalf, and grants the role on receipt. {_NOT_BUILT}",
)
@pytest.mark.spec("CM-33-001")
def test_case_manager_records_and_forwards_the_offer(make_payload):
    """The Offer is ledgered and forwarded; nothing is granted until Accept."""
    dl = _store(_CASE_MANAGER_ID)

    _deliver_offer(dl, make_payload, _offer())

    forwards = [
        item
        for item in _queued(dl)
        if _type_of(item) == "Offer"
        and getattr(item, "to", None) == [_TARGET_ID]
        and getattr(item, "in_reply_to", None) == _OFFER_ID
    ]
    assert len(forwards) == 1
    assert "offer_case_participant_role" in _event_types(dl)
    assert not _target_holds(dl, CVDRole.VENDOR)


@pytest.mark.xfail(
    strict=True,
    reason=f"CM-33-002: no sender check on a role Offer. {_NOT_BUILT}",
)
@pytest.mark.spec("CM-33-002")
def test_offer_from_a_participant_that_is_not_the_owner_is_refused(
    make_payload,
):
    """Only the Case Owner hands out roles."""
    dl = _store(_CASE_MANAGER_ID)

    result = _deliver_offer(dl, make_payload, _offer(sender=_BYSTANDER_ID))

    assert result.disposition is HandlerDisposition.REFUSED
    assert _event_types(dl) == []
    assert _queued(dl) == []


@pytest.mark.xfail(
    strict=True,
    reason=f"CM-33-003: a role Offer's role and target are not checked."
    f" {_NOT_BUILT}",
)
@pytest.mark.spec("CM-33-003")
@pytest.mark.parametrize(
    ("role", "target"),
    [
        pytest.param(CVDRole.CASE_MANAGER, _TARGET_ID, id="case-manager"),
        pytest.param(CVDRole.CASE_OWNER, _TARGET_ID, id="case-owner"),
        pytest.param(CVDRole.FINDER, _TARGET_ID, id="role-already-held"),
        pytest.param(
            CVDRole.VENDOR,
            "https://example.org/users/stranger",
            id="target-not-a-participant",
        ),
    ],
)
def test_offer_the_case_manager_must_refuse(make_payload, role, target):
    """Each refused shape leaves no entry and sends nothing."""
    dl = _store(_CASE_MANAGER_ID)

    result = _deliver_offer(dl, make_payload, _offer(role=role, target=target))

    assert result.disposition is HandlerDisposition.REFUSED
    assert _event_types(dl) == []
    assert _queued(dl) == []


@pytest.mark.xfail(
    strict=True,
    reason=f"CM-33-004: the target answers a role Offer from any sender."
    f" {_NOT_BUILT}",
)
@pytest.mark.spec("CM-33-004")
def test_target_refuses_an_offer_not_sent_by_the_case_manager(make_payload):
    """The Case Owner's Offer reaches the target only as the CM's forward."""
    dl = _store(_TARGET_ID)

    result = _deliver_offer(dl, make_payload, _offer(to=_TARGET_ID))

    assert result.disposition is HandlerDisposition.REFUSED
    assert _queued(dl) == []


@pytest.mark.xfail(
    strict=True,
    reason=f"CM-33-005: the answer has no sender check and is only stored."
    f" {_NOT_BUILT}",
)
@pytest.mark.spec("CM-33-005")
def test_accept_from_a_participant_that_is_not_the_target_is_refused(
    make_payload,
):
    """Only the actor offered the role may accept it."""
    dl = _store(_CASE_MANAGER_ID)
    offer = _offer()
    _deliver_offer(dl, make_payload, offer)
    entries_before = _event_types(dl)

    result = _deliver_answer(
        dl, make_payload, offer, accept=True, sender=_BYSTANDER_ID
    )

    assert result.disposition is HandlerDisposition.REFUSED
    assert _event_types(dl) == entries_before
    assert not _target_holds(dl, CVDRole.VENDOR)


class TestAdmittedAnswerIsLedgered:
    """CM-33-006: the CASE_MANAGER commits and announces the target's answer."""

    @pytest.mark.xfail(
        strict=True,
        reason=f"CM-33-006: the target's Accept is only stored, never"
        f" committed or announced. {_NOT_BUILT}",
    )
    @pytest.mark.spec("CM-33-006")
    @pytest.mark.spec("CLP-02-012")
    def test_accept_is_committed_granted_and_announced(self, make_payload):
        dl = _store(_CASE_MANAGER_ID)
        offer = _offer()
        _deliver_offer(dl, make_payload, offer)
        queued_before = dl.outbox_list()

        _deliver_answer(
            dl, make_payload, offer, accept=True, sender=_TARGET_ID
        )

        assert "accept_case_participant_role" in _event_types(dl)
        assert _target_holds(dl, CVDRole.VENDOR)
        assert any(
            _type_of(dl.read(i)) == "Announce"
            for i in dl.outbox_list()
            if i not in queued_before
        )

    @pytest.mark.xfail(
        strict=True,
        reason=f"CM-33-006: the target's Reject is only stored; the"
        f" CASE_MANAGER has already accepted for it. {_NOT_BUILT}",
    )
    @pytest.mark.spec("CM-33-006")
    @pytest.mark.spec("CLP-02-012")
    def test_reject_is_committed_and_announced_with_no_grant(
        self, make_payload
    ):
        dl = _store(_CASE_MANAGER_ID)
        offer = _offer()
        _deliver_offer(dl, make_payload, offer)
        queued_before = dl.outbox_list()

        _deliver_answer(
            dl, make_payload, offer, accept=False, sender=_TARGET_ID
        )

        assert "reject_case_participant_role" in _event_types(dl)
        assert not _target_holds(dl, CVDRole.VENDOR)
        assert any(
            _type_of(dl.read(i)) == "Announce"
            for i in dl.outbox_list()
            if i not in queued_before
        )
