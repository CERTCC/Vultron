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
which commits the answer and, on an Accept, grants the role.
"""

from typing import Any
from unittest.mock import MagicMock

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
from vultron.core.models._helpers import _as_id
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
from vultron.errors import VultronBTInternalError
from vultron.wire.as2.factories import (
    accept_case_participant_role_activity,
    offer_case_participant_role_activity,
    reject_case_participant_role_activity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.case_participant_role import (
    as_CaseParticipantRole,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_CASE_ID = "https://example.org/cases/role-offer-routing"
_CASE_MANAGER_ID = "https://example.org/actors/case-actor"
_OWNER_ID = "https://example.org/users/vendor"
_TARGET_ID = "https://example.org/users/finder"
_BYSTANDER_ID = "https://example.org/users/coordinator"
_OFFER_ID = "https://example.org/activities/role-offer"
_FORWARD_ID = "https://example.org/activities/role-offer/forward"


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
    offer_id: str = _OFFER_ID,
) -> Any:
    return offer_case_participant_role_activity(
        role=role,
        target_actor=as_Actor(id_=target),
        case=_CASE_ID,
        actor=sender,
        to=[to],
        id_=offer_id,
    )


def _forward() -> Any:
    """The CASE_MANAGER's forward of the Case Owner's Offer to the target."""
    return offer_case_participant_role_activity(
        role=CVDRole.VENDOR,
        target_actor=as_Actor(id_=_TARGET_ID),
        case=_CASE_ID,
        actor=_CASE_MANAGER_ID,
        attributed_to=_OWNER_ID,
        to=[_TARGET_ID],
        in_reply_to=_OFFER_ID,
        id_=_FORWARD_ID,
    )


def _ports(dl: SqliteDataLayer) -> dict[str, Any]:
    return {
        "wire_render_port": As2WireRenderAdapter(),
        "sync_port": SyncActivityAdapter(dl),
    }


def _deliver_offer(
    dl: SqliteDataLayer, make_payload, offer: Any, *, drop_role: bool = False
) -> Any:
    """Deliver *offer*; with *drop_role* its ``CaseParticipantRole`` has no role.

    The factory cannot build a role-less Offer, so the role object is rebuilt
    without its ``role`` after extraction: the shape a peer could send.
    """
    request = make_payload(offer, receiving_actor_id=dl.actor_id)
    if drop_role:
        role_obj = request.activity.object_
        request = request.model_copy(
            update={
                "activity": request.activity.model_copy(
                    update={
                        "object_": as_CaseParticipantRole.model_construct(
                            id_=role_obj.id_
                        )
                    }
                )
            }
        )
    return OfferCaseParticipantRoleReceivedUseCase(
        dl,
        request,
        trigger_activity=TriggerActivityAdapter(dl),
        **_ports(dl),
    ).execute()


def _deliver_answer(
    dl: SqliteDataLayer,
    make_payload,
    offer: Any,
    *,
    accept: bool,
    sender: str,
    answer_id: str | None = None,
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
    extra = {} if answer_id is None else {"id_": answer_id}
    answer = build(offer=offer, actor=sender, to=[_CASE_MANAGER_ID], **extra)
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


def _forwards(dl: SqliteDataLayer) -> list[Any]:
    """Queued Offers to the target that reply to the Case Owner's Offer."""
    return [
        item
        for item in _queued(dl)
        if _type_of(item) == "Offer"
        and getattr(item, "to", None) == [_TARGET_ID]
        and _as_id(getattr(item, "in_reply_to", None)) == _OFFER_ID
    ]


def _target_holds(dl: SqliteDataLayer, role: CVDRole) -> bool:
    case = dl.read_case(_CASE_ID)
    assert case is not None
    participant = dl.read(case.actor_participant_index[_TARGET_ID])
    assert isinstance(participant, CaseParticipant)
    return participant.has_role(role)


