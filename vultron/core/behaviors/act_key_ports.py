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

"""Input ports that read per-act keys, and the reads a node makes on them.

A node reads each per-act value from a key of the vocabulary
(:mod:`vultron.core.behaviors.act_keys`), never from a constructor argument
(BTND-01-008, BTND-01-009).  The helpers here declare such ports and read
them, so every moved node declares and reads them the same way:

- :func:`act_key_ports` declares one input port per key, named for the key;
- :func:`act_key_remappings` binds each port to the key's absolute path,
  for a node's ``_domain_port_remappings()`` hook (BTND-03-010);
- :func:`act_value` reads a key the node cannot run without, and raises a
  wiring error when nothing seeded or published it (BT-25-008);
- :func:`optional_act_value` reads a key the node falls back from by a
  documented tick-time step, such as reading the case off ``/activity``.

The ports declare ``object``, not the key's own type: a value's type is
checked where the runner seeds the key from the act (BT-25-007), so a tree
a test builds from stand-in values runs as it did when the value was a
constructor argument (as :class:`~vultron.core.behaviors.act_key_scope
.ActKeyScope` does).
"""

from typing import Protocol, cast

from py_trees.ports import PortInformation

from vultron.core.behaviors.act_keys import ActKey
from vultron.errors import VultronWiringError

__all__ = [
    "ReadsOptionalPorts",
    "act_key_ports",
    "act_key_remappings",
    "act_value",
    "optional_act_value",
]


class ReadsOptionalPorts(Protocol):
    """A ports node with the shared optional-port read (BTND-03-021)."""

    @property
    def name(self) -> str: ...

    def _try_get_input(self, key: str) -> object | None: ...


def act_key_ports(*keys: ActKey) -> dict[str, PortInformation]:
    """One optional input port per key of *keys*, named for the key.

    Optional, so ``setup()`` never raises on an unseeded key; the read
    (:func:`act_value`) decides whether absence is a fault.
    """
    return {
        key.name: PortInformation(data_type=object, required=False)
        for key in keys
    }


def act_key_remappings(*keys: ActKey) -> dict[str, str]:
    """Each port of :func:`act_key_ports` bound to its key's path."""
    return {key.name: key.path for key in keys}


def optional_act_value[T](
    node: ReadsOptionalPorts,
    key: ActKey,
    kind: type[T],
    *,
    port: str | None = None,
) -> T | None:
    """The value on *node*'s port for *key*, or ``None`` when it is absent.

    An empty string is no value ("if present, then non-empty", CS-08-002).

    Args:
        node: The node reading its port.
        key: The vocabulary key the port is bound to.
        kind: The type the value must have.
        port: The port's name, when it is not the key's (a node that also
            publishes an output port of the key's name).

    Raises:
        VultronWiringError: The value is not a *kind*; something wrote the
            wrong thing to the key, which is never "not supplied".
    """
    value = node._try_get_input(port or key.name)
    if value is None or value == "":
        return None
    if not isinstance(value, kind):
        raise VultronWiringError(
            f"{node.name}: '{key.path}' holds a {type(value).__name__}, not"
            f" a {kind.__name__} (BTND-03-022)"
        )
    return cast(T, value)


def act_value[T](
    node: ReadsOptionalPorts,
    key: ActKey,
    kind: type[T],
    *,
    port: str | None = None,
) -> T:
    """The value on *node*'s port for *key*, which the node cannot run without.

    The arguments are :func:`optional_act_value`'s.

    Raises:
        VultronWiringError: Nothing seeded or published *key* for this
            tick, or it holds something other than a *kind*.  A composition
            fault, never the sender's doing, so ``BTBridge`` reports it as
            an internal error (BT-25-008).
    """
    value = optional_act_value(node, key, kind, port=port)
    if value is None:
        raise VultronWiringError(
            f"{node.name}: nothing seeded or published '{key.path}' for this"
            " node; a factory that holds the value seeds it with"
            " with_act_keys (BTND-01-008, BT-25-008)"
        )
    return value
