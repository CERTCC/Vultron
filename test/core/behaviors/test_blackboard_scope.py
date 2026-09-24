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

import pytest

from vultron.core.behaviors.blackboard_scope import (
    key_aliases,
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
    storage: dict[str, Any] = {"/ledger_payload_object_override": None}
    saved = snapshot_keys(storage, ["ledger_payload_object_override"])

    storage["/ledger_payload_object_override"] = {"object_id": "stale"}
    restore_keys(storage, saved)

    assert "/ledger_payload_object_override" in storage
    assert storage["/ledger_payload_object_override"] is None


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
