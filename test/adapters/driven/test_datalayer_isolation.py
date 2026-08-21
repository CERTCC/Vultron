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
"""Tests for per-actor DataLayer isolation (ADR-0012 ACT-2).

Covers actor_id scoping via the SQLite ``actor_id`` column, inbox/outbox
isolation, record_outbox_item cross-scope queuing, and get_datalayer("https://test.example/api/v2/actors/test-actor")
caching behaviour.
"""

import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    get_datalayer,
    reset_datalayer,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.ports.datalayer import StorableRecord


def _record(id_: str, type_: str = "Note") -> StorableRecord:
    """Helper to build a minimal StorableRecord for testing."""
    return StorableRecord(id_=id_, type_=type_, data_={"id_": id_})


def _record_obj(
    id_: str, type_: str = "VulnerabilityCase", summary: str | None = None
) -> VulnerabilityCase:
    """Helper to build a typed domain object for ``save()``.

    ``save()`` takes a ``PersistableModel``, not a ``StorableRecord``, so the
    cross-actor tests need a real core object rather than ``_record``.
    """
    assert type_ == "VulnerabilityCase", f"unsupported test type {type_!r}"
    return VulnerabilityCase(id_=id_, summary=summary)


@pytest.fixture(autouse=True)
def reset_instances():
    """Ensure each test starts with a clean set of DataLayer instances."""
    reset_datalayer()
    yield
    reset_datalayer()


# ---------------------------------------------------------------------------
# Actor-id scoping — SQLite stores actor_id as a column (not table prefix)
# ---------------------------------------------------------------------------


class TestActorIdScoping:
    """Every DataLayer belongs to exactly one actor (ADR-0070)."""

    def test_actor_id_is_required(self):
        """There is no unscoped DataLayer to construct.

        Replaces a test that asserted ``dl._actor_id is None`` for a
        shared/admin instance.  That instance was the leak: it could read across
        actors, which CM-01-001 forbids.  The mode is now unreachable rather
        than merely discouraged.
        """
        with pytest.raises(TypeError):
            SqliteDataLayer("sqlite:///:memory:")  # type: ignore[call-arg]

    def test_actor_id_set_for_scoped_datalayer(self):
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id="alice")
        assert dl._actor_id == "alice"

    def test_different_actors_have_different_actor_ids(self):
        dl_a = SqliteDataLayer("sqlite:///:memory:", actor_id="alice")
        dl_b = SqliteDataLayer("sqlite:///:memory:", actor_id="bob")
        assert dl_a._actor_id != dl_b._actor_id


# ---------------------------------------------------------------------------
# Record isolation: writes to one actor are invisible to another
# (file-backed so both actors share the same DB)
# ---------------------------------------------------------------------------


class TestRecordIsolation:
    """Records written to actor-scoped DataLayer are invisible to other actors.

    Uses a shared file-backed database so that actor-level isolation can be
    verified against the same underlying storage.
    """

    @pytest.fixture
    def shared_db(self, tmp_path):
        """Return a SQLite URL pointing to a shared file-backed database."""
        return f"sqlite:///{tmp_path / 'shared.sqlite'}"

    def test_actor_a_record_not_visible_from_actor_b(self, shared_db):
        dl_a = SqliteDataLayer(shared_db, actor_id="alice")
        dl_b = SqliteDataLayer(shared_db, actor_id="bob")

        dl_a.create(_record("https://example.org/r/001"))
        result = dl_b.read("https://example.org/r/001")
        assert result is None

    def test_no_global_view_exists(self, shared_db):
        """No DataLayer can read across actors.

        Replaces ``test_actor_a_record_visible_from_shared_datalayer``, which
        asserted the opposite — that a shared "admin" DL was a global view.
        That assertion encoded the CM-01-001 violation as intended behaviour.
        """
        dl_a = SqliteDataLayer(shared_db, actor_id="alice")
        dl_a.create(_record("https://example.org/r/002"))

        dl_b = SqliteDataLayer(shared_db, actor_id="bob")
        assert dl_b.read("https://example.org/r/002") is None

    def test_actor_a_record_visible_to_itself(self, shared_db):
        dl_a = SqliteDataLayer(shared_db, actor_id="alice")

        dl_a.create(_record("https://example.org/r/003"))
        result = dl_a.read("https://example.org/r/003")
        assert result is not None


