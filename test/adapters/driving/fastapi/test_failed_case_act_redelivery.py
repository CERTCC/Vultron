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
"""A failed received case act commits when it is posted again (#4983).

Every received act that commits to a case is one act (CLP-07-015): when the
CASE_MANAGER's forward of a Case Owner's role Offer fails, neither the
Offer's entry nor the forward is kept, only intake's archive.  Posted again
through the FastAPI inbox, the activity is routed as the copy intake archived
(IE-10-001), and that redelivery commits the Offer and sends the forward
once.  The case act counterpart of ``test_failed_act_redelivery.py``.
"""

import logging
from typing import Any

import pytest

from test.adapters.driving.fastapi._redelivery import (
    assert_routed_as_archived_redelivery,
    faults,
    post,
    served_store,
)
from test.core.use_cases.received.actor.test_role_offer_routing import (
    _CASE_MANAGER_ID,
    _OFFER_ID,
    _OWNER_ID,
    _TARGET_ID,
    _offer,
    _semantic_types,
    _store,
)
from test.support.emitter import RecordingEmitter
from test.support.received import delivered_body
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)

pytestmark = pytest.mark.integration

_INBOX = "/api/v2/actors/case-actor/inbox/"
_ROLE_OFFER_ENTRY = "offer_case_participant_role"


@pytest.fixture
def served_manager():
    """The role-Offer CASE_MANAGER's store served by a real app."""
    dl = _store(_CASE_MANAGER_ID)
    with served_store(dl, _CASE_MANAGER_ID, "Case Actor") as (
        client,
        emitter,
    ):
        yield client, dl, emitter


def _forwards(emitter: RecordingEmitter) -> list[dict[str, Any]]:
    """The delivered forwards of the Case Owner's Offer to the target."""
    return [
        body
        for body in emitter.to(_TARGET_ID)
        if body["type"] == "Offer" and body.get("inReplyTo") == _OFFER_ID
    ]


@pytest.mark.spec("CLP-07-015")
@pytest.mark.spec("CM-24-007")
@pytest.mark.spec("IE-10-001")
@pytest.mark.spec("ASK-07-010")
def test_a_failed_role_offer_forward_commits_when_posted_again(
    served_manager, caplog: pytest.LogCaptureFixture
):
    """The first post fails and keeps nothing but the archive; the second,
    routed as the archived copy, records the Offer and forwards it once."""
    client, dl, emitter = served_manager
    body = delivered_body(_offer(), at=dl)

    calls: list[str] = []

    def _down(self, *args: Any, **kwargs: Any) -> Any:
        calls.append("forward")
        raise RuntimeError("outbox down")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            TriggerActivityAdapter, "offer_case_participant_role", _down
        )
        post(client, _INBOX, body)

    assert calls == ["forward"], "the act failed at its forward"
    assert isinstance(
        dl.read(ReceivedActivityRecord.build_id(body["id"])),
        ReceivedActivityRecord,
    ), "intake's archive survives the rollback"
    assert _ROLE_OFFER_ENTRY not in _semantic_types(dl)
    assert _forwards(emitter) == []
    # The failed act is answered with one internal-error fault to its sender
    # (ASK-07-010).
    (fault,) = faults(emitter)
    assert emitter.to(_OWNER_ID) == [fault]
    assert fault["object"]["inReplyTo"] == body["id"]

    caplog.clear()
    with caplog.at_level(logging.INFO):
        post(client, _INBOX, body)

    # The post met the archive: it was routed as the archived copy, so it
    # cannot have passed on the resent body's own evidence.
    assert_routed_as_archived_redelivery(caplog, body["id"])
    assert _semantic_types(dl).count(_ROLE_OFFER_ENTRY) == 1
    assert len(_forwards(emitter)) == 1
    assert faults(emitter) == [fault], "the applied act sends no fault"