@pytest.mark.spec("CM-33-001")
def test_case_manager_records_and_forwards_the_offer(make_payload):
    """The Offer is ledgered and forwarded; nothing is granted until Accept."""
    dl = _store(_CASE_MANAGER_ID)

    _deliver_offer(dl, make_payload, _offer())

    forwards = _forwards(dl)
    assert len(forwards) == 1
    # Delegated authorship (CM-24-005): the CASE_MANAGER forwards, on the
    # Case Owner's behalf.
    assert _as_id(getattr(forwards[0], "actor", None)) == _CASE_MANAGER_ID
    assert _as_id(getattr(forwards[0], "attributed_to", None)) == _OWNER_ID
    assert "offer_case_participant_role" in _event_types(dl)
    assert not _target_holds(dl, CVDRole.VENDOR)


@pytest.mark.spec("CM-33-001")
def test_case_manager_forwards_to_the_target_only_and_answers_nothing(
    make_payload,
):
    """The forward names the recorded Offer; the CM does not answer for it."""
    dl = _store(_CASE_MANAGER_ID)

    result = _deliver_offer(dl, make_payload, _offer())

    assert result.disposition is HandlerDisposition.APPLIED
    (forward,) = _queued_offers(dl)
    assert forward.to == [_TARGET_ID]
    assert _as_id(forward.in_reply_to) == _OFFER_ID
    assert not [
        item for item in _queued(dl) if _type_of(item) in ("Accept", "Reject")
    ]


@pytest.mark.spec("HP-01-003")
@pytest.mark.spec("OX-06-002")
def test_redelivered_offer_is_skipped_with_no_second_entry_or_forward(
    make_payload,
):
    """Each delivery is built afresh, as a peer's retry would be."""
    dl = _store(_CASE_MANAGER_ID)
    _deliver_offer(dl, make_payload, _offer())
    entries = _event_types(dl)
    forwards = _queued_offers(dl)

    result = _deliver_offer(dl, make_payload, _offer())

    assert result.disposition is HandlerDisposition.SKIPPED
    assert _event_types(dl) == entries
    assert _queued_offers(dl) == forwards


@pytest.mark.spec("HP-01-003")
def test_a_redelivery_after_the_forward_was_sent_sends_nothing(make_payload):
    """Delivery drained the outbox; the forward is not sent again."""
    dl = _store(_CASE_MANAGER_ID)
    _deliver_offer(dl, make_payload, _offer())
    while dl.outbox_pop() is not None:
        pass
    entries = _event_types(dl)

    result = _deliver_offer(dl, make_payload, _offer())

    assert result.disposition is HandlerDisposition.SKIPPED
    assert _event_types(dl) == entries
    assert dl.outbox_list() == []


@pytest.mark.spec("ID-02-001")
@pytest.mark.spec("CM-33-003")
@pytest.mark.parametrize(
    "changed",
    [
        pytest.param({"role": CVDRole.COORDINATOR}, id="another-role"),
        pytest.param({"target": _BYSTANDER_ID}, id="another-target"),
        pytest.param({"target": _CASE_MANAGER_ID}, id="the-case-manager"),
    ],
)
def test_an_offer_reusing_a_recorded_id_for_another_offer_is_refused(
    make_payload, changed
):
    """Only the same role and target make it a redelivery."""
    dl = _store(_CASE_MANAGER_ID)
    _deliver_offer(dl, make_payload, _offer())
    entries = _event_types(dl)
    queued = dl.outbox_list()

    result = _deliver_offer(dl, make_payload, _offer(**changed))

    assert result.disposition is HandlerDisposition.REFUSED
    assert _event_types(dl) == entries
    assert dl.outbox_list() == queued


@pytest.mark.spec("HP-01-003")
@pytest.mark.spec("CLP-10-006")
def test_a_forward_that_fails_after_the_commit_is_sent_on_redelivery(
    make_payload,
):
    """The fault is ours, not a refusal; the redelivery finishes the forward."""
    dl = _store(_CASE_MANAGER_ID)
    offer = _offer()
    broken = MagicMock(wraps=TriggerActivityAdapter(dl))
    broken.offer_case_participant_role.side_effect = RuntimeError("down")

    with pytest.raises(VultronBTInternalError):
        OfferCaseParticipantRoleReceivedUseCase(
            dl,
            make_payload(offer, receiving_actor_id=dl.actor_id),
            trigger_activity=broken,
            **_ports(dl),
        ).execute()
    assert _event_types(dl) == ["offer_case_participant_role"]
    assert _forwards(dl) == []

    result = _deliver_offer(dl, make_payload, offer)

    assert result.disposition is HandlerDisposition.SKIPPED
    assert _event_types(dl) == ["offer_case_participant_role"]
    assert len(_forwards(dl)) == 1


