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

"""One place that snapshots and restores process-global blackboard keys.

``py_trees.blackboard.Blackboard.storage`` is process-global, so anything a BT
execution writes there outlives that execution unless something puts the previous
value back.  Two callers need exactly that guarantee and each had its own copy of
it (#3534, CS-22-001):

- ``BTBridge.execute_with_setup`` — the execution-scoped keys of BT-17-007.
- ``vultron.core.behaviors.inbox._process_payload`` — the inbox pipeline keys.

The two key sets are disjoint, so the copies never conflicted at runtime.  The
cost was that a fix to one did not reach the other, and this logic has a
demonstrated history of one-line omissions: #3161 (``activity`` and the
``context_data`` keys) and #3516 (``actor_id``) were the same defect found twice,
both in the bridge copy alone.

Two details are load-bearing and easy to get wrong independently in a
re-implementation, which is the specific reason to have one implementation:

1. **Absent is not the same as ``None``.** A key that did not exist before must
   be *removed* afterwards, not set to ``None`` — a consumer that distinguishes
   ``KeyError`` from ``None`` (the BT-17-003 no-op sentinel contract) sees a
   different answer otherwise.  Hence the ``(was_present, value)`` pair rather
   than a plain value map.
2. **Both key spellings.** py_trees' port machinery reads and writes the
   ``/``-prefixed alias while direct ``Blackboard.storage`` access often uses the
   bare name.  Restoring one spelling and not the other leaves the key visible
   through the path that was missed.

The same two callers also release the run's blackboard *clients*
(:func:`release_clients`, :func:`release_tree_clients`).  py_trees records
every ``Client`` in two more process-global maps, ``Blackboard.clients`` and
each key's ``Blackboard.metadata`` reader and writer sets, and only
``Client.unregister()`` takes it out: collecting the ``Client`` does not.  A
run that leaves its clients registered grows both maps by one entry per node,
for the life of the process (#6727).
"""

from collections.abc import Iterable
from typing import Any

import py_trees

#: A key's pre-execution state: whether it was present, and what it held.
KeyState = tuple[bool, Any]


def key_aliases(key: str) -> tuple[str, str]:
    """Return both spellings py_trees may store *key* under.

    The bare name and the ``/``-prefixed namespaced alias are distinct dict
    entries in ``Blackboard.storage``, and which one a given access path uses
    depends on whether it went through a ``Client``/port or straight to
    ``storage``.  Anything that claims to reset a key has to cover both.
    """
    return key, f"/{key}"


def snapshot_keys(
    storage: dict[str, Any], keys: Iterable[str]
) -> dict[str, KeyState]:
    """Record the current state of every alias of every key in *keys*.

    Args:
        storage: The process-global blackboard dict
            (``py_trees.blackboard.Blackboard.storage``).
        keys: Bare key names.  Duplicates are harmless — the result is keyed by
            alias, so a key listed twice collapses to one entry.

    Returns:
        ``{alias: (was_present, value)}`` for both spellings of each key,
        suitable for passing straight to :func:`restore_keys`.
    """
    return {
        alias: (alias in storage, storage.get(alias))
        for key in keys
        for alias in key_aliases(key)
    }


def restore_keys(storage: dict[str, Any], saved: dict[str, KeyState]) -> None:
    """Put every alias in *saved* back to the state :func:`snapshot_keys` recorded.

    A key that was absent is removed rather than set to ``None``, so the
    "never written" and "explicitly cleared" cases stay distinguishable to a
    consumer (BT-17-003).

    Args:
        storage: The process-global blackboard dict.
        saved: The mapping returned by :func:`snapshot_keys`.
    """
    for alias, (was_present, value) in saved.items():
        if was_present:
            storage[alias] = value
        else:
            storage.pop(alias, None)


def release_clients(clients: Iterable[py_trees.blackboard.Client]) -> None:
    """Take each of *clients* out of py_trees' process-global registry.

    Drops the client's id from ``Blackboard.clients`` and from the reader,
    writer and exclusive sets of every key it registered, and deletes a key's
    metadata once no client holds it, as ``Client.unregister`` would.  It keeps
    every value the client wrote: ``storage`` is :func:`restore_keys`'s to put
    back, and a value a run hands its caller is read after the run ends.

    Not ``Client.unregister`` itself: py_trees deletes a key's metadata on the
    first of two local keys remapped onto it, then raises ``KeyError`` on the
    second, and a node whose input and output ports share one blackboard key
    has exactly that (``_SignEmbargoConsentLeafNode``).

    A client the registry no longer holds is skipped: a seam may release its
    own client early, and ``Blackboard.clear()`` may have dropped the whole
    registry since the client was built.

    Args:
        clients: Clients whose registrations end now.
    """
    board = py_trees.blackboard.Blackboard
    for client in clients:
        uid = client.id()
        if uid not in board.clients:
            continue
        # A Client answers attribute reads as blackboard keys, so its own
        # bookkeeping is read past that override, as py_trees itself does.
        remappings: dict[str, str] = object.__getattribute__(
            client, "remappings"
        )
        for key in set(remappings.values()):
            meta = board.metadata.get(key)
            if meta is None:
                continue
            for ids in (meta.read, meta.write, meta.exclusive):
                ids.discard(uid)
            if not (meta.read or meta.write or meta.exclusive):
                del board.metadata[key]
        for registered in ("read", "write", "exclusive", "required"):
            object.__getattribute__(client, registered).clear()
        remappings.clear()
        del board.clients[uid]


def release_tree_clients(root: py_trees.behaviour.Behaviour) -> None:
    """Release the client of every node under *root*, *root* included.

    A tree is built for one run (BT-01-002), so the run that executes it
    releases it once its ticks are done.  The clients a node attached are
    detached too, so a later ``setup()`` attaches fresh ones instead of
    appending to released ones.

    Args:
        root: The tree whose run has ended.
    """
    for node in root.iterate():
        release_clients(node.blackboards)
        node.blackboards.clear()
