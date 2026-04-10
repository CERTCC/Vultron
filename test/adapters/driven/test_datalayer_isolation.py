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
"""Tests for per-actor DataLayer isolation (ADR-0012 ACT-2)."""

import pytest

from vultron.adapters.driven.datalayer_tinydb import (
    TinyDbDataLayer,
    get_datalayer,
    reset_datalayer,
)
from vultron.core.ports.datalayer import StorableRecord


def _record(id_: str, type_: str = "Note") -> StorableRecord:
    """Helper to build a minimal StorableRecord for testing."""
    return StorableRecord(id_=id_, type_=type_, data_={"id_": id_})


@pytest.fixture(autouse=True)
def reset_instances():
    """Ensure each test starts with a clean set of DataLayer instances."""
    reset_datalayer()
    yield
    reset_datalayer()


# ---------------------------------------------------------------------------
# Table namespace isolation
# ---------------------------------------------------------------------------


class TestTableNamespaceIsolation:
    """Actor-scoped DataLayer uses prefixed table names (Option B)."""

    def test_no_prefix_for_shared_datalayer(self):
        dl = TinyDbDataLayer(db_path=None)
        tbl = dl._table("VulnerabilityReport")
        assert tbl.name == "VulnerabilityReport"

    def test_actor_prefix_applied_to_table_name(self):
        dl = TinyDbDataLayer(db_path=None, actor_id="alice")
        tbl = dl._table("VulnerabilityReport")
        assert tbl.name == "alice_VulnerabilityReport"

    def test_different_actors_get_different_table_names(self):
        dl_a = TinyDbDataLayer(db_path=None, actor_id="alice")
        dl_b = TinyDbDataLayer(db_path=None, actor_id="bob")
        assert dl_a._table("Report").name == "alice_Report"
        assert dl_b._table("Report").name == "bob_Report"


# ---------------------------------------------------------------------------
# Record isolation: writes to one actor are invisible to another
# ---------------------------------------------------------------------------


class TestRecordIsolation:
    """Records written to actor-scoped DataLayer are invisible to other actors."""

    def test_actor_a_record_not_visible_from_actor_b(self):
        dl_a = TinyDbDataLayer(db_path=None, actor_id="alice")
        dl_b = TinyDbDataLayer(db_path=None, actor_id="bob")

        dl_a.create(_record("https://example.org/r/001"))
        result = dl_b.read("https://example.org/r/001")
        assert result is None

    def test_actor_a_record_not_visible_from_shared_datalayer(self):
        dl_a = TinyDbDataLayer(db_path=None, actor_id="alice")
        dl_shared = TinyDbDataLayer(db_path=None)

        dl_a.create(_record("https://example.org/r/002"))
        result = dl_shared.read("https://example.org/r/002")
        assert result is None

    def test_two_actors_can_store_same_id_independently(self):
        dl_a = TinyDbDataLayer(db_path=None, actor_id="alice")
        dl_b = TinyDbDataLayer(db_path=None, actor_id="bob")

        shared_id = "https://example.org/cases/case-001"
        dl_a.create(_record(shared_id))
        dl_b.create(_record(shared_id))

        rec_a = dl_a.read(shared_id)
        rec_b = dl_b.read(shared_id)
        assert rec_a is not None
        assert rec_b is not None


# ---------------------------------------------------------------------------
# Inbox methods
# ---------------------------------------------------------------------------


class TestInboxMethods:
    """Per-actor DataLayer inbox_append / inbox_list / inbox_pop."""

    def test_inbox_starts_empty(self):
        dl = TinyDbDataLayer(db_path=None, actor_id="alice")
        assert dl.inbox_list() == []

    def test_inbox_append_then_list(self):
        dl = TinyDbDataLayer(db_path=None, actor_id="alice")
        dl.inbox_append("https://example.org/activities/001")
        items = dl.inbox_list()
        assert items == ["https://example.org/activities/001"]

    def test_inbox_append_multiple(self):
        dl = TinyDbDataLayer(db_path=None, actor_id="alice")
        dl.inbox_append("https://example.org/activities/001")
        dl.inbox_append("https://example.org/activities/002")
        assert len(dl.inbox_list()) == 2

    def test_inbox_pop_returns_first_then_removes(self):
        dl = TinyDbDataLayer(db_path=None, actor_id="alice")
        dl.inbox_append("https://example.org/activities/001")
        dl.inbox_append("https://example.org/activities/002")
        first = dl.inbox_pop()
        assert first == "https://example.org/activities/001"
        remaining = dl.inbox_list()
        assert len(remaining) == 1

    def test_inbox_pop_on_empty_returns_none(self):
        dl = TinyDbDataLayer(db_path=None, actor_id="alice")
        assert dl.inbox_pop() is None

    def test_inbox_is_isolated_between_actors(self):
        dl_a = TinyDbDataLayer(db_path=None, actor_id="alice")
        dl_b = TinyDbDataLayer(db_path=None, actor_id="bob")

        dl_a.inbox_append("https://example.org/activities/for-alice")
        assert dl_b.inbox_list() == []