@pytest.mark.spec("HP-01-005")
def test_a_copy_not_addressed_to_the_receiver_is_refused(make_payload):
    """The CASE_MANAGER holds a copy of an Offer sent to someone else."""
    dl = _store(_CASE_MANAGER_ID)

    result = _deliver_offer(dl, make_payload, _offer(to=_TARGET_ID))

    assert result.disposition is HandlerDisposition.REFUSED
    assert _event_types(dl) == []
    assert _queued(dl) == []
    assert dl.read(_OFFER_ID) is None


@pytest.mark.spec("CM-33-003")
@pytest.mark.spec("BT-17-008")
def test_offer_naming_the_case_manager_as_target_is_refused(make_payload):
    """The CASE_MANAGER would forward the Offer to itself."""
    dl = _store(_CASE_MANAGER_ID)

    result = _deliver_offer(
        dl, make_payload, _offer(role=CVDRole.VENDOR, target=_CASE_MANAGER_ID)
    )

    assert result.disposition is HandlerDisposition.REFUSED
    assert _event_types(dl) == []
    assert _queued(dl) == []


@pytest.mark.spec("CM-33-004")
def test_an_addressee_that_is_not_the_target_does_not_answer(make_payload):
    """A CASE_MANAGER-sent Offer naming another target is not answered."""
    dl = _store(_BYSTANDER_ID)
    offer = offer_case_participant_role_activity(
        role=CVDRole.VENDOR,
        target_actor=as_Actor(id_=_TARGET_ID),
        case=_CASE_ID,
        actor=_CASE_MANAGER_ID,
        attributed_to=_OWNER_ID,
        to=[_BYSTANDER_ID],
        in_reply_to=_OFFER_ID,
        id_=_FORWARD_ID,
    )

    result = _deliver_offer(dl, make_payload, offer)

    assert result.disposition is HandlerDisposition.REFUSED
    assert _queued(dl) == []


@pytest.mark.spec("CM-33-003")
@pytest.mark.parametrize(
    "dropped",
    [
        pytest.param("context", id="no-case"),
        pytest.param("target", id="no-target"),
    ],
)
def test_offer_naming_no_case_or_no_target_is_refused(make_payload, dropped):
    """Only intake's archive keeps it: no entry, no forward (CLP-10-018)."""
    dl = _store(_CASE_MANAGER_ID)
    request = make_payload(_offer(), receiving_actor_id=dl.actor_id)
    request = request.model_copy(
        update={
            "activity": request.activity.model_copy(update={dropped: None})
        }
    )

    result = OfferCaseParticipantRoleReceivedUseCase(
        dl,
        request,
        trigger_activity=TriggerActivityAdapter(dl),
        **_ports(dl),
    ).execute()

    assert result.disposition is HandlerDisposition.REFUSED
    assert _event_types(dl) == []
    assert _queued(dl) == []


def _queued_offers(dl: SqliteDataLayer) -> list[Any]:
    return [item for item in _queued(dl) if _type_of(item) == "Offer"]


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


@pytest.mark.spec("CM-33-003")
@pytest.mark.parametrize(
    ("role", "target"),
    [
        pytest.param(None, _TARGET_ID, id="missing-role"),
        pytest.param(CVDRole.CASE_MANAGER, _TARGET_ID, id="case-manager"),
        pytest.param(CVDRole.CASE_OWNER, _TARGET_ID, id="case-owner"),
        pytest.param(CVDRole.REPORTER, _TARGET_ID, id="role-already-held"),
        pytest.param(
            CVDRole.VENDOR,
            "https://example.org/users/stranger",
            id="target-not-a-participant",
        ),
    ],
)
def test_offer_the_case_manager_must_refuse(make_payload, role, target):
    """Each refused shape leaves no entry and sends nothing.

    A missing role must not be read as any default role, as the received use
    case once read it as CASE_MANAGER.
    """
    dl = _store(_CASE_MANAGER_ID)

    result = _deliver_offer(
        dl,
        make_payload,
        _offer(role=role or CVDRole.VENDOR, target=target),
        drop_role=role is None,
    )

    assert result.disposition is HandlerDisposition.REFUSED
    assert _event_types(dl) == []
    assert _queued(dl) == []


