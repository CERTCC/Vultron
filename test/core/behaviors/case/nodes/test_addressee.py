#!/usr/bin/env python

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

"""The addressee door guard of every received tree (HP-01-005, CLP-10-010).

"Addressed to the receiver" has one definition: the receiver sent the
activity, is named in its ``to``, or belongs to a case participants
collection its ``to`` names.  ``cc`` is never read (ADR-0109).  The factory
places the guard in every received tree between the post-close boundary and
the sender guard, unless the tree passes a registered exemption.
"""

from unittest.mock import MagicMock

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.addressee import (
    ADDRESSEE_EXEMPTIONS,
    OFFER_REPORT_STORED_FIRST,
    ActivityAddressedToReceiverNode,
    AddresseeExemption,
    addressed_to_receiver,
    named_in_to,
    unaddressed_copy_reason,
)
from vultron.core.behaviors.case.nodes.post_close import (
    CaseOpenToExternalWritesNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.behaviors.sender_guard import SenderCheckContext
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.predicates.addressing import (
    participants_collection_case_id,
)
from vultron.errors import VultronWiringError

_CASE = "https://example.org/cases/addressee"
_OTHER_CASE = "https://example.org/cases/other"
_MANAGER = "https://example.org/users/coord"
_SENDER = "https://example.org/users/vendor"
_OTHER = "https://example.org/users/vendor-a"
_BYSTANDER = "https://example.org/users/vendor-b"
_COLLECTION = f"{_CASE}/participants"


def _event(to: list[str], cc: list[str] | None = None) -> MagicMock:
    event = MagicMock()
    event.actor_id = _SENDER
    event.activity_id = f"{_CASE}/activities/a2"
    event.activity.to = to
    event.activity.cc = cc or []
    return event


def _store(
    actor_id: str,
    *,
    members: tuple[str, ...] = (),
    removed: tuple[str, ...] = (),
) -> SqliteDataLayer:
    """*actor_id*'s store, holding ``_CASE`` with *members* as participants.

    A participant in *removed* carries the removal fact (CM-31-001): it stays
    on the roster but is no longer an active participant (CM-10-004).
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
    case = VulnerabilityCase(id_=_CASE, attributed_to=_SENDER)
    for member in (*members, *removed):
        participant = CaseParticipant(attributed_to=member, context=_CASE)
        if member in removed:
            participant.record_removal(f"{_CASE}/activities/remove")
        case.add_participant(participant)
        dl.create(participant)
    dl.create(case)
    return dl


class TestParticipantsCollectionCaseId:
    @pytest.mark.parametrize(
        "address, case_id",
        [
            (_COLLECTION, _CASE),
            (f"{_COLLECTION}/", _CASE),
            (f"{_COLLECTION}/vendor", None),
            (_MANAGER, None),
            ("participants", None),
            ("", None),
        ],
        ids=[
            "collection",
            "trailing-slash",
            "a-participant",
            "an-actor",
            "bare-segment",
            "blank",
        ],
    )
    def test_names_the_case_of_a_participants_collection(
        self, address, case_id
    ):
        assert participants_collection_case_id(address) == case_id


class TestAddressedToReceiver:
    """The one definition every addressee check reads (HP-01-012)."""

    @pytest.mark.spec("HP-01-012")
    @pytest.mark.spec("HP-01-005")
    @pytest.mark.parametrize(
        "receiver, to",
        [
            (_SENDER, []),
            (f"{_SENDER}/", []),
            (_MANAGER, [_MANAGER]),
            (_MANAGER, [f"{_MANAGER}/"]),
            (_MANAGER, [_OTHER, _MANAGER]),
        ],
        ids=["sender", "sender-trailing-slash", "to", "to-slash", "to-many"],
    )
    def test_the_sender_and_each_recipient_are_addressed(self, receiver, to):
        assert addressed_to_receiver(
            _store(receiver), receiver, sender_id=_SENDER, to=to
        )

    @pytest.mark.spec("HP-01-005")
    @pytest.mark.parametrize(
        "to", [[_COLLECTION], [f"{_COLLECTION}/"]], ids=["plain", "slash"]
    )
    def test_a_member_of_the_participants_collection_is_addressed(self, to):
        dl = _store(_BYSTANDER, members=(_SENDER, _BYSTANDER))

        assert addressed_to_receiver(dl, _BYSTANDER, sender_id=_SENDER, to=to)

    @pytest.mark.spec("HP-01-005")
    def test_a_non_member_of_the_collection_is_not_addressed(self):
        dl = _store(_BYSTANDER, members=(_SENDER, _MANAGER))

        assert not addressed_to_receiver(
            dl, _BYSTANDER, sender_id=_SENDER, to=[_COLLECTION]
        )

    @pytest.mark.spec("HP-01-005")
    @pytest.mark.spec("CM-10-004")
    def test_a_removed_participant_is_not_a_member_of_the_collection(self):
        """The roster is not membership: a removed participant's copy of a
        collection-addressed activity is unaddressed (CM-31-002)."""
        dl = _store(_BYSTANDER, members=(_SENDER,), removed=(_BYSTANDER,))

        assert not addressed_to_receiver(
            dl, _BYSTANDER, sender_id=_SENDER, to=[_COLLECTION]
        )

    @pytest.mark.spec("HP-01-005")
    def test_a_collection_of_a_case_the_store_lacks_addresses_nobody(self):
        dl = _store(_BYSTANDER, members=(_BYSTANDER,))

        assert not addressed_to_receiver(
            dl,
            _BYSTANDER,
            sender_id=_SENDER,
            to=[f"{_OTHER_CASE}/participants"],
        )

    @pytest.mark.spec("HP-09-001")
    def test_the_to_half_does_not_admit_the_sender(self):
        """An ``Offer(Report)`` reads only the ``to`` half (HP-09-001)."""
        dl = _store(_SENDER)

        assert addressed_to_receiver(
            dl, _SENDER, sender_id=_SENDER, to=[_MANAGER]
        )
        assert not named_in_to(dl, _SENDER, [_MANAGER])
        assert named_in_to(dl, _SENDER, [_SENDER])

    @pytest.mark.spec("HP-01-005")
    def test_an_unaddressed_copy_is_not_addressed(self):
        assert not addressed_to_receiver(
            _store(_BYSTANDER), _BYSTANDER, sender_id=_SENDER, to=[_MANAGER]
        )

    @pytest.mark.spec("HP-01-005")
    def test_an_empty_to_addresses_nobody_but_the_sender(self):
        dl = _store(_BYSTANDER)

        assert not addressed_to_receiver(
            dl, _BYSTANDER, sender_id=_SENDER, to=[]
        )
        assert not addressed_to_receiver(dl, _BYSTANDER, sender_id=None, to=[])


class TestUnaddressedCopyReason:
    @pytest.mark.spec("HP-01-005")
    @pytest.mark.parametrize(
        "receiver, to",
        [
            (_SENDER, []),
            (_MANAGER, [_MANAGER]),
            (_MANAGER, [f"{_MANAGER}/"]),
        ],
        ids=["sender", "to", "trailing-slash"],
    )
    def test_admits_the_sender_and_each_recipient(self, receiver, to):
        assert (
            unaddressed_copy_reason(
                _store(receiver), receiver, _event(to), label="Test"
            )
            is None
        )

    @pytest.mark.spec("HP-01-005")
    @pytest.mark.spec("OX-08-001")
    def test_a_cc_value_does_not_make_a_recipient(self):
        """Only ``to`` addresses a Vultron recipient (ADR-0109)."""
        reason = unaddressed_copy_reason(
            _store(_MANAGER),
            _MANAGER,
            _event([_OTHER], [_MANAGER]),
            label="Test",
        )
        assert reason is not None
        assert "cc=" not in reason

    @pytest.mark.spec("HP-01-005")
    def test_a_cc_of_the_collection_does_not_make_a_member_a_recipient(self):
        dl = _store(_BYSTANDER, members=(_BYSTANDER,))

        reason = unaddressed_copy_reason(
            dl, _BYSTANDER, _event([_MANAGER], [_COLLECTION]), label="Test"
        )

        assert reason is not None

    @pytest.mark.spec("HP-01-005")
    def test_refuses_an_event_with_no_activity(self):
        event = _event([])
        event.activity = None
        reason = unaddressed_copy_reason(
            _store(_BYSTANDER), _BYSTANDER, event, label="Test"
        )
        assert reason is not None
        assert "(to=[])" in reason

    @pytest.mark.spec("HP-01-005")
    def test_the_reason_names_the_receiver_the_activity_and_its_to(self):
        reason = unaddressed_copy_reason(
            _store(_BYSTANDER),
            _BYSTANDER,
            _event([_MANAGER]),
            label="RemoveEmbargoFromCaseBT",
        )
        assert reason == (
            f"'{_BYSTANDER}' is neither the sender nor a recipient of"
            f" RemoveEmbargoFromCaseBT '{_CASE}/activities/a2'"
            f" (to=['{_MANAGER}']); an unaddressed copy is refused (HP-01-005)"
        )


def _run(
    event: object, actor_id: str, dl: SqliteDataLayer | None = None
) -> ActivityAddressedToReceiverNode:
    node = ActivityAddressedToReceiverNode(label="Test")
    tree = py_trees.composites.Sequence(
        name="Probe", memory=False, children=[node]
    )
    BTBridge(datalayer=dl or _store(actor_id)).execute_with_setup(
        tree=tree, actor_id=actor_id, activity=event
    )
    return node


class TestActivityAddressedToReceiverNode:
    @pytest.mark.spec("HP-01-005")
    def test_an_addressed_copy_passes(self):
        assert _run(_event([_MANAGER]), _MANAGER).status is Status.SUCCESS

    @pytest.mark.spec("HP-01-005")
    def test_a_copy_to_a_collection_holding_the_receiver_passes(self):
        dl = _store(_BYSTANDER, members=(_BYSTANDER,))

        node = _run(_event([_COLLECTION]), _BYSTANDER, dl)

        assert node.status is Status.SUCCESS

    @pytest.mark.spec("HP-01-005")
    def test_an_unaddressed_copy_fails_and_warns(self, caplog):
        with caplog.at_level("WARNING"):
            node = _run(_event([_MANAGER]), _BYSTANDER)

        assert node.status is Status.FAILURE
        assert "neither the sender nor a recipient" in node.feedback_message
        assert any(
            r.levelname == "WARNING" and _BYSTANDER in r.getMessage()
            for r in caplog.records
        )


@pytest.mark.spec("CLP-10-010")
@pytest.mark.spec("HP-01-005")
def test_the_factory_places_it_between_post_close_and_the_sender_guard():
    tree = create_receive_activity_tree(
        name="Probe",
        case_id=_CASE,
        sender_rule=SenderRule.in_case(SenderEntitlementKind.PARTICIPANT),
        sender_context=SenderCheckContext(sender_id=_SENDER, case_id=_CASE),
        precondition_guards=[],
    )

    assert isinstance(tree.children[1], CaseOpenToExternalWritesNode)
    assert isinstance(tree.children[2], ActivityAddressedToReceiverNode)
    assert tree.children[2].label == "Probe"
    assert tree.children[3].name == "SenderIsParticipantNode"
    assert tree.children[2] in tree.door_guards


@pytest.mark.spec("HP-01-005")
def test_the_factory_places_it_by_default_in_a_tree_with_no_case():
    tree = create_receive_activity_tree(
        name="Probe", case_id=None, precondition_guards=[]
    )

    guards = [
        n
        for n in tree.iterate()
        if isinstance(n, ActivityAddressedToReceiverNode)
    ]
    assert [g.label for g in guards] == ["Probe"]


@pytest.mark.spec("HP-01-005")
def test_a_registered_exemption_leaves_the_guard_out():
    tree = create_receive_activity_tree(
        name="Probe",
        case_id=None,
        precondition_guards=[],
        addressee_exemption=OFFER_REPORT_STORED_FIRST,
    )

    assert not [
        n
        for n in tree.iterate()
        if isinstance(n, ActivityAddressedToReceiverNode)
    ]


@pytest.mark.spec("HP-01-005")
def test_an_unregistered_exemption_is_refused_at_construction():
    rogue = AddresseeExemption(name="rogue", reason="no reason on record")

    with pytest.raises(VultronWiringError, match="not registered"):
        create_receive_activity_tree(
            name="Probe",
            case_id=None,
            precondition_guards=[],
            addressee_exemption=rogue,
        )


def test_a_lookalike_of_a_registered_exemption_is_refused():
    """The registry holds the decision itself, not just its name."""
    lookalike = AddresseeExemption(
        name=OFFER_REPORT_STORED_FIRST.name, reason="a different reason"
    )
    assert ADDRESSEE_EXEMPTIONS[lookalike.name] != lookalike

    with pytest.raises(VultronWiringError, match="not registered"):
        create_receive_activity_tree(
            name="Probe",
            case_id=None,
            precondition_guards=[],
            addressee_exemption=lookalike,
        )
