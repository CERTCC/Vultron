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
"""Architecture test: a node with an act-key port takes no such argument.

A node that declares an input port for a key of the act-key vocabulary
(:mod:`vultron.core.behaviors.act_keys`) reads that value from the
blackboard in some tree.  BTND-01-006 and BTND-01-007 say it then reads it
from that port in every tree, never also from a constructor argument: a
constructor value with a port fallback is the dual channel that let a
``/case_id`` left by one delivery decide a later delivery's path (#5803).  A
tree that knows the value at build time seeds the port with
:func:`~vultron.core.behaviors.act_key_scope.with_act_keys` instead
(BTND-10-005, ADR-0089).

A port reads a vocabulary key when its name is the key's name, or when the
class's ``_domain_port_remappings()`` binds it to the key's path.  A binding
made per instance (``_instance_port_remappings()``) needs a built node, so it
is not read here.

The check is over every ``PortsMixin`` class under ``vultron.core.behaviors``,
found by import rather than by a list of names, so a new node with both
channels fails it whatever it is called.
"""

import importlib
import inspect
import pkgutil
from collections.abc import Mapping

import pytest
from py_trees.ports import PortsMixin

import vultron.core.behaviors
from test.support.signatures import signature_of
from vultron.core.behaviors.act_keys import ACT_KEYS, CASE_ID, ActKey
from vultron.subclasses import all_subclasses


def _import_all_behavior_modules() -> None:
    for info in pkgutil.walk_packages(
        vultron.core.behaviors.__path__, "vultron.core.behaviors."
    ):
        importlib.import_module(info.name)


def act_key_ports(cls: type) -> dict[str, ActKey]:
    """Each input port of *cls* that reads a vocabulary key, with the key."""
    ports: Mapping[str, object] = getattr(cls, "INPUT_PORTS", None) or {}
    remaps_of = getattr(cls, "_domain_port_remappings", None)
    remaps = remaps_of() if callable(remaps_of) else {}
    found: dict[str, ActKey] = {}
    for port in ports:
        target = remaps.get(port) if isinstance(remaps, Mapping) else None
        key = ACT_KEYS.get(port)
        if isinstance(target, str) and target.startswith("/"):
            key = ACT_KEYS.get(target.removeprefix("/")) or key
        if key is not None:
            found[port] = key
    return found


def _act_key_port_classes() -> list[type]:
    """Every vultron ``PortsMixin`` class with an act-key input port."""
    _import_all_behavior_modules()
    # PortsMixin is abstract, which mypy refuses as a ``type[T]`` argument.
    root: type[object] = PortsMixin
    found = [
        cls
        for cls in all_subclasses(root)
        if cls.__module__.startswith("vultron.") and act_key_ports(cls)
    ]
    return sorted(found, key=lambda c: f"{c.__module__}.{c.__qualname__}")


def dual_channels(cls: type) -> list[str]:
    """The act-key ports *cls* may also take from a constructor argument.

    An argument named for the port or for its key counts.  Fails closed:
    ``**kwargs`` could carry either, so it counts for every port.
    """
    parameters = signature_of(cls).parameters
    forwards = any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters.values()
    )
    return sorted(
        f"{port} ({key.path})"
        for port, key in act_key_ports(cls).items()
        if forwards or port in parameters or key.name in parameters
    )


@pytest.mark.spec("BTND-01-006")
def test_act_key_port_classes_are_discovered() -> None:
    """Guards the check below against passing vacuously."""
    classes = _act_key_port_classes()
    names = {cls.__name__ for cls in classes}
    assert {
        "ReceivedPathNode",
        "CheckIsCaseManagerNode",
        "CommitCaseLedgerEntryNode",
        "CheckLedgerFreshnessNode",
        "ActorHoldsRoleInCaseNode",
        "SenderIsCaseOwnerNode",
        "CreateParticipantStatusNode",
    } <= names
    keys = {key for cls in classes for key in act_key_ports(cls).values()}
    assert keys - {CASE_ID}, "only /case_id ports were found"


@pytest.mark.spec("BTND-01-006")
@pytest.mark.spec("BTND-01-007")
@pytest.mark.spec("BTND-10-005")
def test_no_node_reads_an_act_key_from_both_a_port_and_its_constructor() -> (
    None
):
    dual = [
        f"{cls.__module__}.{cls.__qualname__}: {', '.join(ports)}"
        for cls in _act_key_port_classes()
        if (ports := dual_channels(cls))
    ]
    assert dual == [], (
        "These nodes declare an input port for an act key and also accept it"
        " (or **kwargs) as a constructor argument.  Read it from the port"
        " alone, and have build-time callers seed the port with"
        " with_act_keys(node, {KEY: value}) (BTND-01-006, BTND-01-007,"
        " BTND-10-005):\n" + "\n".join(f"  {d}" for d in dual)
    )


# ---------------------------------------------------------------------------
# The reading itself, on synthetic classes
# ---------------------------------------------------------------------------


class _Ports:
    INPUT_PORTS: dict[str, object] = {"case_id": None, "invitee": None}

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"invitee": "/invitee_id"}


@pytest.mark.spec("BTND-01-007")
def test_a_port_reads_a_key_by_name_or_by_class_binding() -> None:
    assert act_key_ports(_Ports) == {
        "case_id": CASE_ID,
        "invitee": ACT_KEYS["invitee_id"],
    }


@pytest.mark.spec("BTND-01-007")
def test_a_constructor_argument_for_a_bound_key_is_a_dual_channel() -> None:
    class _TakesInviteeId(_Ports):
        def __init__(self, invitee_id: str, name: str = "") -> None:
            pass

    class _TakesPortName(_Ports):
        def __init__(self, invitee: str, name: str = "") -> None:
            pass

    class _Configured(_Ports):
        def __init__(self, name: str = "") -> None:
            pass

    assert dual_channels(_TakesInviteeId) == ["invitee (/invitee_id)"]
    assert dual_channels(_TakesPortName) == ["invitee (/invitee_id)"]
    assert dual_channels(_Configured) == []


@pytest.mark.spec("BTND-01-007")
def test_a_kwargs_constructor_counts_for_every_act_key_port() -> None:
    """The check fails closed on a constructor that could forward one."""

    class _Forwards(_Ports):
        def __init__(self, **kwargs: object) -> None:
            pass

    assert dual_channels(_Forwards) == [
        "case_id (/case_id)",
        "invitee (/invitee_id)",
    ]


@pytest.mark.spec("BTND-01-007")
def test_a_port_bound_outside_the_vocabulary_is_not_an_act_key_port() -> None:
    class _Other:
        INPUT_PORTS: dict[str, object] = {"subject": None}

        @classmethod
        def _domain_port_remappings(cls) -> dict[str, str]:
            return {"subject": "/some_local_key"}

    assert act_key_ports(_Other) == {}