# ---------------------------------------------------------------------------
# Inbox methods
# ---------------------------------------------------------------------------


class TestCrossActorReplicaIsolation:
    """Two actors sharing one configured store each hold their own replica.

    Regression coverage for issue #2238 / CM-01-001 ("each actor MUST have an
    isolated protocol state domain").  ``create()`` decided "already exists"
    with an **unscoped** primary-key lookup while ``read()`` was actor-scoped,
    so the second actor's ``create()`` raised ``ValueError`` and left that
    actor with no replica row it could read.  ``save()`` had the same unscoped
    lookup but no error, so one actor's write silently landed in another
    actor's row.

    Both are deployed topologies, not hypotheticals: a single container hosts
    an actor plus the CaseActors it self-hosts (CP-08-003), and single-server
    demo mode runs every actor against one configured store.
    """

    ACTOR_A = "https://a.example/api/v2/actors/a"
    ACTOR_B = "https://b.example/api/v2/actors/b"
    CASE_ID = "urn:uuid:11111111-1111-1111-1111-111111111111"

    @pytest.fixture
    def db_url(self, tmp_path):
        """One configured storage location shared by both actors."""
        return f"sqlite:///{tmp_path / 'vultron.sqlite'}"

    def test_both_actors_can_create_the_same_object_id(self, db_url):
        """Neither actor's create() may be refused because of the other's."""
        dl_a = SqliteDataLayer(db_url, actor_id=self.ACTOR_A)
        dl_b = SqliteDataLayer(db_url, actor_id=self.ACTOR_B)

        dl_a.create(_record(self.CASE_ID, "VulnerabilityCase"))
        # Before #2238 this raised ValueError: the existence check was a bare
        # primary-key get that saw actor A's row.
        dl_b.create(_record(self.CASE_ID, "VulnerabilityCase"))

        assert dl_a.read(self.CASE_ID) is not None
        assert dl_b.read(self.CASE_ID) is not None

    def test_second_actor_can_read_back_its_own_replica(self, db_url):
        """A replica the actor created MUST be readable by that actor."""
        dl_a = SqliteDataLayer(db_url, actor_id=self.ACTOR_A)
        dl_b = SqliteDataLayer(db_url, actor_id=self.ACTOR_B)

        dl_a.create(_record(self.CASE_ID, "VulnerabilityCase"))
        dl_b.save(_record_obj(self.CASE_ID, "VulnerabilityCase"))

        assert dl_b.read(self.CASE_ID) is not None, (
            "actor B wrote its own replica and cannot read it back — the write"
            " landed in another actor's row (#2238)"
        )

    def test_one_actors_write_cannot_change_what_another_reads(self, db_url):
        """The core invariant: writes never cross the actor boundary."""
        dl_a = SqliteDataLayer(db_url, actor_id=self.ACTOR_A)
        dl_b = SqliteDataLayer(db_url, actor_id=self.ACTOR_B)

        dl_a.create(
            StorableRecord(
                id_=self.CASE_ID,
                type_="VulnerabilityCase",
                data_={"id_": self.CASE_ID, "summary": "A's view"},
            )
        )
        before = dl_a.read(self.CASE_ID)

        dl_b.save(_record_obj(self.CASE_ID, "VulnerabilityCase", "B's view"))

        after = dl_a.read(self.CASE_ID)
        assert after is not None, "actor B's write deleted actor A's row"
        assert getattr(after, "summary", None) == getattr(
            before, "summary", None
        ), "actor B's write mutated what actor A reads (CM-01-001)"


# ---------------------------------------------------------------------------
# Inbox methods
# ---------------------------------------------------------------------------