# ---------------------------------------------------------------------------
# Outbox methods
# ---------------------------------------------------------------------------


class TestOutboxMethods:
    """Per-actor DataLayer outbox_append / outbox_list / outbox_pop."""

    def test_outbox_starts_empty(self):
        dl = TinyDbDataLayer(db_path=None, actor_id="alice")
        assert dl.outbox_list() == []

    def test_outbox_append_then_list(self):
        dl = TinyDbDataLayer(db_path=None, actor_id="alice")
        dl.outbox_append("https://example.org/activities/sent-001")
        items = dl.outbox_list()
        assert items == ["https://example.org/activities/sent-001"]

    def test_outbox_pop_returns_first_then_removes(self):
        dl = TinyDbDataLayer(db_path=None, actor_id="alice")
        dl.outbox_append("https://example.org/activities/sent-001")
        dl.outbox_append("https://example.org/activities/sent-002")
        first = dl.outbox_pop()
        assert first == "https://example.org/activities/sent-001"
        assert len(dl.outbox_list()) == 1

    def test_outbox_pop_on_empty_returns_none(self):
        dl = TinyDbDataLayer(db_path=None, actor_id="alice")
        assert dl.outbox_pop() is None

    def test_outbox_is_isolated_between_actors(self):
        dl_a = TinyDbDataLayer(db_path=None, actor_id="alice")
        dl_b = TinyDbDataLayer(db_path=None, actor_id="bob")

        dl_a.outbox_append("https://example.org/activities/from-alice")
        assert dl_b.outbox_list() == []


# ---------------------------------------------------------------------------
# record_outbox_item — cross-scope outbox queueing
# ---------------------------------------------------------------------------


class TestRecordOutboxItem:
    """record_outbox_item writes to the actor-scoped outbox regardless of DL scope."""

    def test_shared_dl_can_queue_for_actor(self):
        """Calling record_outbox_item on the shared DL reaches the actor-scoped queue."""
        # shared DL has no actor prefix
        dl_shared = TinyDbDataLayer(db_path=None)
        # actor-scoped DL uses alice_ prefix on the same backing store
        dl_alice = TinyDbDataLayer(db_path=None, actor_id="alice")
        # Patch both to share the same underlying _db object so the test
        # can verify cross-scope behaviour without a real file.
        dl_alice._db = dl_shared._db

        activity_id = "https://example.org/activities/test-001"
        dl_shared.record_outbox_item("alice", activity_id)

        # The actor-scoped DL should now see the queued item
        assert activity_id in dl_alice.outbox_list()

    def test_actor_scoped_dl_record_outbox_item_uses_actor_id(self):
        """record_outbox_item on actor-scoped DL also targets the correct table."""
        dl_alice = TinyDbDataLayer(db_path=None, actor_id="alice")
        dl_bob = TinyDbDataLayer(db_path=None, actor_id="bob")
        dl_alice._db = dl_bob._db  # shared backing store for verification

        activity_id = "https://example.org/activities/test-002"
        # record_outbox_item uses the explicitly-passed actor_id, not self._actor_id
        dl_alice.record_outbox_item("bob", activity_id)

        assert activity_id in dl_bob.outbox_list()
        assert activity_id not in dl_alice.outbox_list()

    def test_record_outbox_item_does_not_mix_queues(self):
        """Items queued for alice do not appear in bob's outbox."""
        dl_shared = TinyDbDataLayer(db_path=None)
        dl_alice = TinyDbDataLayer(db_path=None, actor_id="alice")
        dl_bob = TinyDbDataLayer(db_path=None, actor_id="bob")
        dl_alice._db = dl_shared._db
        dl_bob._db = dl_shared._db

        dl_shared.record_outbox_item(
            "alice", "https://example.org/activities/for-alice"
        )
        dl_shared.record_outbox_item(
            "bob", "https://example.org/activities/for-bob"
        )

        assert dl_alice.outbox_list() == [
            "https://example.org/activities/for-alice"
        ]
        assert dl_bob.outbox_list() == [
            "https://example.org/activities/for-bob"
        ]

    def test_record_outbox_item_full_uri_requires_matching_scoped_dl(self):
        """record_outbox_item with a full URI writes to the full-URI-prefixed table.

        This confirms the contract: the actor-scoped DataLayer passed to
        outbox_handler MUST be keyed by the same actor ID string used in
        record_outbox_item.  Trigger routes must resolve the canonical actor
        URI (actor.id_) and pass it to both get_datalayer() and the
        outbox_handler call so that the scoped DL reads from the same table
        that record_outbox_item wrote to (BUG-2026040901).
        """
        dl_shared = TinyDbDataLayer(db_path=None)
        full_uri = "https://example.org/actors/alice"
        dl_canonical = TinyDbDataLayer(db_path=None, actor_id=full_uri)
        dl_canonical._db = dl_shared._db

        activity_id = "https://example.org/activities/full-uri-001"
        dl_shared.record_outbox_item(full_uri, activity_id)

        # The actor-scoped DL keyed by the FULL URI sees the item
        assert activity_id in dl_canonical.outbox_list()

        # A DL keyed only by the short segment does NOT (different table)
        dl_short = TinyDbDataLayer(db_path=None, actor_id="alice")
        dl_short._db = dl_shared._db
        assert activity_id not in dl_short.outbox_list()


