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
"""Every capability declaration, checked from its ports (#3421).

The roster is :func:`capability_declarations`, so a capability added later is
checked too.  For each declaration:

- it lives in core and is one of the four shapes (BT-18-020);
- its docstring's ``Blackboard contract (BT-18-001):`` section names exactly
  its declared ports, with their types (BT-18-001, BT-18-012);
- a simulation node in ``vultron/demo/fuzzer/`` binds to it, and that node,
  answering *yes*, has every declared output port written with a value of the
  port's type (BT-18-002, BT-18-003, BT-18-012, BT-18-021).

The tests read the ports and compare the prose to them, never the reverse.
"""

from __future__ import annotations

import importlib
import pkgutil
import re

import py_trees
import pytest
from py_trees.common import Status

import vultron.demo.fuzzer as fuzzer_pkg
from test.support.call_out import tick_call_out
from vultron.core.behaviors.call_out.answer import REFUSAL_REASON_KEY
from vultron.core.behaviors.call_out.capabilities import (
    capability_declarations,
)
from vultron.core.behaviors.call_out.capability import (
    Capability,
    CapabilityShape,
)

_DECLARATIONS = capability_declarations()
_SECTION = "Blackboard contract (BT-18-001):"
_LABELS = {
    "Input keys:": "inputs",
    "Output keys:": "outputs",
    "Refusal keys:": "refusals",
}
_ENTRY = re.compile(r"^(\w+): (\w+)\b")


def _id(cls: type) -> str:
    return cls.__qualname__


def _simulation_nodes() -> dict[type[Capability], list[type[Capability]]]:
    """Each declaration's binding classes in ``vultron/demo/fuzzer/``."""
    for info in pkgutil.walk_packages(
        fuzzer_pkg.__path__, prefix=f"{fuzzer_pkg.__name__}."
    ):
        importlib.import_module(info.name)
    bound: dict[type[Capability], list[type[Capability]]] = {}
    pending: list[type] = list(Capability.__subclasses__())
    seen: set[type] = set()
    while pending:
        cls = pending.pop()
        if cls in seen:
            continue
        seen.add(cls)
        pending.extend(cls.__subclasses__())
        declaration = cls.declaration()  # type: ignore[attr-defined]
        if cls.__module__.startswith(fuzzer_pkg.__name__) and declaration:
            bound.setdefault(declaration, []).append(cls)
    return bound


_BOUND = _simulation_nodes()


def _contract_section(doc: str) -> dict[str, dict[str, str]]:
    """The keys and type names each label of the contract section names."""
    lines = doc.splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == _SECTION)
    named: dict[str, dict[str, str]] = {v: {} for v in _LABELS.values()}
    label: str | None = None
    for line in lines[start + 1 :]:
        text = line.strip()
        if not text:
            break
        for prefix, name in _LABELS.items():
            if text.startswith(prefix):
                label, text = name, text[len(prefix) :].strip()
        assert label is not None, f"contract line before a label: {line!r}"
        if match := _ENTRY.match(text):
            named[label][match.group(1)] = match.group(2)
        else:
            # A parenthesised note, such as "(none — ...)".
            assert text.startswith("("), f"unreadable contract line {line!r}"
    return named


def test_the_roster_is_found() -> None:
    assert len(_DECLARATIONS) > len(CapabilityShape)
    assert {d.shape for d in _DECLARATIONS} == set(CapabilityShape)


def test_capability_names_are_unique() -> None:
    names = [d.__name__ for d in _DECLARATIONS]
    assert len(names) == len(set(names))


@pytest.mark.spec("BT-18-020")
@pytest.mark.parametrize("declaration", _DECLARATIONS, ids=_id)
def test_declaration_lives_in_core(declaration: type[Capability]) -> None:
    assert declaration.__module__.startswith(
        "vultron.core.behaviors.call_out.capabilities."
    )
    assert declaration.declaration() is declaration
    assert declaration.shape in CapabilityShape


