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

"""Tests for the shared blackboard snapshot/restore helper (#3534).

``BTBridge.execute_with_setup`` and the inbox pipeline both delegate here, so
the two behaviours their callers depend on are pinned once, at the helper, rather
than separately at each call site:

- an absent key is *removed* on restore, never set to ``None`` (BT-17-003
  distinguishes "never written" from "explicitly cleared");
- both the bare and the ``/``-prefixed spelling are covered.
"""

from typing import Any

import py_trees
import pytest

from test.support.blackboard_registry import registry_snapshot
from vultron.core.behaviors.blackboard_scope import (
    key_aliases,
    release_clients,
    release_tree_clients,
    restore_keys,
    snapshot_keys,
)


def test_both_spellings_of_a_key_are_covered() -> None:
    """py_trees stores the bare and namespaced aliases as separate entries."""
    assert key_aliases("activity") == ("activity", "/activity")

    storage: dict[str, Any] = {"activity": "bare", "/activity": "slashed"}
    saved = snapshot_keys(storage, ["activity"])

    assert set(saved) == {"activity", "/activity"}
    assert saved["activity"] == (True, "bare")
    assert saved["/activity"] == (True, "slashed")


def test_a_present_key_is_restored_to_its_original_value() -> None:
    storage: dict[str, Any] = {"/actor_id": "outer-actor"}
    saved = snapshot_keys(storage, ["actor_id"])

    storage["/actor_id"] = "inner-actor"
    restore_keys(storage, saved)

    assert storage["/actor_id"] == "outer-actor"


def test_a_key_absent_before_is_removed_rather_than_set_to_none() -> None:
    """The distinction a plain value map would destroy.

    A consumer that treats ``KeyError`` and ``None`` as different answers — the
    BT-17-003 no-op sentinel contract does — would see "explicitly cleared"
    where the truth is "never written".
    """
    storage: dict[str, Any] = {}
    saved = snapshot_keys(storage, ["case_id"])

    storage["case_id"] = "written-during-execution"
    storage["/case_id"] = "written-during-execution"
    restore_keys(storage, saved)

    assert "case_id" not in storage
    assert "/case_id" not in storage


def test_a_key_holding_none_is_restored_as_none_not_removed() -> None:
    """The converse: ``None`` was a real value and must come back as one."""
    storage: dict[str, Any] = {"/rm_transition_anomaly": None}
    saved = snapshot_keys(storage, ["rm_transition_anomaly"])

    storage["/rm_transition_anomaly"] = {"anomaly_type": "stale"}
    restore_keys(storage, saved)

    assert "/rm_transition_anomaly" in storage
    assert storage["/rm_transition_anomaly"] is None


def test_a_duplicated_key_collapses_to_one_entry() -> None:
    """``managed_keys`` may list a key twice once context_data is appended."""
    storage: dict[str, Any] = {"/activity": "outer"}
    saved = snapshot_keys(storage, ["activity", "activity"])

    assert set(saved) == {"activity", "/activity"}
    assert saved["/activity"] == (True, "outer")


def test_restoring_an_empty_snapshot_touches_nothing() -> None:
    storage: dict[str, Any] = {"/unmanaged": "left alone"}
    restore_keys(storage, snapshot_keys(storage, []))

    assert storage == {"/unmanaged": "left alone"}


@pytest.mark.parametrize("key", ["a/b", "1bad", "dash-key", ""])
def test_a_non_identifier_key_round_trips(key: str) -> None:
    """``**context_data`` keys reach here unvalidated, so do not assume identifiers."""
    storage: dict[str, Any] = {}
    saved = snapshot_keys(storage, [key])

    for alias in key_aliases(key):
        storage[alias] = "inner"
    restore_keys(storage, saved)

    for alias in key_aliases(key):
        assert alias not in storage