class TestInboxMethods:
    """Per-actor DataLayer inbox_append / inbox_list / inbox_pop."""

    def test_inbox_starts_empty(self):
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id="alice")
        assert dl.inbox_list() == []

    def test_inbox_append_then_list(self):
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id="alice")
        dl.inbox_append("https://example.org/activities/001")
        items = dl.inbox_list()
        assert items == ["https://example.org/activities/001"]

    def test_inbox_append_multiple(self):
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id="alice")
        dl.inbox_append("https://example.org/activities/001")
        dl.inbox_append("https://example.org/activities/002")
        assert len(dl.inbox_list()) == 2

    def test_inbox_pop_returns_first_then_removes(self):
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id="alice")
        dl.inbox_append("https://example.org/activities/001")
        dl.inbox_append("https://example.org/activities/002")
        first = dl.inbox_pop()
        assert first == "https://example.org/activities/001"
        remaining = dl.inbox_list()
        assert len(remaining) == 1

    def test_inbox_pop_on_empty_returns_none(self):
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id="alice")
        assert dl.inbox_pop() is None

    def test_inbox_is_isolated_between_actors(self):
        dl_a = SqliteDataLayer("sqlite:///:memory:", actor_id="alice")
        dl_b = SqliteDataLayer("sqlite:///:memory:", actor_id="bob")

        dl_a.inbox_append("https://example.org/activities/for-alice")
        assert dl_b.inbox_list() == []


# ---------------------------------------------------------------------------
# Outbox methods
# ---------------------------------------------------------------------------


class TestOutboxMethods:
    """Per-actor DataLayer outbox_append / outbox_list / outbox_pop."""

    def test_outbox_starts_empty(self):
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id="alice")
        assert dl.outbox_list() == []

    def test_outbox_append_then_list(self):
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id="alice")
        dl.outbox_append("https://example.org/activities/sent-001")
        items = dl.outbox_list()
        assert items == ["https://example.org/activities/sent-001"]

    def test_outbox_pop_returns_first_then_removes(self):
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id="alice")
        dl.outbox_append("https://example.org/activities/sent-001")
        dl.outbox_append("https://example.org/activities/sent-002")
        first = dl.outbox_pop()
        assert first == "https://example.org/activities/sent-001"
        assert len(dl.outbox_list()) == 1

    def test_outbox_pop_on_empty_returns_none(self):
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id="alice")
        assert dl.outbox_pop() is None

    def test_outbox_is_isolated_between_actors(self):
        dl_a = SqliteDataLayer("sqlite:///:memory:", actor_id="alice")
        dl_b = SqliteDataLayer("sqlite:///:memory:", actor_id="bob")

        dl_a.outbox_append("https://example.org/activities/from-alice")
        # dl_b is on a different in-memory DB; its outbox is empty
        assert dl_b.outbox_list() == []


# ---------------------------------------------------------------------------
# record_outbox_item — cross-scope outbox queueing
# ---------------------------------------------------------------------------


class TestOutboxIsPerActorStore:
    """Outbox queues live in their owning actor's store.

    Replaces ``TestRecordOutboxItem``.  ``record_outbox_item(actor_id, id)``
    existed so an *unscoped* DataLayer could name whose queue to touch, and its
    tests asserted that alice's DL could write into bob's queue.  With a
    mandatory actor scope the method is exactly ``outbox_append`` and the
    cross-actor write it enabled is gone (ADR-0070).

    This also retires BUG-2026040901 structurally: there is one store per actor,
    so a queue can no longer be written under one spelling of an actor id and
    read under another.
    """

    @pytest.fixture
    def shared_db(self, tmp_path):
        return f"sqlite:///{tmp_path / 'shared.sqlite'}"

    def test_outbox_append_reaches_only_its_own_actor(self, shared_db):
        dl_alice = SqliteDataLayer(shared_db, actor_id="alice")
        dl_bob = SqliteDataLayer(shared_db, actor_id="bob")

        activity_id = "https://example.org/activities/test-001"
        dl_alice.outbox_append(activity_id)

        assert dl_alice.outbox_list() == [activity_id]
        assert dl_bob.outbox_list() == []

    def test_queues_do_not_mix(self, shared_db):
        dl_alice = SqliteDataLayer(shared_db, actor_id="alice")
        dl_bob = SqliteDataLayer(shared_db, actor_id="bob")

        dl_alice.outbox_append("https://example.org/activities/for-alice")
        dl_bob.outbox_append("https://example.org/activities/for-bob")

        assert dl_alice.outbox_list() == [
            "https://example.org/activities/for-alice"
        ]
        assert dl_bob.outbox_list() == [
            "https://example.org/activities/for-bob"
        ]

    def test_no_cross_actor_enqueue_method_remains(self, shared_db):
        """The explicit-actor enqueue form is gone from the adapter."""
        dl_alice = SqliteDataLayer(shared_db, actor_id="alice")
        assert not hasattr(dl_alice, "record_outbox_item")
        assert not hasattr(dl_alice, "outbox_list_for_actor")