@pytest.mark.spec("BT-18-001")
@pytest.mark.spec("BT-18-012")
@pytest.mark.spec("BT-18-016")
@pytest.mark.parametrize("declaration", _DECLARATIONS, ids=_id)
def test_docstring_contract_names_the_declared_ports(
    declaration: type[Capability],
) -> None:
    doc = declaration.__doc__ or ""
    assert _SECTION in doc, f"{_id(declaration)} documents no contract"
    named = _contract_section(doc)

    def declared(ports):  # type: ignore[no-untyped-def]
        return {k: p.data_type.__name__ for k, p in ports.items()}

    assert named["inputs"] == declared(declaration.INPUT_PORTS)
    assert named["outputs"] == declared(declaration.OUTPUT_PORTS)
    assert named["refusals"] == {
        declaration.REFUSAL_REASON_KEY: "str",
        **declared(declaration.REFUSAL_PORTS),
    }


def test_contract_parser_reads_ports_and_notes() -> None:
    doc = f"""Summary.

    {_SECTION}
      Input keys:  (none — reads the case)
      Output keys: verdict: bool  (yes only)
                   rationale: str  (yes only)
      Refusal keys: {REFUSAL_REASON_KEY}: str  (no only)

    Trailing paragraph: not_a_port: int
    """
    assert _contract_section(doc) == {
        "inputs": {},
        "outputs": {"verdict": "bool", "rationale": "str"},
        "refusals": {REFUSAL_REASON_KEY: "str"},
    }


@pytest.mark.spec("BT-18-021")
@pytest.mark.parametrize("declaration", _DECLARATIONS, ids=_id)
def test_a_simulation_node_binds_to_each_declaration(
    declaration: type[Capability],
) -> None:
    nodes = _BOUND.get(declaration, [])
    assert nodes, f"no node in vultron/demo/fuzzer/ binds {_id(declaration)}"
    for node in nodes:
        assert node.contract == declaration.contract
        assert node.OUTPUT_PORTS == declaration.OUTPUT_PORTS


_WRITERS = [d for d in _DECLARATIONS if d.OUTPUT_PORTS]


def _answering_yes(node_cls: type[Capability]) -> Capability:
    """A node of *node_cls* whose own ``answer()`` gives *yes*.

    The test patches the roll to 0.0, so a probabilistic node takes its
    *yes* branch through its real ``answer()``.  A node that never answers
    *yes* (``AlwaysFail``) has no *yes* branch to run; for it alone the test
    calls the simulation's ``yes()`` directly.
    """
    from vultron.demo.fuzzer.base import AlwaysFail

    if node_cls.answer is not AlwaysFail.answer:
        return node_cls()
    forced: type[Capability] = type(
        f"{node_cls.__name__}AnsweringYes",
        (node_cls,),
        {"answer": lambda self: self.yes()},
    )
    return forced()


def test_writers_are_found() -> None:
    assert _WRITERS
    assert all(d.shape is not CapabilityShape.ACTUATOR for d in _WRITERS), (
        "an Actuator declares no outputs (BT-18-028)"
    )


@pytest.mark.spec("BT-18-002")
@pytest.mark.spec("BT-18-003")
@pytest.mark.spec("BT-18-012")
@pytest.mark.parametrize("declaration", _WRITERS, ids=_id)
def test_yes_writes_every_declared_output_port(
    declaration: type[Capability], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Read the declared output ports, then check a *yes* writes each one."""
    from vultron.demo.fuzzer import base

    monkeypatch.setattr(base.random, "random", lambda: 0.0)
    nodes = _BOUND.get(declaration, [])
    assert nodes
    for node_cls in nodes:
        py_trees.blackboard.Blackboard.storage.clear()
        node = _answering_yes(node_cls)
        node.setup()
        assert tick_call_out(node) == Status.SUCCESS, _id(node_cls)
        storage = py_trees.blackboard.Blackboard.storage
        for key, port in declaration.OUTPUT_PORTS.items():
            assert isinstance(storage.get(f"/{key}"), port.data_type), (
                f"{_id(node_cls)} answered yes without {key}"
            )
    py_trees.blackboard.Blackboard.storage.clear()
