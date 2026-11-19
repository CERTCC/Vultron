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
"""Check that a node reading act keys refuses to run with one unseeded.

A node that takes its per-act values from act keys (BTND-01-008) and is
ticked with no seed for a key it requires is a composition fault: the shared
read (:func:`~vultron.core.behaviors.act_key_ports.act_value`) raises a
wiring error naming the key (BT-25-008).  A test module lists each node with
the keys it cannot run without, expands the list with
:func:`unseeded_key_cases`, and ticks each case with
:func:`assert_unseeded_key_raises` inside :func:`restored_act_keys`.
"""

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager

import py_trees
import pytest

from test.support.act_runner import in_act
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.act_keys import ACT_KEYS, ActKey
from vultron.errors import VultronWiringError

#: Builds a node from configuration alone.
NodeBuild = Callable[[], py_trees.behaviour.Behaviour]

#: One case: the node, the key left unseeded, and every key it requires.
UnseededKeyCase = tuple[NodeBuild, ActKey, tuple[ActKey, ...]]

_ACTOR_ID = "https://example.org/users/vendor"


def unseeded_key_cases(
    nodes: Sequence[tuple[NodeBuild, tuple[ActKey, ...]]],
) -> list[UnseededKeyCase]:
    """Each (node, required key) pair, the key left unseeded once."""
    return [(build, key, keys) for build, keys in nodes for key in keys]


def unseeded_key_case_ids(cases: Sequence[UnseededKeyCase]) -> list[str]:
    """A readable test id per case: ``<NodeClass>-<key name>``."""
    return [f"{type(build()).__name__}-{key.name}" for build, key, _ in cases]


@contextmanager
def restored_act_keys() -> Iterator[None]:
    """Put every act key back on the blackboard as it was."""
    storage = py_trees.blackboard.Blackboard.storage
    saved = {
        k.path: storage[k.path] for k in ACT_KEYS.values() if k.path in storage
    }
    try:
        yield
    finally:
        for key in ACT_KEYS.values():
            storage.pop(key.path, None)
        storage.update(saved)


def assert_unseeded_key_raises(
    build: NodeBuild, key: ActKey, keys: tuple[ActKey, ...]
) -> None:
    """Tick *build*'s node with *key* unseeded and every other key seeded.

    Raises:
        AssertionError: The tick did not raise a wiring error naming *key*.
    """
    node = build()
    storage = py_trees.blackboard.Blackboard.storage
    for other in keys:
        if other is not key:
            storage[other.path] = "urn:uuid:stand-in"
    storage.pop(key.path, None)
    py_trees.blackboard.Blackboard.enable_activity_stream()
    client = py_trees.blackboard.Client(name="act-key-inputs")
    for name in ("datalayer", "actor_id"):
        client.register_key(key=name, access=py_trees.common.Access.WRITE)
    client.datalayer = SqliteDataLayer(
        "sqlite:///:memory:", actor_id=_ACTOR_ID
    )
    client.actor_id = _ACTOR_ID
    tree = py_trees.trees.BehaviourTree(root=node)
    tree.setup()

    with in_act(), pytest.raises(VultronWiringError, match=key.path):
        tree.tick()
