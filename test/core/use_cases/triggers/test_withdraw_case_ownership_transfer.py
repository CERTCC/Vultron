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
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Tests for ``SvcWithdrawCaseOwnershipTransferUseCase`` (TRIG-11-006).

The Case Owner withdraws an ownership-transfer Offer it made: the trigger
emits ``Undo(Offer(VulnerabilityCase))`` from the owner, addressed to the
case's CASE_MANAGER (CM-21-015), and queues it in the owner's own outbox.
What the CASE_MANAGER does with it (admit only from the offerer of an open
Offer, ledger it, close the Offer) is tested with the received use case in
``test/core/use_cases/received/actor/test_ownership.py``.
"""

from typing import Any
from unittest.mock import MagicMock

import pytest

from test.support.trigger_results import activity_of
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.use_cases.triggers.actor import (
    SvcWithdrawCaseOwnershipTransferUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    WithdrawCaseOwnershipTransferTriggerRequest,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronNotFoundError
from vultron.wire.as2.factories.case import (
    offer_case_ownership_transfer_activity,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)


def _seed_case(dl: Any, owner_id: str, case_manager_id: str):
    """A case owned by *owner_id* and managed by *case_manager_id*."""
    case = as_VulnerabilityCase(
        attributed_to=owner_id, name="Withdraw Case", content="Content"
    )
    for actor_id, role in (
        (owner_id, CVDRole.CASE_OWNER),
        (case_manager_id, CVDRole.CASE_MANAGER),
    ):
        participant = as_CaseParticipant(
            attributed_to=actor_id, context=case.id_, case_roles=[role]
        )
        case.actor_participant_index[actor_id] = participant.id_
        case.case_participants.append(participant.id_)
        dl.create(participant)
    dl.create(case)
    return case


def _owners_offer(
    dl: Any, case, case_manager_id: str, owner_id: str, transferee_id: str
):
    """The Offer as the offer trigger stored it in the owner's store.

    The CASE_MANAGER is its ``actor`` and the owner its ``attributed_to``
    (CM-24-001, CM-24-002).
    """
    offer = offer_case_ownership_transfer_activity(
        case=as_VulnerabilityCase.model_validate(
            {"id": case.id_, "name": case.name}
        ),
        target=transferee_id,
        actor=case_manager_id,
        attributed_to=owner_id,
        to=[case_manager_id],
    )
    dl.create(offer)
    return offer


def _execute(dl: Any, actor_id: str, offer_id: str):
    return SvcWithdrawCaseOwnershipTransferUseCase(
        dl,
        WithdrawCaseOwnershipTransferTriggerRequest(
            actor_id=actor_id, offer_id=offer_id
        ),
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()


@pytest.fixture
def owner_world(actor_store):
    """The owner's own store, holding the case and the Offer it made.

    The trigger runs as the owner against its own store (ADR-0073,
    DL-07-009): that is where the offer trigger stored the Offer.
    """
    owner, dl = actor_store("Vendor")
    transferee, _ = actor_store("Coordinator")
    case_manager, _ = actor_store("CaseActor")
    dl.create(transferee)
    dl.create(case_manager)
    case = _seed_case(dl, owner.id_, case_manager.id_)
    offer = _owners_offer(
        dl, case, case_manager.id_, owner.id_, transferee.id_
    )
    return dl, owner, case_manager, case, offer


@pytest.mark.spec("TRIG-11-006")
@pytest.mark.spec("CM-21-015")
def test_withdrawal_is_addressed_to_the_case_manager(owner_world):
    dl, owner, case_manager, _, offer = owner_world

    result = _execute(dl, owner.id_, offer.id_)

    activity = activity_of(result)
    assert activity["type"] == "Undo"
    # From the requesting actor, not delegated (TRIG-11-006).
    assert activity["actor"] == owner.id_
    assert activity["to"] == [case_manager.id_]
    withdrawn = activity["object"]
    assert (withdrawn["id"] if isinstance(withdrawn, dict) else withdrawn) == (
        offer.id_
    )


@pytest.mark.spec("TRIG-11-006")
def test_withdrawal_is_persisted_and_queued(owner_world):
    dl, owner, _, _, offer = owner_world

    result = _execute(dl, owner.id_, offer.id_)

    undo_id = activity_of(result)["id"]
    assert dl.read(undo_id) is not None
    assert undo_id in dl.outbox_list()


def test_raises_when_offer_not_held(actor_store):
    owner, dl = actor_store("Vendor")

    with pytest.raises(VultronNotFoundError):
        _execute(dl, owner.id_, "https://example.org/activities/nope")
    assert dl.outbox_list() == []


def test_raises_when_actor_not_found(owner_world):
    dl, _, _, _, offer = owner_world

    with pytest.raises(VultronNotFoundError):
        _execute(dl, "https://example.org/actors/ghost", offer.id_)
    assert dl.outbox_list() == []


def test_raises_when_offer_names_no_case():
    """Neither stored shape of the Offer yields a case id."""
    actor_id = "https://example.org/actors/owner-nocase"
    actor = MagicMock()
    actor.id_ = actor_id
    offer = MagicMock()
    offer.case_id = None
    offer.object_ = None
    dl = MagicMock()
    dl.read.side_effect = lambda id_: actor if id_ == actor_id else offer

    with pytest.raises(VultronNotFoundError):
        _execute(dl, actor_id, "https://example.org/activities/offer-nocase")


@pytest.mark.spec("CM-21-015")
@pytest.mark.spec("PCR-08-011")
def test_withdrawal_of_an_offer_for_a_case_not_held_is_not_sent(actor_store):
    """A store that does not hold the case cannot name its CASE_MANAGER.

    The Offer the owner sent directly names the owner as ``actor``; falling
    back to it would address the withdrawal to its own sender.
    """
    owner, dl = actor_store("Vendor")
    case_id = "https://example.org/cases/withdraw-no-case-held"
    offer = offer_case_ownership_transfer_activity(
        case=as_VulnerabilityCase.model_validate(
            {"id": case_id, "name": "Not held"}
        ),
        target="https://example.org/actors/coordinator",
        actor=owner.id_,
    )
    dl.create(offer)

    with pytest.raises(VultronNotFoundError, match="VulnerabilityCase"):
        _execute(dl, owner.id_, offer.id_)
    assert dl.outbox_list() == []


@pytest.mark.spec("CM-21-015")
@pytest.mark.spec("PCR-08-011")
def test_withdrawal_with_no_case_manager_to_address_is_not_sent(actor_store):
    """A held case whose roster names no CASE_MANAGER sends nothing.

    It is refused as not found before the tree runs, as the offer trigger
    refuses the same case, rather than failing inside the emit node.
    """
    owner, dl = actor_store("Vendor")
    case = as_VulnerabilityCase(attributed_to=owner.id_, name="No manager")
    participant = as_CaseParticipant(
        attributed_to=owner.id_,
        context=case.id_,
        case_roles=[CVDRole.CASE_OWNER],
    )
    case.actor_participant_index[owner.id_] = participant.id_
    case.case_participants.append(participant.id_)
    dl.create(participant)
    dl.create(case)
    offer = offer_case_ownership_transfer_activity(
        case=as_VulnerabilityCase.model_validate(
            {"id": case.id_, "name": case.name}
        ),
        target="https://example.org/actors/coordinator",
        actor=owner.id_,
    )
    dl.create(offer)

    with pytest.raises(VultronNotFoundError, match="CASE_MANAGER"):
        _execute(dl, owner.id_, offer.id_)
    assert dl.outbox_list() == []