def test_nesting_restores_the_outer_value_not_the_innermost() -> None:
    """The re-entrancy the bridge relies on: each level undoes only its own write."""
    storage: dict[str, Any] = {"/actor_id": "outer"}

    outer_saved = snapshot_keys(storage, ["actor_id"])
    storage["/actor_id"] = "middle"

    inner_saved = snapshot_keys(storage, ["actor_id"])
    storage["/actor_id"] = "inner"

    restore_keys(storage, inner_saved)
    assert storage["/actor_id"] == "middle"

    restore_keys(storage, outer_saved)
    assert storage["/actor_id"] == "outer"


def _client(name: str) -> py_trees.blackboard.Client:
    client = py_trees.blackboard.Client(name=name)
    client.register_key(key="actor_id", access=py_trees.common.Access.WRITE)
    return client


def test_a_released_client_leaves_the_registry_and_its_key_metadata() -> None:
    """Both process-global maps drop the client (#6727)."""
    before = registry_snapshot()

    release_clients([_client("released")])

    gained = registry_snapshot().gained_since(before)
    assert not gained, gained.describe()


def test_releasing_a_client_keeps_the_value_it_wrote() -> None:
    """Storage belongs to ``restore_keys``; release never clears it."""
    client = _client("writer")
    client.actor_id = "kept"

    release_clients([client])

    assert py_trees.blackboard.Blackboard.storage["/actor_id"] == "kept"


def test_releasing_a_client_twice_changes_nothing() -> None:
    """A seam may release its own client before the run ends (BT-18)."""
    client = _client("twice")
    release_clients([client])
    before = registry_snapshot()

    release_clients([client])

    assert registry_snapshot() == before


def test_a_client_whose_registry_was_cleared_is_skipped() -> None:
    """``Blackboard.clear()`` may run between a client's build and release."""
    client = _client("cleared")
    py_trees.blackboard.Blackboard.clear()

    release_clients([client])

    assert not registry_snapshot()


def test_releasing_a_tree_reaches_every_node_and_keeps_other_clients() -> None:
    """Each node's attached clients are released, and nothing outside the tree."""
    outside = _client("outside")
    leaf = py_trees.behaviours.Success(name="leaf")
    leaf.attach_blackboard_client(name="leaf").register_key(
        key="actor_id", access=py_trees.common.Access.READ
    )
    root = py_trees.decorators.Inverter(name="root", child=leaf)
    root.attach_blackboard_client(name="root")
    tree_ids = {c.id() for node in root.iterate() for c in node.blackboards}

    release_tree_clients(root)

    registered = set(py_trees.blackboard.Blackboard.clients)
    assert outside.id() in registered
    assert len(tree_ids) == 2
    assert not tree_ids & registered


def test_a_client_with_two_keys_remapped_onto_one_is_released() -> None:
    """An input and an output port may share one blackboard key.

    ``Client.unregister`` deletes the shared key's metadata on the first local
    key and raises ``KeyError`` on the second; the release must not.
    """
    client = py_trees.blackboard.Client(name="ports")
    client.register_key(
        key="record_in",
        access=py_trees.common.Access.READ,
        remap_to="/record",
    )
    client.register_key(
        key="record_out",
        access=py_trees.common.Access.WRITE,
        remap_to="/record",
    )
    before = registry_snapshot()

    release_clients([client])

    assert client.id() not in py_trees.blackboard.Blackboard.clients
    assert "/record" not in py_trees.blackboard.Blackboard.metadata
    assert before.gained_since(registry_snapshot()).clients == {client.id()}


def test_releasing_one_client_keeps_another_clients_registration() -> None:
    """A key two clients registered keeps the one not released."""
    reader = py_trees.blackboard.Client(name="reader")
    reader.register_key(key="actor_id", access=py_trees.common.Access.READ)
    writer = _client("writer")

    release_clients([writer])

    meta = py_trees.blackboard.Blackboard.metadata["/actor_id"]
    assert reader.id() in meta.read
    assert writer.id() not in meta.write