@pytest.mark.spec("CM-33-004")
def test_target_refuses_an_offer_not_sent_by_the_case_manager(make_payload):
    """The Case Owner's Offer reaches the target only as the CM's forward."""
    dl = _store(_TARGET_ID)

    result = _deliver_offer(dl, make_payload, _offer(to=_TARGET_ID))

    assert result.disposition is HandlerDisposition.REFUSED
    assert _queued(dl) == []


@pytest.mark.spec("CM-33-004")
def test_target_answers_the_forward_to_the_case_manager_only(make_payload):
    """The CASE_MANAGER's forward is acted on, and answered to it alone."""
    dl = _store(_TARGET_ID)

    result = _deliver_offer(dl, make_payload, _forward())

    assert result.disposition is HandlerDisposition.APPLIED
    answers = [
        item for item in _queued(dl) if _type_of(item) in ("Accept", "Reject")
    ]
    assert len(answers) == 1
    assert getattr(answers[0], "to", None) == [_CASE_MANAGER_ID]


@pytest.mark.spec("CM-33-005")
def test_accept_from_a_participant_that_is_not_the_target_is_refused(
    make_payload,
):
    """Only the actor offered the role may accept it."""
    dl = _store(_CASE_MANAGER_ID)
    offer = _offer()
    _deliver_offer(dl, make_payload, offer)
    entries_before = _event_types(dl)
    # The refusal must come from the sender check, not from a missing Offer.
    assert "offer_case_participant_role" in entries_before

    result = _deliver_answer(
        dl, make_payload, offer, accept=True, sender=_BYSTANDER_ID
    )

    assert result.disposition is HandlerDisposition.REFUSED
    assert "is not the target" in (result.reason or "")
    assert _event_types(dl) == entries_before
    assert not _target_holds(dl, CVDRole.VENDOR)


@pytest.mark.spec("CM-33-005")
def test_answer_to_an_offer_that_is_not_open_is_refused(make_payload):
    """A Reject after the target's Accept closed the Offer changes nothing."""
    dl = _store(_CASE_MANAGER_ID)
    offer = _offer()
    _deliver_offer(dl, make_payload, offer)
    _deliver_answer(dl, make_payload, offer, accept=True, sender=_TARGET_ID)
    entries_before = _event_types(dl)
    assert _target_holds(dl, CVDRole.VENDOR)

    result = _deliver_answer(
        dl, make_payload, offer, accept=False, sender=_TARGET_ID
    )

    assert result.disposition is HandlerDisposition.REFUSED
    assert "already closed" in (result.reason or "")
    assert _event_types(dl) == entries_before
    assert _target_holds(dl, CVDRole.VENDOR)


@pytest.mark.spec("CM-33-005")
@pytest.mark.spec("HP-01-003")
def test_redelivered_closing_answer_is_skipped(make_payload):
    """The answer that closed the Offer, delivered again, is a duplicate."""
    dl = _store(_CASE_MANAGER_ID)
    offer = _offer()
    _deliver_offer(dl, make_payload, offer)
    accepts_before = _event_types(dl).count("accept_case_participant_role")
    answer_id = "https://example.org/activities/role-offer/accept"
    _deliver_answer(
        dl,
        make_payload,
        offer,
        accept=True,
        sender=_TARGET_ID,
        answer_id=answer_id,
    )
    entries_after_first = _event_types(dl)
    assert (
        entries_after_first.count("accept_case_participant_role")
        == accepts_before + 1
    )

    result = _deliver_answer(
        dl,
        make_payload,
        offer,
        accept=True,
        sender=_TARGET_ID,
        answer_id=answer_id,
    )

    assert result.disposition is HandlerDisposition.SKIPPED
    assert _event_types(dl) == entries_after_first


