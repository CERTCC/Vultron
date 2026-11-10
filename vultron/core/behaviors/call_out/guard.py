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
"""The call-out seam: turn a backend's answer into tree behaviour (ADR-0183).

Every call-out backend gives one answer, *yes*, *no* or *error*, with the data
its capability declares (:mod:`~vultron.core.behaviors.call_out.answer`).
:class:`SynchronousCallOut` is the one place that interprets it:

- *yes* writes the declared outputs to the blackboard and the node succeeds;
- *no* writes the refusal payload to the declared refusal ports and the node
  fails;
- *error* raises :class:`CallOutBackendError`, naming the node, so the message
  is not judged and stays in holding to be tried again.

The seam also rejects an answer that is not a
:class:`~vultron.core.behaviors.call_out.answer.CallOutAnswer`, has a verdict
outside the three, or carries data its declaration does not name, by raising
:class:`CallOutContractError`.  So does a backend that returns
``Status.RUNNING`` (BT-18-011, the general case of the codebase-wide
no-``RUNNING`` invariant from ADR-0080), or one that is not a
:class:`~vultron.core.behaviors.call_out.backend.CallOutBackend`.

Both errors are plain ``RuntimeError`` subclasses, **not**
:class:`~vultron.errors.VultronError`: ``BTBridge`` classifies them via its
``except Exception`` branch as ``internal_error=True``, never as a protocol
``FAILURE``.  A call-out backend is injected from *outside* the repository
(BT-23-004), so only a runtime guard at the seam can police it.

The seam is applied uniformly at the bundle boundary via
:func:`guard_call_out_factory`, so every node a call-out bundle hands out is
guarded, with no change in the tree-builder call sites.  See
:class:`~vultron.core.behaviors.call_out.bundles.base.CallOutBundle`.

References
----------
- ADR-0080: ``docs/adr/0080-protocol-asks-not-suspended-behaviors.md``
- ADR-0183: ``docs/adr/0183-a-call-out-backend-answers-yes-no-or-error-and-the-seam-turns-the-answer-into-tree-behaviour.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-18-002, BT-18-007,
  BT-18-011, BT-18-018
- ``notes/call-out-configuration.md`` — "A Backend Answers Yes, No or Error"
"""

from __future__ import annotations

from collections.abc import Mapping

import py_trees
from py_trees.common import Access, Status

from vultron.core.behaviors.call_out.answer import (
    CallOutAnswer,
    CallOutVerdict,
)
from vultron.core.behaviors.call_out.backend import CallOutBackend
from vultron.core.behaviors.call_out.errors import (
    CallOutBackendError,
    CallOutContractError,
)
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory
from vultron.core.behaviors.node_logger import node_logger

#: Sentinel attribute marking a factory returned by :func:`guard_call_out_factory`,
#: so re-wrapping an already-guarded factory (e.g. one bundle's factory passed
#: into another bundle's constructor) is a no-op rather than a nested decorator.
_GUARDED_ATTR = "_vultron_call_out_guarded"


def _check_data(
    node: str,
    what: str,
    data: Mapping[str, object],
    declared: Mapping[str, type],
) -> None:
    """Raise unless *data* names exactly the *declared* ports, typed."""
    undeclared = sorted(set(data) - set(declared))
    missing = sorted(set(declared) - set(data))
    if undeclared or missing:
        raise CallOutContractError(
            f"Call-out backend {node!r} answered {what} with "
            f"undeclared ports {undeclared} and missing ports {missing}; "
            "an answer carries exactly the ports its declaration names "
            "(BT-18-002, ADR-0183)."
        )
    for key, typ in declared.items():
        value = data[key]
        if (
            isinstance(typ, type)
            and typ is not object
            and not isinstance(value, typ)
        ):
            raise CallOutContractError(
                f"Call-out backend {node!r} answered {what} with "
                f"{key}={type(value).__name__}, not the declared "
                f"{typ.__name__} (ADR-0183)."
            )


