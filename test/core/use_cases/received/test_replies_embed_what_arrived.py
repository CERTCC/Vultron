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

"""A reply embeds the activity it answers as its sender sent it (ADR-0149).

Each actor has its own store, and activities move between them only as the
sealed body the sender's outbox delivers, parsed and routed as the inbox
routes it (``LedgerNetwork``).  The received body is archived verbatim, so a
field the core model does not keep (an Invite's ``cc``, a key no vocabulary
names) and the RSVP deadline survive into the answer.
"""

import json
from typing import Any

import pytest

from test.support.received import received_record
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.use_cases.triggers.embargo import SvcAcceptEmbargoUseCase
from vultron.core.use_cases.triggers.requests import (
    AcceptEmbargoTriggerRequest,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service

from ._ledger_network import BYSTANDER, MANAGER, LedgerNetwork
from .test_embargo_relay_replay import _propose

_WATCHER = "https://example.org/users/watcher"
_EXTRA = {"rsvpNote": "answer within the week", "priority": 3}


def _relayed_invite_with_extras(net: LedgerNetwork) -> dict[str, Any]:
    """The CASE_MANAGER's relayed Invite to BYSTANDER, with fields added.

    The relay carries its RSVP deadline as ``endTime``; the sender adds a
    ``cc`` and a key this receiver's vocabulary does not name.
    """
    _propose(net, "verbatim", 90)
    [invite] = net.queued(MANAGER, to=BYSTANDER, type_="Invite")
    body = read_sealed_body_dict(net.stores[MANAGER], invite.id_)
    assert body is not None
    assert body.get("endTime"), "the relayed Invite carries its deadline"
    return {**body, "cc": [_WATCHER], "x-vendorExtension": _EXTRA}


@pytest.mark.spec("DL-06-004")
@pytest.mark.spec("CLP-10-017")
def test_the_participants_accept_embeds_the_invite_as_received():
    net = LedgerNetwork("https://example.org/cases/verbatim-accept")
    body = _relayed_invite_with_extras(net)

    net.receive(BYSTANDER, body)

    record = received_record(net.stores[BYSTANDER], body["id"])
    assert record is not None
    # The archive is the body the parser sealed, every key included.
    assert record.received_body is not None
    archived = json.loads(record.received_body)
    assert archived == body

    _, sealed = TriggerActivityAdapter(net.stores[BYSTANDER]).accept_embargo(
        proposal_id=body["id"],
        case_id=net.case_id,
        actor=BYSTANDER,
        to=[MANAGER],
    )
    embedded = json.loads(sealed)["object"]

    assert embedded == body
    assert embedded["endTime"] == body["endTime"]
    assert embedded["cc"] == [_WATCHER]
    assert embedded["x-vendorExtension"] == _EXTRA


@pytest.mark.spec("DL-06-004")
@pytest.mark.spec("DL-06-001")
def test_the_accept_trigger_embeds_the_invite_as_received():
    """End to end: the Invite is delivered, the participant runs its accept
    trigger, and the Accept its outbox delivers embeds the Invite verbatim."""
    net = LedgerNetwork("https://example.org/cases/verbatim-trigger")
    body = _relayed_invite_with_extras(net)
    net.deliver(MANAGER, to=BYSTANDER, type_="Announce")
    net.receive(BYSTANDER, body)
    dl = net.stores[BYSTANDER]
    # The trigger runs as the actor whose store this is (ADR-0073).
    dl.save(as_Service(id_=BYSTANDER, name="Vendor B"))

    result = SvcAcceptEmbargoUseCase(
        dl,
        AcceptEmbargoTriggerRequest(
            actor_id=BYSTANDER, case_id=net.case_id, proposal_id=body["id"]
        ),
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()

    assert result.activity is not None
    sealed = read_sealed_body_dict(dl, result.activity["id"])
    assert sealed is not None
    assert sealed["object"] == body