@pytest.mark.spec("CM-33-005")
def test_answer_naming_the_forward_resolves_to_the_recorded_offer(
    make_payload,
):
    """The target answers the forward it received; it closes the Offer."""
    dl = _store(_CASE_MANAGER_ID)
    _deliver_offer(dl, make_payload, _offer())
    forwards = _forwards(dl)
    assert len(forwards) == 1
    entries_before = _event_types(dl)

    result = _deliver_answer(
        dl, make_payload, forwards[0], accept=True, sender=_TARGET_ID
    )

    assert result.disposition is HandlerDisposition.APPLIED
    assert (
        _event_types(dl).count("accept_case_participant_role")
        == entries_before.count("accept_case_participant_role") + 1
    )
    assert _target_holds(dl, CVDRole.VENDOR)


class TestAdmittedAnswerIsLedgered:
    """CM-33-006: the CASE_MANAGER commits and announces the target's answer."""

    @pytest.mark.spec("CM-33-006")
    @pytest.mark.spec("CLP-02-012")
    def test_accept_is_committed_granted_and_announced(self, make_payload):
        dl = _store(_CASE_MANAGER_ID)
        offer = _offer()
        _deliver_offer(dl, make_payload, offer)
        queued_before = dl.outbox_list()
        # The Offer step grants nothing and records no Accept: the change
        # below must come from the answer.
        assert "accept_case_participant_role" not in _event_types(dl)
        assert not _target_holds(dl, CVDRole.VENDOR)

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


def _holds(dl: SqliteDataLayer, actor_id: str, role: CVDRole) -> bool:
    case = dl.read_case(_CASE_ID)
    assert case is not None
    participant = dl.read(case.actor_participant_index[actor_id])
    assert isinstance(participant, CaseParticipant)
    return participant.has_role(role)


def _entries(dl: SqliteDataLayer, event_type: str) -> list[CaseLedgerEntry]:
    return [
        entry
        for entry in dl.list_objects("CaseLedgerEntry")
        if isinstance(entry, CaseLedgerEntry)
        and entry.event_type == event_type
    ]


@pytest.mark.spec("CM-33-005")
@pytest.mark.parametrize("accept", [True, False], ids=["accept", "reject"])
def test_answer_to_an_offer_never_recorded_is_refused(make_payload, accept):
    """No recorded Offer, so the sender has no standing to answer."""
    dl = _store(_CASE_MANAGER_ID)

    result = _deliver_answer(
        dl, make_payload, _offer(), accept=accept, sender=_TARGET_ID
    )

    assert result.disposition is HandlerDisposition.REFUSED
    assert "CM-33-005" in (result.reason or "")
    assert _event_types(dl) == []
    assert not _target_holds(dl, CVDRole.VENDOR)


@pytest.mark.spec("CM-33-005")
def test_reject_from_a_participant_that_is_not_the_target_is_refused(
    make_payload,
):
    """The Reject takes the Accept's sender rule."""
    dl = _store(_CASE_MANAGER_ID)
    offer = _offer()
    _deliver_offer(dl, make_payload, offer)
    entries_before = _event_types(dl)

    result = _deliver_answer(
        dl, make_payload, offer, accept=False, sender=_BYSTANDER_ID
    )

    assert result.disposition is HandlerDisposition.REFUSED
    assert _event_types(dl) == entries_before


@pytest.mark.spec("CM-33-005")
def test_accept_after_the_target_rejected_is_refused(make_payload):
    """The Reject closed the Offer, so a later Accept grants nothing."""
    dl = _store(_CASE_MANAGER_ID)
    offer = _offer()
    _deliver_offer(dl, make_payload, offer)
    _deliver_answer(dl, make_payload, offer, accept=False, sender=_TARGET_ID)
    entries_before = _event_types(dl)

    result = _deliver_answer(
        dl, make_payload, offer, accept=True, sender=_TARGET_ID
    )

    assert result.disposition is HandlerDisposition.REFUSED
    assert _event_types(dl) == entries_before
    assert not _target_holds(dl, CVDRole.VENDOR)


@pytest.mark.spec("CM-33-005")
@pytest.mark.spec("HP-01-003")
def test_redelivered_closing_reject_is_skipped(make_payload):
    dl = _store(_CASE_MANAGER_ID)
    offer = _offer()
    _deliver_offer(dl, make_payload, offer)
    answer_id = "https://example.org/activities/role-offer/reject"
    _deliver_answer(
        dl,
        make_payload,
        offer,
        accept=False,
        sender=_TARGET_ID,
        answer_id=answer_id,
    )
    entries_after_first = _event_types(dl)
    queued_after_first = dl.outbox_list()

    result = _deliver_answer(
        dl,
        make_payload,
        offer,
        accept=False,
        sender=_TARGET_ID,
        answer_id=answer_id,
    )

    assert result.disposition is HandlerDisposition.SKIPPED
    assert _event_types(dl) == entries_after_first
    assert dl.outbox_list() == queued_after_first