class TestGetDatalayerFactory:
    """get_datalayer() returns per-actor cached instances."""

    def test_shared_datalayer_is_singleton(self):
        dl1 = get_datalayer("https://test.example/api/v2/actors/test-actor")
        dl2 = get_datalayer("https://test.example/api/v2/actors/test-actor")
        assert dl1 is dl2

    def test_actor_datalayer_is_cached(self):
        dl1 = get_datalayer("alice")
        dl2 = get_datalayer("alice")
        assert dl1 is dl2

    def test_different_actors_get_different_instances(self):
        dl_a = get_datalayer("alice")
        dl_b = get_datalayer("bob")
        assert dl_a is not dl_b

    def test_instances_for_two_actors_are_distinct(self):
        dl_test_actor = get_datalayer(
            "https://test.example/api/v2/actors/test-actor"
        )
        dl_alice = get_datalayer("alice")
        assert dl_test_actor is not dl_alice

    def test_actor_id_assigned_on_scoped_instance(self):
        dl = get_datalayer("vendorco")
        assert dl._actor_id == "vendorco"

    def test_every_instance_carries_the_actor_it_was_asked_for(self):
        """There is no instance without an actor id (AC-2, at the factory).

        This replaces ``test_shared_instance_has_no_actor_id``, which asserted
        that ``get_datalayer`` could hand back an instance whose ``_actor_id``
        was ``None``.  That was the shared DataLayer, and ADR-0070 deletes it:
        the argument is mandatory and is always the instance's own actor, so the
        old assertion described a state the factory can no longer reach.
        """
        for actor_id in (
            "alice",
            "vendorco",
            "https://test.example/api/v2/actors/test-actor",
        ):
            assert get_datalayer(actor_id)._actor_id == actor_id

        with pytest.raises(TypeError):
            get_datalayer()  # type: ignore[call-arg]

    def test_get_datalayer_full_uri_is_distinct_from_short_id(self):
        """get_datalayer keyed by full URI is distinct from the short-UUID instance.

        This documents the current (intentional) behavior: trigger routes must
        resolve the canonical actor URI (actor.id_) and pass it to get_datalayer
        so that outbox_handler reads from the same queue that record_outbox_item
        wrote to.  If a short UUID is passed instead, a separate (empty) DL is
        returned (BUG-2026040901 — fixed in trigger routes, not here).
        """
        dl_short = get_datalayer("alice")
        dl_full = get_datalayer("https://example.org/actors/alice")
        assert dl_short is not dl_full


# ---------------------------------------------------------------------------
# reset_datalayer()
# ---------------------------------------------------------------------------


class TestResetDatalayer:
    """reset_datalayer() clears one or all cached instances."""

    def test_reset_all_clears_shared_and_per_actor(self):
        dl_shared = get_datalayer(
            "https://test.example/api/v2/actors/test-actor"
        )
        dl_alice = get_datalayer("alice")

        reset_datalayer()

        dl_shared_new = get_datalayer(
            "https://test.example/api/v2/actors/test-actor"
        )
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
