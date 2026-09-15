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
"""Runtime guard for the call-out seam: reject a ``RUNNING`` return (BT-18-011).

A call-out point backend MUST answer synchronously — its ``update()`` returns
``Status.SUCCESS`` or ``Status.FAILURE`` and MUST NOT return ``Status.RUNNING``
(BT-18-011, the general case of the codebase-wide no-``RUNNING`` invariant from
ADR-0080). In-repo nodes are policed statically by the ``test/architecture``
ratchet; a call-out backend, however, is injected from *outside* the repository
(BT-23-004), so a static scan cannot see it. Only a runtime guard at the seam
can.

:class:`SynchronousCallOut` is that guard: a ``py_trees`` decorator that ticks
its child and raises :class:`CallOutContractError` — a plain ``RuntimeError``,
**not** a :class:`~vultron.errors.VultronError` — when the child returns
``RUNNING``. The non-``VultronError`` type matters: it makes ``BTBridge``
classify the failure via its ``except Exception`` branch as
``internal_error=True`` (a mis-wired backend), rather than its
``except VultronError`` branch (a deliberate protocol outcome). See
``bridge.py``'s two-branch exception handling.

The guard is applied uniformly at the bundle boundary via
:func:`guard_call_out_factory`, so every node a call-out bundle hands out —
core DETERMINISTIC defaults and implementer-injected backends alike — is
guard-wrapped, with no change required in the tree-builder call sites. See
:class:`~vultron.core.behaviors.call_out.bundles.base.CallOutBundle`.

References
----------
- ADR-0080: ``docs/adr/0080-protocol-asks-not-suspended-behaviors.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-18-011
- ``notes/protocol-asks.md`` — "Why there is nothing to suspend"
"""

from __future__ import annotations

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory

#: Sentinel attribute marking a factory returned by :func:`guard_call_out_factory`,
#: so re-wrapping an already-guarded factory (e.g. one bundle's factory passed
#: into another bundle's constructor) is a no-op rather than a nested decorator.
_GUARDED_ATTR = "_vultron_call_out_guarded"


class CallOutContractError(RuntimeError):
    """A call-out backend violated the synchronous-answer contract (BT-18-011).

    Deliberately a plain :class:`RuntimeError` and **not** a
    :class:`~vultron.errors.VultronError`: ``BTBridge`` treats a
    ``VultronError`` as a protocol-attributable ``FAILURE`` but any other
    exception as ``internal_error=True``. A backend that returns
    ``Status.RUNNING`` is a wiring bug, not a protocol outcome, so it must
    surface as an internal error.
    """


class SynchronousCallOut(py_trees.decorators.Decorator):
    """Reject a ``RUNNING`` return from a call-out backend (BT-18-011).

    Ticks the decorated child and returns its status unchanged for
    ``SUCCESS`` / ``FAILURE`` / ``INVALID``. If the child returns
    ``Status.RUNNING`` — which Vultron's execution model cannot suspend on —
    raises :class:`CallOutContractError` naming the offending node.

    The decorator adopts the child's ``name`` so it is transparent to callers
    that navigate a tree by node name; the guarded node remains available as
    ``self.decorated``.
    """

    def __init__(self, child: py_trees.behaviour.Behaviour) -> None:
        # Adopt the child's name so the guard is transparent in tree walks and
        # visualizations; the guarded node is reachable via ``self.decorated``.
        super().__init__(name=child.name, child=child)

    def update(self) -> Status:
        """Pass the child's status through, but forbid ``RUNNING`` (BT-18-011)."""
        status = self.decorated.status
        if status == Status.RUNNING:
            raise CallOutContractError(
                f"Call-out backend {self.decorated.name!r} "
                f"({type(self.decorated).__name__}) returned Status.RUNNING; "
                "a call-out point MUST answer synchronously with SUCCESS or "
                "FAILURE (BT-18-011, ADR-0080)."
            )
        return status


def guard_call_out_factory(
    factory: CallOutBackendFactory,
) -> CallOutBackendFactory:
    """Wrap *factory* so the node it produces is guarded against ``RUNNING``.

    Returns a new :class:`CallOutBackendFactory` whose product is the original
    node wrapped in :class:`SynchronousCallOut`. Idempotent: an already-guarded
    factory is returned unchanged, and a node that is already a
    :class:`SynchronousCallOut` is not double-wrapped.
    """
    if getattr(factory, _GUARDED_ATTR, False):
        return factory

    def guarded(name: str) -> py_trees.behaviour.Behaviour:
        node = factory(name)
        if isinstance(node, SynchronousCallOut):
            return node
        return SynchronousCallOut(node)

    setattr(guarded, _GUARDED_ATTR, True)
    return guarded


def unwrap_call_out(
    node: py_trees.behaviour.Behaviour,
) -> py_trees.behaviour.Behaviour:
    """Return the guarded child of a :class:`SynchronousCallOut`, else *node*.

    Convenience for callers (and tests) that need the underlying backend node
    rather than the transparent guard wrapper.
    """
    if isinstance(node, SynchronousCallOut):
        return node.decorated
    return node


__all__ = [
    "CallOutContractError",
    "SynchronousCallOut",
    "guard_call_out_factory",
    "unwrap_call_out",
]