@pytest.mark.spec("CM-33-005")
def test_an_answer_closes_only_the_offer_it_answers(make_payload):
    """Two role Offers are open at once; one answer leaves the other open."""
    dl = _store(_CASE_MANAGER_ID)
    first = _offer()
    second = _offer(
        role=CVDRole.COORDINATOR,
        target=_BYSTANDER_ID,
        offer_id="https://example.org/activities/role-offer-2",
    )
    _deliver_offer(dl, make_payload, first)
    _deliver_offer(dl, make_payload, second)
    _deliver_answer(dl, make_payload, first, accept=True, sender=_TARGET_ID)

    result = _deliver_answer(
        dl, make_payload, second, accept=True, sender=_BYSTANDER_ID
    )

    assert result.disposition is HandlerDisposition.APPLIED
    assert _holds(dl, _TARGET_ID, CVDRole.VENDOR)
    assert _holds(dl, _BYSTANDER_ID, CVDRole.COORDINATOR)
    assert len(_entries(dl, "accept_case_participant_role")) == 2


@pytest.mark.spec("CM-33-005")
@pytest.mark.spec("CM-02-016")
def test_answer_carrying_an_offer_for_another_role_is_refused(make_payload):
    """The entry is what replicas grant from, so its copy must match."""
    dl = _store(_CASE_MANAGER_ID)
    _deliver_offer(dl, make_payload, _offer())
    entries_before = _event_types(dl)
    # Names the recorded Offer's id, but carries a role it never offered.
    forged = _offer(role=CVDRole.COORDINATOR)

    result = _deliver_answer(
        dl, make_payload, forged, accept=True, sender=_TARGET_ID
    )

    assert result.disposition is HandlerDisposition.REFUSED
    assert "carries an Offer naming role" in (result.reason or "")
    assert _event_types(dl) == entries_before
    assert not _target_holds(dl, CVDRole.COORDINATOR)


@pytest.mark.spec("CM-33-005")
def test_answer_naming_an_offer_no_forward_links_is_refused(make_payload):
    """An Offer the target made up, linking itself to the recorded one,
    stands for nothing: only the CASE_MANAGER's stored forward resolves."""
    dl = _store(_CASE_MANAGER_ID)
    _deliver_offer(dl, make_payload, _offer())
    entries_before = _event_types(dl)
    made_up = offer_case_participant_role_activity(
        role=CVDRole.VENDOR,
        target_actor=as_Actor(id_=_TARGET_ID),
        case=_CASE_ID,
        actor=_CASE_MANAGER_ID,
        to=[_TARGET_ID],
        in_reply_to=_OFFER_ID,
        id_="https://example.org/activities/role-offer/made-up",
    )

    result = _deliver_answer(
        dl, make_payload, made_up, accept=True, sender=_TARGET_ID
    )

    assert result.disposition is HandlerDisposition.REFUSED
    assert "never recorded" in (result.reason or "")
    assert _event_types(dl) == entries_before
    assert not _target_holds(dl, CVDRole.VENDOR)


@pytest.mark.spec("CM-33-004")
@pytest.mark.parametrize("accept", [True, False], ids=["accept", "reject"])
def test_a_participant_refuses_an_answer_sent_to_it(make_payload, accept):
    """The answer goes to the CASE_MANAGER only; no other store acts on it."""
    dl = _store(_OWNER_ID)
    answer = (
        accept_case_participant_role_activity
        if accept
        else reject_case_participant_role_activity
    )(offer=_forward(), actor=_TARGET_ID, to=[_OWNER_ID])
    use_case = (
        AcceptCaseParticipantRoleReceivedUseCase
        if accept
        else RejectCaseParticipantRoleReceivedUseCase
    )

    result = use_case(
        dl, make_payload(answer, receiving_actor_id=dl.actor_id), **_ports(dl)
    ).execute()

    assert result.disposition is HandlerDisposition.REFUSED
    assert "No sender is entitled" in (result.reason or "")
    assert _event_types(dl) == []
    assert not _target_holds(dl, CVDRole.VENDOR)


