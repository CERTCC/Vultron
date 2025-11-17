#  Copyright (c) 2025 Carnegie Mellon University and Contributors.
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

import unittest

from vultron.api.v2.data import actor_io


class TestActorIO(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        actor_io.ACTOR_IO_STORE.clear()

    def test_ACTOR_IO_STORE_initially_empty(self):
        self.assertEqual(len(actor_io.ACTOR_IO_STORE), 0)

    def test_init_actor_io_creates_actor_io(self):
        actor_id = "https://demo.vultron.local/actors/test-actor"
        actor_io_instance = actor_io.init_actor_io(actor_id)

        self.assertIn(actor_id, actor_io.ACTOR_IO_STORE)
        self.assertEqual(actor_io_instance.actor_id, actor_id)
        self.assertIsInstance(actor_io_instance.inbox, actor_io.Mailbox)
        self.assertIsInstance(actor_io_instance.outbox, actor_io.Mailbox)

    def test_init_actor_io_raises_on_existing_actor(self):
        actor_id = "https://demo.vultron.local/actors/test-actor"
        actor_io.init_actor_io(actor_id)

        with self.assertRaises(KeyError):
            actor_io.init_actor_io(actor_id)

    def test_init_actor_io_force_overwrites(self):
        actor_id = "https://demo.vultron.local/actors/test-actor"
        actor_io_instance1 = actor_io.init_actor_io(actor_id)
        self.assertIn(actor_id, actor_io.ACTOR_IO_STORE)
        self.assertIs(actor_io_instance1, actor_io.ACTOR_IO_STORE[actor_id])

        actor_io_instance2 = actor_io.init_actor_io(actor_id, force=True)

        # Verify that the instance has been overwritten
        self.assertIn(actor_id, actor_io.ACTOR_IO_STORE)
        self.assertIs(actor_io_instance2, actor_io.ACTOR_IO_STORE[actor_id])
        # note we have to use assertIsNot to confirm they are different instances
        # because assertEqual would compare their content which is the same
        self.assertIsNot(actor_io_instance1, actor_io_instance2)

    def test_get_actor_io_returns_existing_instance(self):
        actor_id = "https://demo.vultron.local/actors/test-actor"
        actor_io_instance1 = actor_io.init_actor_io(actor_id)

        actor_io_instance2 = actor_io.get_actor_io(actor_id)

        self.assertIs(actor_io_instance1, actor_io_instance2)

    def test_get_actor_io_on_nonexistent_actor(self):
        actor_id = "https://demo.vultron.local/actors/nonexistent-actor"

        self.assertNotIn(actor_id, actor_io.ACTOR_IO_STORE)

        self.assertIsNone(
            actor_io.get_actor_io(actor_id, init=False, raise_on_missing=False)
        )

        with self.assertRaises(KeyError):
            actor_io.get_actor_io(actor_id, init=False, raise_on_missing=True)

        with self.assertRaises(KeyError):
            # Note that raise_on_missing takes precedence over init
            actor_io.get_actor_io(actor_id, init=True, raise_on_missing=True)

    def test_get_actor_io_initializes_when_requested(self):
        actor_id = "https://demo.vultron.local/actors/new-actor"

        self.assertNotIn(actor_id, actor_io.ACTOR_IO_STORE)

        actor_io_instance = actor_io.get_actor_io(
            actor_id, init=True, raise_on_missing=False
        )

        self.assertIsNotNone(actor_io_instance)
        self.assertIn(actor_id, actor_io.ACTOR_IO_STORE)
        self.assertIs(actor_io_instance, actor_io.ACTOR_IO_STORE[actor_id])

    def test_get_actor_inbox_returns_mailbox(self):
        actor_id = "https://demo.vultron.local/actors/test-actor"
        actor_io.init_actor_io(actor_id)

        inbox = actor_io.get_actor_inbox(actor_id)

        self.assertIsInstance(inbox, actor_io.Mailbox)
        self.assertIs(inbox, actor_io.ACTOR_IO_STORE[actor_id].inbox)

    def test_get_actor_inbox_raises_on_nonexistent_actor(self):
        actor_id = "https://demo.vultron.local/actors/nonexistent-actor"

        self.assertNotIn(actor_id, actor_io.ACTOR_IO_STORE)

        with self.assertRaises(KeyError):
            actor_io.get_actor_inbox(actor_id)

    def test_get_actor_outbox_returns_mailbox(self):
        actor_id = "https://demo.vultron.local/actors/test-actor"
        actor_io.init_actor_io(actor_id)

        outbox = actor_io.get_actor_outbox(actor_id)

        self.assertIsInstance(outbox, actor_io.Mailbox)
        self.assertIs(outbox, actor_io.ACTOR_IO_STORE[actor_id].outbox)

    def test_get_actor_outbox_raises_on_nonexistent_actor(self):
        actor_id = "https://demo.vultron.local/actors/nonexistent-actor"

        self.assertNotIn(actor_id, actor_io.ACTOR_IO_STORE)

        with self.assertRaises(KeyError):
            actor_io.get_actor_outbox(actor_id)

    def test_reset_actor_inbox_clears_inbox(self):
        actor_id = "https://demo.vultron.local/actors/test-actor"
        actor_io_instance = actor_io.init_actor_io(actor_id)

        # Add a message to the inbox
        actor_io_instance.inbox.items.append(
            {"id": "msg1", "content": "Hello"}
        )

        self.assertEqual(len(actor_io_instance.inbox.items), 1)

        new_inbox = actor_io.reset_actor_inbox(actor_id)

        self.assertIsInstance(new_inbox, actor_io.Mailbox)
        self.assertEqual(len(new_inbox.items), 0)
        self.assertIs(new_inbox, actor_io_instance.inbox)

    def test_reset_actor_inbox_raises_on_nonexistent_actor(self):
        actor_id = "https://demo.vultron.local/actors/nonexistent-actor"

        self.assertNotIn(actor_id, actor_io.ACTOR_IO_STORE)

        with self.assertRaises(KeyError):
            actor_io.reset_actor_inbox(actor_id)

    def test_reset_actor_outbox_clears_outbox(self):
        actor_id = "https://demo.vultron.local/actors/test-actor"
        actor_io_instance = actor_io.init_actor_io(actor_id)

        # Add a message to the outbox
        actor_io_instance.outbox.items.append(
            {"id": "msg1", "content": "Hello"}
        )

        self.assertEqual(len(actor_io_instance.outbox.items), 1)

        new_outbox = actor_io.reset_actor_outbox(actor_id)

        self.assertIsInstance(new_outbox, actor_io.Mailbox)
        self.assertEqual(len(new_outbox.items), 0)
        self.assertIs(new_outbox, actor_io_instance.outbox)

    def test_reset_actor_outbox_raises_on_nonexistent_actor(self):
        actor_id = "https://demo.vultron.local/actors/nonexistent-actor"

        self.assertNotIn(actor_id, actor_io.ACTOR_IO_STORE)

        with self.assertRaises(KeyError):
            actor_io.reset_actor_outbox(actor_id)

    def test_clear_all_actor_ios_empties_store(self):
        actor_id1 = "https://demo.vultron.local/actors/actor1"
        actor_id2 = "https://demo.vultron.local/actors/actor2"
        actor_io.init_actor_io(actor_id1)
        actor_io.init_actor_io(actor_id2)

        self.assertEqual(len(actor_io.ACTOR_IO_STORE), 2)

        actor_io.clear_all_actor_ios()

        self.assertEqual(len(actor_io.ACTOR_IO_STORE), 0)


if __name__ == "__main__":
    unittest.main()
