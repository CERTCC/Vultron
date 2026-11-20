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

The Case Owner withdraws its own ownership-transfer Offer: the trigger emits
``Undo(Offer(VulnerabilityCase))`` from the owner, addressed to the case's
CASE_MANAGER (CM-21-036, ADR-0199), and queues it in the owner's own
outbox.  What the CASE_MANAGER does with it (admit only from the owner of an
open Offer it made from the proposal, ledger it, close the Offer) is tested
with the received use case in
``test/core/use_cases/received/actor/test_ownership.py``.
"""

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from test.support.act_runner import run_in_act
from test.support.case_owner import CASE_OWNER_ID
from test.support.objects import authored_at, make, with_times
from test.support.trigger_results import activity_of
from vultron.adapters.driven.clock import SystemClock
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
from vultron.wire.as2.enums import as_TransitiveActivityType as TAtype
from vultron.wire.as2.factories.case import (
    offer_case_ownership_transfer_activity,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)


def _seed_case(dl: Any, owner_id: str, case_manager_id: str):
    """A case owned by *owner_id* and managed by *case_manager_id*."""
    case = make(
        as_VulnerabilityCase,
        attributed_to=owner_id,
        name="Withdraw Case",
        content="Content",
    )
    for actor_id, role in (
        (owner_id, CVDRole.CASE_OWNER),
        (case_manager_id, CVDRole.CASE_MANAGER),
    ):
        participant = make(
            as_CaseParticipant,
            attributed_to=actor_id,
            context=case.id_,
            case_roles=[role],
        )
        case.actor_participant_index[actor_id] = participant.id_
        case.case_participants.append(participant.id_)
        dl.create(participant)
    dl.create(case)
    return case


def _proposal(case_id: str, name: str, owner_id: str, to: list[str] | None):
    """The Owner's own Offer, as the offer trigger builds it (ADR-0199)."""
    return offer_case_ownership_transfer_activity(
        as_VulnerabilityCase.model_validate(
            with_times(
                as_VulnerabilityCase,
                {"attributed_to": CASE_OWNER_ID, "id": case_id, "name": name},
            )
        ),
        target="https://example.org/actors/coordinator",
        actor=owner_id,
        to=to,
        at=authored_at(),
    )


def _owners_offer(
    dl: Any, case, case_manager_id: str, owner_id: str, transferee_id: str
):
    """The Owner's Offer as the offer trigger stored it in its store
    (ADR-0199)."""
    proposal = offer_case_ownership_transfer_activity(
        as_VulnerabilityCase.model_validate(
            with_times(
                as_VulnerabilityCase,
                {
                    "attributed_to": CASE_OWNER_ID,
                    "id": case.id_,
                    "name": case.name,
                },
            )
        ),
        target=transferee_id,
        actor=owner_id,
        to=[case_manager_id],
        at=authored_at(),
    )
    dl.create(proposal)
    return proposal


def _execute(dl: Any, actor_id: str, offer_id: str):
    return run_in_act(
        SvcWithdrawCaseOwnershipTransferUseCase(
            dl,
            WithdrawCaseOwnershipTransferTriggerRequest(
                actor_id=actor_id, offer_id=offer_id
            ),
            trigger_activity=TriggerActivityAdapter(dl),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            clock=SystemClock(),
        )
    )


@pytest.fixture
def owner_world(actor_store):
    """The owner's own store, holding the case and the proposal it sent.

    The trigger runs as the owner against its own store (ADR-0073,
    DL-07-009): that is where the offer trigger stored the proposal.
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
@pytest.mark.spec("TRIG-11-004")
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
    # The owner withdraws its own Offer of the case (ADR-0199).
    assert withdrawn["type"] == "Offer"
    assert withdrawn["object"]["type"] == "VulnerabilityCase"


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


def test_raises_when_proposal_names_no_case():
    """A held Owner's Offer with no ``object`` yields no case id."""
    actor_id = "https://example.org/actors/owner-nocase"
    actor = MagicMock()
    actor.id_ = actor_id
    offer = MagicMock()
    offer.type_ = "Offer"
    offer.actor = actor_id
    offer.object_ = None
    dl = MagicMock()
    dl.read.side_effect = lambda id_: actor if id_ == actor_id else offer

    with pytest.raises(VultronNotFoundError, match="this actor sent"):
        _execute(dl, actor_id, "https://example.org/activities/offer-nocase")