@pytest.mark.parametrize("accept", [True, False], ids=["accept", "reject"])
def test_answer_naming_no_case_is_refused(make_payload, accept):
    """Only intake's archive keeps it (CLP-10-018)."""
    dl = _store(_CASE_MANAGER_ID)
    answer = (
        accept_case_participant_role_activity
        if accept
        else reject_case_participant_role_activity
    )(offer=_offer(), actor=_TARGET_ID, to=[_CASE_MANAGER_ID])
    request = make_payload(answer, receiving_actor_id=dl.actor_id)
    request = request.model_copy(
        update={
            "activity": request.activity.model_copy(update={"context": None})
        }
    )
    use_case = (
        AcceptCaseParticipantRoleReceivedUseCase
        if accept
        else RejectCaseParticipantRoleReceivedUseCase
    )

    result = use_case(dl, request, **_ports(dl)).execute()

    assert result.disposition is HandlerDisposition.REFUSED
    assert _event_types(dl) == []


@pytest.mark.spec("CM-23-018")
@pytest.mark.spec("CM-33-005")
def test_a_target_that_left_the_case_cannot_answer(make_payload):
    """A target at RM CLOSED may answer nothing further."""
    from vultron.core.models.dimensions import RmDimension
    from vultron.core.models.participant_status import ParticipantStatus
    from vultron.core.states.rm import RM

    dl = _store(_CASE_MANAGER_ID)
    offer = _offer()
    _deliver_offer(dl, make_payload, offer)
    case = dl.read_case(_CASE_ID)
    assert case is not None
    record = dl.read(case.actor_participant_index[_TARGET_ID])
    assert isinstance(record, CaseParticipant)
    record.participant_statuses.append(
        ParticipantStatus(
            context=_CASE_ID,
            attributed_to=_TARGET_ID,
            rm=RmDimension(state=RM.CLOSED),
        )
    )
    dl.save(record)
    entries_before = _event_types(dl)

    result = _deliver_answer(
        dl, make_payload, offer, accept=True, sender=_TARGET_ID
    )

    assert result.disposition is HandlerDisposition.REFUSED
    assert "CM-23-018" in (result.reason or "")
    assert _event_types(dl) == entries_before
    assert not _target_holds(dl, CVDRole.VENDOR)


@pytest.mark.spec("CM-02-016")
@pytest.mark.spec("CM-33-006")
def test_the_committed_accept_carries_the_grant_replicas_apply(make_payload):
    """Replicas grant from the entry: it names the recorded role and target."""
    from vultron.core.behaviors.sync.nodes.role_grant_effect import (
        role_and_target_from_accept_snapshot,
    )

    dl = _store(_CASE_MANAGER_ID)
    _deliver_offer(dl, make_payload, _offer())
    (forward,) = _forwards(dl)

    _deliver_answer(dl, make_payload, forward, accept=True, sender=_TARGET_ID)

    (entry,) = _entries(dl, "accept_case_participant_role")
    assert role_and_target_from_accept_snapshot(entry.payload_snapshot) == (
        CVDRole.VENDOR,
        _TARGET_ID,
    )


@pytest.mark.spec("CM-33-005")
def test_open_offer_guard_flags_a_vanished_offer_as_internal(make_payload):
    """The sender check found the Offer, so its absence is a local fault."""
    from vultron.core.behaviors.bridge import BTBridge
    from vultron.core.behaviors.case.nodes.role_offer_guard import (
        RoleOfferOpenNode,
    )

    dl = _store(_CASE_MANAGER_ID)
    node = RoleOfferOpenNode(
        case_id=_CASE_ID,
        offer_id=_OFFER_ID,
        reply_id="https://example.org/activities/role-offer/accept",
        carried_role=CVDRole.VENDOR,
        carried_target_id=_TARGET_ID,
    )

    result = BTBridge(datalayer=dl).execute_with_setup(
        tree=node, actor_id=_CASE_MANAGER_ID
    )

    assert result.internal_error
