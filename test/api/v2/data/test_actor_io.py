#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

import pytest

from vultron.api.v2.data import actor_io
from vultron.api.v2.data.utils import parse_id


def test_actor_io_store_initially_empty():
    assert len(actor_io.ACTOR_IO_STORE) == 0


def test_init_actor_io_creates_actor_io_and_registers_store_key():
    actor_id = "https://demo.vultron.local/actors/test-actor"
    actor_io_instance = actor_io.init_actor_io(actor_id)
    assert actor_io_instance.actor_id in actor_io.ACTOR_IO_STORE
    # store key should include the object id part
    parsed = parse_id(actor_id)
    assert parsed["object_id"] in actor_io.ACTOR_IO_STORE
    assert isinstance(actor_io_instance.inbox, actor_io.Mailbox)
    assert isinstance(actor_io_instance.outbox, actor_io.Mailbox)


def test_init_actor_io_raises_on_existing_actor():
    actor_id = "https://demo.vultron.local/actors/test-actor"
    actor_io.init_actor_io(actor_id)
    with pytest.raises(KeyError):
        actor_io.init_actor_io(actor_id)


def test_init_actor_io_force_overwrites_existing_instance():
    actor_id = "https://demo.vultron.local/actors/test-actor"
    instance1 = actor_io.init_actor_io(actor_id)
    assert instance1.actor_id in actor_io.ACTOR_IO_STORE
    instance2 = actor_io.init_actor_io(actor_id, force=True)
    assert instance2.actor_id in actor_io.ACTOR_IO_STORE
    assert instance1.actor_id == instance2.actor_id
    assert instance1 is not instance2


def test_get_actor_io_returns_existing_instance():
    actor_id = "https://demo.vultron.local/actors/test-actor"
    instance1 = actor_io.init_actor_io(actor_id)
    instance2 = actor_io.get_actor_io(actor_id)
    assert instance1 is instance2


def test_get_actor_io_nonexistent_behaviour_and_exceptions():
    actor_id = "https://demo.vultron.local/actors/nonexistent-actor"
    assert actor_id not in actor_io.ACTOR_IO_STORE
    assert (
        actor_io.get_actor_io(actor_id, init=False, raise_on_missing=False)
        is None
    )
    with pytest.raises(KeyError):
        actor_io.get_actor_io(actor_id, init=False, raise_on_missing=True)
    with pytest.raises(KeyError):
        actor_io.get_actor_io(actor_id, init=True, raise_on_missing=True)


def test_get_actor_io_initializes_when_requested():
    actor_id = "https://demo.vultron.local/actors/new-actor"
    actor_key = parse_id(actor_id)["object_id"]
    assert actor_key not in actor_io.ACTOR_IO_STORE
    actor_io_instance = actor_io.get_actor_io(
        actor_id, init=True, raise_on_missing=False
    )
    assert actor_io_instance is not None
    assert actor_key in actor_io.ACTOR_IO_STORE
    assert actor_io_instance is actor_io.ACTOR_IO_STORE[actor_key]


def test_get_actor_inbox_returns_mailbox_instance():
    actor_id = "https://demo.vultron.local/actors/test-actor"
    io = actor_io.init_actor_io(actor_id)
    returned = actor_io.get_actor_inbox(actor_id)
    assert isinstance(returned, actor_io.Mailbox)
    assert returned is io.inbox


def test_get_actor_inbox_raises_for_nonexistent_actor():
    actor_id = "https://demo.vultron.local/actors/nonexistent-actor"
    assert actor_id not in actor_io.ACTOR_IO_STORE
    with pytest.raises(KeyError):
        actor_io.get_actor_inbox(actor_id)


def test_get_actor_outbox_returns_mailbox_instance():
    actor_id = "https://demo.vultron.local/actors/test-actor"
    io = actor_io.init_actor_io(actor_id)
    outbox = actor_io.get_actor_outbox(actor_id)
    assert isinstance(outbox, actor_io.Mailbox)
    assert outbox is io.outbox


def test_get_actor_outbox_raises_for_nonexistent_actor():
    actor_id = "https://demo.vultron.local/actors/nonexistent-actor"
    assert actor_id not in actor_io.ACTOR_IO_STORE
    with pytest.raises(KeyError):
        actor_io.get_actor_outbox(actor_id)


def test_reset_actor_inbox_clears_existing_messages_and_returns_mailbox():
    actor_id = "https://demo.vultron.local/actors/test-actor"
    actor_io_instance = actor_io.init_actor_io(actor_id)
    actor_io_instance.inbox.items.append({"id": "msg1", "content": "Hello"})
    assert len(actor_io_instance.inbox.items) == 1
    new_inbox = actor_io.reset_actor_inbox(actor_id)
    assert isinstance(new_inbox, actor_io.Mailbox)
    assert len(new_inbox.items) == 0
    assert new_inbox is actor_io_instance.inbox


def test_reset_actor_inbox_raises_for_nonexistent_actor():
    actor_id = "https://demo.vultron.local/actors/nonexistent-actor"
    assert actor_id not in actor_io.ACTOR_IO_STORE
    with pytest.raises(KeyError):
        actor_io.reset_actor_inbox(actor_id)


def test_reset_actor_outbox_clears_existing_messages_and_returns_mailbox():
    actor_id = "https://demo.vultron.local/actors/test-actor"
    actor_io_instance = actor_io.init_actor_io(actor_id)
    actor_io_instance.outbox.items.append({"id": "msg1", "content": "Hello"})
    assert len(actor_io_instance.outbox.items) == 1
    new_outbox = actor_io.reset_actor_outbox(actor_id)
    assert isinstance(new_outbox, actor_io.Mailbox)
    assert len(new_outbox.items) == 0
    assert new_outbox is actor_io_instance.outbox


def test_reset_actor_outbox_raises_for_nonexistent_actor():
    actor_id = "https://demo.vultron.local/actors/nonexistent-actor"
    assert actor_id not in actor_io.ACTOR_IO_STORE
    with pytest.raises(KeyError):
        actor_io.reset_actor_outbox(actor_id)


def test_clear_all_actor_ios_empties_the_store():
    actor_id1 = "https://demo.vultron.local/actors/actor1"
    actor_id2 = "https://demo.vultron.local/actors/actor2"
    actor_io.init_actor_io(actor_id1)
    actor_io.init_actor_io(actor_id2)
    assert len(actor_io.ACTOR_IO_STORE) == 2
    actor_io.clear_all_actor_ios()
    assert len(actor_io.ACTOR_IO_STORE) == 0