@pytest.mark.spec("TRIG-11-006")
@pytest.mark.parametrize(
    "offer_type",
    [
        pytest.param("Offer", id="core-str-type"),
        pytest.param(TAtype.OFFER, id="wire-enum-type"),
    ],
)
def test_the_owners_offer_is_recognised_whatever_form_its_type_takes(
    offer_type,
):
    """The Owner's Offer's type is read from a wire StrEnum or a core
    ``str``: neither is refused as not-an-Offer."""
    case_id = "https://example.org/cases/held-forms"
    owner_id = "https://example.org/actors/owner-forms"
    own_offer = SimpleNamespace(
        type_=offer_type,
        actor=owner_id,
        object_=SimpleNamespace(id_=case_id, type_="VulnerabilityCase"),
    )
    dl = MagicMock()
    dl.read.return_value = own_offer
    use_case = SvcWithdrawCaseOwnershipTransferUseCase.__new__(
        SvcWithdrawCaseOwnershipTransferUseCase
    )
    use_case._dl = dl
    use_case._actor_id = owner_id
    # The Offer is one the owner sent, so nothing loads it as received.
    cast(Any, use_case)._trigger_activity = SimpleNamespace(
        load_received_activity=lambda _activity_id: None
    )

    assert use_case._held_case_id("https://example.org/p/1") == case_id


_HELD_OWNER_ID = "https://example.org/actors/owner-held"
_HELD_CASE = SimpleNamespace(
    id_="https://example.org/cases/held", type_="VulnerabilityCase"
)


@pytest.mark.spec("TRIG-11-006")
@pytest.mark.parametrize(
    "held",
    [
        pytest.param(
            SimpleNamespace(
                type_="Offer",
                actor=_HELD_OWNER_ID,
                object_=SimpleNamespace(
                    id_="https://example.org/reports/r1",
                    type_="VulnerabilityReport",
                ),
            ),
            id="offer-of-a-report",
        ),
        pytest.param(
            SimpleNamespace(
                type_="Invite", actor=_HELD_OWNER_ID, object_=_HELD_CASE
            ),
            id="invite-of-the-case",
        ),
        pytest.param(
            SimpleNamespace(type_="Offer", actor=None, object_=_HELD_CASE),
            id="offer-naming-no-actor",
        ),
    ],
)
def test_naming_an_activity_that_is_not_the_owners_offer_is_refused(held):
    """An activity this actor holds that is not its own ownership-transfer
    Offer (an Offer of something else, an Invite of the case, or an Offer
    naming no sender) is refused before any tree runs."""
    dl = MagicMock()
    dl.read.return_value = held
    use_case = SvcWithdrawCaseOwnershipTransferUseCase.__new__(
        SvcWithdrawCaseOwnershipTransferUseCase
    )
    use_case._dl = dl
    use_case._actor_id = _HELD_OWNER_ID
    cast(Any, use_case)._trigger_activity = SimpleNamespace(
        load_received_activity=lambda _activity_id: None
    )

    with pytest.raises(VultronNotFoundError, match="this actor sent"):
        use_case._held_case_id("https://example.org/p/held")


@pytest.mark.spec("TRIG-11-006")
@pytest.mark.spec("CM-21-015")
def test_naming_the_offer_rather_than_the_proposal_is_refused(owner_world):
    """``offer_id`` names the owner's own Offer, never the CASE_MANAGER's
    Offer made from it: an Offer another actor sent is refused before
    anything is sent, with an error that says what to name (ADR-0199)."""
    dl, owner, case_manager, case, _ = owner_world
    offer = offer_case_ownership_transfer_activity(
        case=as_VulnerabilityCase.model_validate(
            with_times(
                as_VulnerabilityCase,
                {
                    "attributed_to": CASE_OWNER_ID,
                    "id": case.id_,
                    "name": case.name,
                },
            )
        ),
        target="https://example.org/actors/coordinator",
        actor=case_manager.id_,
        attributed_to=owner.id_,
        at=authored_at(),
    )
    dl.create(offer)

    with pytest.raises(VultronNotFoundError, match="this actor sent"):
        _execute(dl, owner.id_, offer.id_)
    assert dl.outbox_list() == []


@pytest.mark.spec("CM-21-015")
@pytest.mark.spec("PCR-08-011")
def test_withdrawal_of_an_offer_for_a_case_not_held_is_not_sent(actor_store):
    """A store that does not hold the case cannot name its CASE_MANAGER.

    The proposal names the owner as ``actor``; falling back to it would
    address the withdrawal to its own sender.
    """
    owner, dl = actor_store("Vendor")
    case_id = "https://example.org/cases/withdraw-no-case-held"
    offer = _proposal(case_id, "Not held", owner.id_, None)
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
    case = make(
        as_VulnerabilityCase, attributed_to=owner.id_, name="No manager"
    )
    participant = make(
        as_CaseParticipant,
        attributed_to=owner.id_,
        context=case.id_,
        case_roles=[CVDRole.CASE_OWNER],
    )
    case.actor_participant_index[owner.id_] = participant.id_
    case.case_participants.append(participant.id_)
    dl.create(participant)
    dl.create(case)
    offer = _proposal(case.id_, case.name or "No manager", owner.id_, None)
    dl.create(offer)

    with pytest.raises(VultronNotFoundError, match="CASE_MANAGER"):
        _execute(dl, owner.id_, offer.id_)
    assert dl.outbox_list() == []