class SynchronousCallOut(py_trees.decorators.Decorator):
    """The call-out seam: turns its backend's answer into tree behaviour.

    Ticks the decorated :class:`CallOutBackend`, takes its answer and, per
    ADR-0183, writes the *yes* outputs and returns ``SUCCESS``, writes the *no*
    refusal payload and returns ``FAILURE``, or raises
    :class:`CallOutBackendError` on *error*.  Anything else raises
    :class:`CallOutContractError`.

    The seam adopts the child's ``name`` so it is transparent to callers that
    navigate a tree by node name; the backend remains available as
    ``self.decorated``.
    """

    #: Marks the seam for :class:`CallOutBackend`, which refuses a tick from
    #: any other parent (ADR-0183).
    is_call_out_seam = True

    def __init__(self, child: py_trees.behaviour.Behaviour) -> None:
        if not isinstance(child, CallOutBackend):
            raise CallOutContractError(
                f"Call-out backend {child.name!r} ({type(child).__name__}) is "
                "not a CallOutBackend; a backend answers yes, no or error "
                "through CallOutBackend.answer() (ADR-0183)."
            )
        # Adopt the child's name so the seam is transparent in tree walks and
        # visualizations; the backend is reachable via ``self.decorated``.
        super().__init__(name=child.name, child=child)
        self._backend: CallOutBackend = child
        contract = child.contract
        # Built here, not in setup(), so a tick without setup() still writes
        # the declared data (BT-23-013).
        self._bb = self.attach_blackboard_client(
            name=f"{type(self).__name__}_{child.name}"
        )
        for key in (*contract.outputs, *contract.refusal_ports):
            self._bb.register_key(key, Access.WRITE)

    def update(self) -> Status:
        """Interpret the backend's answer (ADR-0183); forbid ``RUNNING``."""
        backend = self._backend
        if backend.status == Status.RUNNING:
            raise CallOutContractError(
                f"Call-out backend {backend.name!r} "
                f"({type(backend).__name__}) returned Status.RUNNING; "
                "a call-out point MUST answer synchronously (BT-18-011, "
                "ADR-0080)."
            )
        answer = backend.take_answer()
        if not isinstance(answer, CallOutAnswer) or answer.verdict not in (
            CallOutVerdict.YES,
            CallOutVerdict.NO,
            CallOutVerdict.ERROR,
        ):
            raise CallOutContractError(
                f"Call-out backend {backend.name!r} "
                f"({type(backend).__name__}) gave {answer!r}, not a "
                "CallOutAnswer of yes, no or error (ADR-0183)."
            )
        contract = backend.contract
        if answer.verdict is CallOutVerdict.YES:
            _check_data(backend.name, "yes", answer.outputs, contract.outputs)
            for key, value in answer.outputs.items():
                setattr(self._bb, key, value)
            return Status.SUCCESS
        if answer.verdict is CallOutVerdict.NO:
            # The model guarantees a reason on a no answer.
            assert answer.reason is not None
            payload: dict[str, object] = {
                contract.refusal_reason_key: answer.reason,
                **answer.refusal,
            }
            _check_data(backend.name, "no", payload, contract.refusal_ports)
            for key, value in payload.items():
                setattr(self._bb, key, value)
            self.feedback_message = answer.reason
            return Status.FAILURE
        # The model guarantees diagnostics on an error answer.
        assert answer.diagnostics is not None
        node_logger(self).warning(
            "Call-out backend %r answered error; the message is not judged:"
            " %s",
            backend.name,
            answer.diagnostics,
        )
        raise CallOutBackendError(backend.name, answer.diagnostics)


def guard_call_out_factory(
    factory: CallOutBackendFactory,
) -> CallOutBackendFactory:
    """Wrap *factory* so the node it produces sits behind the seam.

    Returns a new :class:`CallOutBackendFactory` whose product is the original
    node wrapped in :class:`SynchronousCallOut`.  A product that is not a
    :class:`CallOutBackend` raises :class:`CallOutContractError` when the tree
    is built.  Idempotent: an already-guarded factory is returned unchanged,
    and a node that is already a :class:`SynchronousCallOut` is not
    double-wrapped.
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
    """Return the backend behind a :class:`SynchronousCallOut`, else *node*.

    Convenience for callers (and tests) that need the underlying backend node
    rather than the transparent seam.
    """
    if isinstance(node, SynchronousCallOut):
        return node.decorated
    return node


__all__ = [
    "CallOutBackendError",
    "CallOutContractError",
    "SynchronousCallOut",
    "guard_call_out_factory",
    "unwrap_call_out",
]
