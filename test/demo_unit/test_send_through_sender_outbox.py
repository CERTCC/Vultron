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
"""An exchange demo sends a hand-built activity through its sender's outbox.

Demo code never signs as an actor (SIG-05-004): ``post_to_inbox_and_wait``
posts the activity to the sender's own outbox, which signs and delivers it,
then waits for the receiver's outcome (EDF-06).
"""

from typing import Any
from unittest.mock import MagicMock

import pytest

from test.support.objects import authored_at, make
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
    ReceivedStage,
)
from vultron.demo.utils import DataLayerClient, inbox as demo_inbox
from vultron.wire.as2.factories import add_note_to_case_activity
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

_CASE = "https://example.org/cases/demo-send"
_SENDER = "https://example.org/users/finder"
_RECEIVER = "https://example.org/users/vendor"


def _note(**kwargs: Any):
    return add_note_to_case_activity(
        make(as_Note, id_=f"{_CASE}/notes/1", content="n", context=_CASE),
        target=_CASE,
        actor=_SENDER,
        **kwargs,
        at=authored_at(),
    )


def test_an_unaddressed_activity_is_addressed_to_the_receiver():
    addressed = demo_inbox._addressed_to(_note(), _RECEIVER)

    assert addressed.to == [_RECEIVER]


def test_an_activity_addressed_to_the_receiver_is_kept():
    activity = _note(to=[f"{_RECEIVER}/"])

    assert demo_inbox._addressed_to(activity, _RECEIVER) is activity


def test_an_activity_addressed_to_others_fails_fast():
    with pytest.raises(ValueError, match="not to"):
        demo_inbox._addressed_to(
            _note(to=["https://example.org/users/other"]), _RECEIVER
        )


@pytest.mark.parametrize(
    ("record", "reached"),
    [
        (None, False),
        ({"stage": ReceivedStage.HELD, "replay_owed": False}, False),
        ({"stage": ReceivedStage.HELD, "replay_owed": True}, True),
        ({"stage": ReceivedStage.ARCHIVED}, True),
        ({"stage": ReceivedStage.REFUSED}, True),
    ],
    ids=["none", "in-handling", "deferred", "archived", "refused"],
)
def test_the_wait_ends_at_an_outcome(record: Any, reached: bool):
    assert demo_inbox._delivery_outcome_reached(record) is reached


def _client(records: dict[str, Any]) -> MagicMock:
    client = MagicMock(spec=DataLayerClient)
    client.base_url = "http://testserver/api/v2"
    client.dl_path.side_effect = lambda key=None, actor_id=None: key or ""
    client.get.side_effect = lambda path, **kwargs: (
        records if kwargs.get("params") else {}
    )
    return client


@pytest.mark.spec("SIG-05-004")
def test_the_activity_goes_to_the_senders_outbox_unsigned(monkeypatch):
    monkeypatch.setattr(
        demo_inbox, "_stamped_as_in_step", lambda client, actor, a: a
    )
    monkeypatch.setattr(
        demo_inbox, "_numbered_as_in_step", lambda client, actor, a: a
    )
    activity = _note()
    client = _client(
        {
            ReceivedActivityRecord.build_id(activity.id_): {
                "stage": ReceivedStage.ARCHIVED
            }
        }
    )

    demo_inbox.post_to_inbox_and_wait(client, _RECEIVER, activity)

    [call] = client.post.call_args_list
    path, body = call.args[0], call.kwargs["json"]
    assert path == "/actors/finder/outbox/"
    assert body["to"] == [_RECEIVER]
    assert "proof" not in body


def test_no_outcome_in_time_fails_the_step(monkeypatch):
    monkeypatch.setattr(
        demo_inbox, "_stamped_as_in_step", lambda client, actor, a: a
    )
    monkeypatch.setattr(
        demo_inbox, "_numbered_as_in_step", lambda client, actor, a: a
    )

    with pytest.raises(AssertionError, match="reach an outcome"):
        demo_inbox.post_to_inbox_and_wait(
            _client({}), _RECEIVER, _note(), wait_seconds=0
        )