# ---------------------------------------------------------------------------
# get_datalayer() factory and instance caching
# ---------------------------------------------------------------------------


class TestGetDatalayerFactory:
    """get_datalayer() returns per-actor cached instances."""

    def test_shared_datalayer_is_singleton(self):
        dl1 = get_datalayer()
        dl2 = get_datalayer()
        assert dl1 is dl2

    def test_actor_datalayer_is_cached(self):
        dl1 = get_datalayer("alice")
        dl2 = get_datalayer("alice")
        assert dl1 is dl2

    def test_different_actors_get_different_instances(self):
        dl_a = get_datalayer("alice")
        dl_b = get_datalayer("bob")
        assert dl_a is not dl_b

    def test_actor_instance_distinct_from_shared(self):
        dl_shared = get_datalayer()
        dl_alice = get_datalayer("alice")
        assert dl_shared is not dl_alice

    def test_actor_id_assigned_on_scoped_instance(self):
        dl = get_datalayer("vendorco")
        assert dl._actor_id == "vendorco"

    def test_shared_instance_has_no_actor_id(self):
        dl = get_datalayer()
        assert dl._actor_id is None

    def test_get_datalayer_full_uri_is_distinct_from_short_id(self):
        """get_datalayer keyed by full URI is distinct from the short-UUID instance.

        This documents the current (intentional) behavior: trigger routes must
        resolve the canonical actor URI (actor.id_) and pass it to get_datalayer
        so that outbox_handler reads from the same table that record_outbox_item
        wrote to.  If a short UUID is passed instead, a separate (empty) DL is
        returned (BUG-2026040901 — fixed in trigger routes, not here).
        """
        dl_short = get_datalayer("alice", db_path=None)
        dl_full = get_datalayer(
            "https://example.org/actors/alice", db_path=None
        )
        # They ARE different instances — the fix is in the trigger routes
        assert dl_short is not dl_full


# ---------------------------------------------------------------------------
# reset_datalayer()
# ---------------------------------------------------------------------------


class TestResetDatalayer:
    """reset_datalayer() clears one or all cached instances."""

    def test_reset_all_clears_shared_and_per_actor(self):
        dl_shared = get_datalayer()
        dl_alice = get_datalayer("alice")

        reset_datalayer()

        dl_shared_new = get_datalayer()
        dl_alice_new = get_datalayer("alice")

        assert dl_shared_new is not dl_shared
        assert dl_alice_new is not dl_alice

    def test_reset_specific_actor_only(self):
        dl_alice = get_datalayer("alice")
        dl_bob = get_datalayer("bob")

        reset_datalayer("alice")

        dl_alice_new = get_datalayer("alice")
        dl_bob_after = get_datalayer("bob")

        assert dl_alice_new is not dl_alice
        assert dl_bob_after is dl_bob

    def test_reset_nonexistent_actor_is_safe(self):
        reset_datalayer("nobody")  # must not raise
