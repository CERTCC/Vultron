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

"""Tests for ``SvcRejectCaseOwnershipTransferUseCase`` (TRIG-11-005).

The transferee declines an ownership-transfer Offer it holds: the trigger
emits ``Reject(Offer(VulnerabilityCase))`` from the transferee, addressed to
the case's CASE_MANAGER (CM-21-010), and queues it in the transferee's own
outbox.  What the CASE_MANAGER does with it (CM-21-012 – CM-21-014) is tested
with the received use case in
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
from vultron.core.models.ownership_transfer_offer_record import (
    VultronOwnershipTransferOfferRecord,
)
from vultron.core.use_cases.triggers.actor import (
    SvcRejectCaseOwnershipTransferUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    RejectCaseOwnershipTransferTriggerRequest,
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
        attributed_to=owner_id, name="Reject Case", content="Content"
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


def _forwarded_offer(dl: Any, case, case_manager_id: str, transferee_id: str):
    """The CASE_MANAGER's forward of the Offer, as the transferee holds it."""
    offer = offer_case_ownership_transfer_activity(
        case=as_VulnerabilityCase.model_validate(
            {"id": case.id_, "name": case.name}
        ),
        target=transferee_id,
        actor=case_manager_id,
        to=[transferee_id],
    )
    dl.create(offer)
    return offer


def _execute(dl: Any, actor_id: str, offer_id: str):
    return SvcRejectCaseOwnershipTransferUseCase(
        dl,
        RejectCaseOwnershipTransferTriggerRequest(
            actor_id=actor_id, offer_id=offer_id
        ),
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()


@pytest.fixture
def transferee_world(actor_store):
    """The transferee's own store, holding the case and the forwarded Offer.

    The trigger runs as the transferee against its own store (ADR-0073,
    DL-07-009): that is where the forward landed.
    """
    transferee, dl = actor_store("Coordinator")
    owner, _ = actor_store("Vendor")
    case_manager, _ = actor_store("CaseActor")
    dl.create(owner)
    dl.create(case_manager)
    case = _seed_case(dl, owner.id_, case_manager.id_)
    offer = _forwarded_offer(dl, case, case_manager.id_, transferee.id_)
    return dl, transferee, case_manager, case, offer


@pytest.mark.spec("TRIG-11-005")
@pytest.mark.spec("CM-21-010")
def test_reject_is_addressed_to_the_case_manager(transferee_world):
    dl, transferee, case_manager, _, offer = transferee_world

    result = _execute(dl, transferee.id_, offer.id_)

    activity = activity_of(result)
    assert activity["type"] == "Reject"
    assert activity["actor"] == transferee.id_
    assert activity["to"] == [case_manager.id_]
    rejected = activity["object"]
    assert (rejected["id"] if isinstance(rejected, dict) else rejected) == (
        offer.id_
    )


@pytest.mark.spec("TRIG-11-005")
def test_reject_is_persisted_and_queued(transferee_world):
    dl, transferee, _, _, offer = transferee_world

    result = _execute(dl, transferee.id_, offer.id_)

    reject_id = activity_of(result)["id"]
    assert dl.read(reject_id) is not None
    assert reject_id in dl.outbox_list()


@pytest.mark.spec("TRIG-11-005")
def test_reject_of_an_offer_known_only_from_the_ledger(actor_store):
    """A replica that learned of the Offer from the ledger holds only its record.

    The adapter rebuilds the wire Offer from the record, as for the Accept
    (#2225), so the Reject names the same Offer either way.
    """
    transferee, dl = actor_store("Coordinator")
    owner, _ = actor_store("Vendor")
    case_manager, _ = actor_store("CaseActor")
    case = _seed_case(dl, owner.id_, case_manager.id_)
    offer_id = "https://example.org/activities/offer-known-from-ledger"
    dl.create(
        VultronOwnershipTransferOfferRecord(
            offer_id=offer_id,
            case_id=case.id_,
            actor_id=owner.id_,
            target_id=transferee.id_,
        )
    )

    result = _execute(dl, transferee.id_, offer_id)

    activity = activity_of(result)
    assert activity["type"] == "Reject"
    assert activity["to"] == [case_manager.id_]


def test_raises_when_offer_not_held(actor_store):
    transferee, dl = actor_store("Coordinator")

    with pytest.raises(VultronNotFoundError):
        _execute(dl, transferee.id_, "https://example.org/activities/nope")
    assert dl.outbox_list() == []


def test_raises_when_actor_not_found(transferee_world):
    dl, _, _, _, offer = transferee_world

    with pytest.raises(VultronNotFoundError):
        _execute(dl, "https://example.org/actors/ghost", offer.id_)
    assert dl.outbox_list() == []


def test_raises_when_offer_names_no_case():
    """Neither stored shape of the Offer yields a case id."""
    actor_id = "https://example.org/actors/transferee-nocase"
    actor = MagicMock()
    actor.id_ = actor_id
    offer = MagicMock()
    offer.case_id = None
    offer.object_ = None
    dl = MagicMock()
    dl.read.side_effect = lambda id_: actor if id_ == actor_id else offer

    with pytest.raises(VultronNotFoundError):
        _execute(dl, actor_id, "https://example.org/activities/offer-nocase")
