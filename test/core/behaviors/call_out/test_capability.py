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
"""Tests for the four capability shapes and their typed ports (#3421).

Covers:

- The four shape bases live in core under the capability names, and there is
  no fifth (ADR-0097 decisions 5 and 6).
- A declaration's ``contract`` is derived from its ports, never set by hand,
  and a class that binds to a declaration cannot declare ports again
  (BT-18-012, BT-18-021).
- A port names a concrete class, has no default, and every written port is
  required (ADR-0044, BT-18-002).
- A concrete ``data_type`` is checked on read and on write, and a mismatch
  fails the whole tree run as an internal error, even beside a Selector
  fallback that would otherwise succeed (BTND-03-021).
"""

from __future__ import annotations

import py_trees
import pytest
from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from test.core.behaviors.bt_harness import BTTestScenario
from test.support.call_out import tick_call_out
from vultron.core.behaviors.call_out.actuator import ActuatorContract
from vultron.core.behaviors.call_out.answer import (
    REFUSAL_REASON_KEY,
    CallOutAnswer,
    CallOutContract,
)
from vultron.core.behaviors.call_out.capability import (
    ActuatorCapability,
    Capability,
    CapabilityShape,
    ComposerCapability,
    EvaluatorCapability,
    RetrieverCapability,
)
from vultron.core.behaviors.call_out.guard import SynchronousCallOut

_IN = "probe_capability_input"
_OUT = "probe_capability_output"
_CODE = "probe_capability_refusal_code"


def _port(data_type: type, *, required: bool = True) -> PortInformation:
    return PortInformation(data_type=data_type, required=required)


class _Declared(EvaluatorCapability):
    """A probe declaration with one port of each kind."""

    INPUT_PORTS = {_IN: _port(str)}
    OUTPUT_PORTS = {_OUT: _port(int)}
    REFUSAL_PORTS = {_CODE: _port(str)}


class _AnswersYes(_Declared):
    """Binds to ``_Declared``: reads its input, answers with *outputs*."""

    outputs: dict[str, object] = {_OUT: 7}

    def answer(self) -> CallOutAnswer:
        self.get_input(_IN)
        return CallOutAnswer.yes(self.outputs)


class _AnswersWrongType(_AnswersYes):
    outputs = {_OUT: "seven"}


@pytest.fixture(autouse=True)
def _clean_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


# ---------------------------------------------------------------------------
# The four shapes (AC-1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("shape_base", "shape"),
    [
        (EvaluatorCapability, CapabilityShape.EVALUATOR),
        (RetrieverCapability, CapabilityShape.RETRIEVER),
        (ComposerCapability, CapabilityShape.COMPOSER),
        (ActuatorCapability, CapabilityShape.ACTUATOR),
    ],
)
def test_shape_base_lives_in_core_and_names_its_shape(
    shape_base: type[Capability], shape: CapabilityShape
) -> None:
    assert (
        shape_base.__module__ == "vultron.core.behaviors.call_out.capability"
    )
    assert shape_base.shape is shape
    assert shape_base.declaration() is None


@pytest.mark.spec("BT-18-013")
def test_there_are_four_shapes_and_no_sentinel() -> None:
    assert len(CapabilityShape) == 4
    assert not [s for s in CapabilityShape if "sentinel" in s.name.lower()]


def test_old_fuzzer_names_are_the_core_shapes() -> None:
    from vultron.demo.fuzzer import call_out_point

    assert call_out_point.EvaluatorCallOutPoint is EvaluatorCapability
    assert call_out_point.RetrieverCallOutPoint is RetrieverCapability
    assert call_out_point.ComposerCallOutPoint is ComposerCapability
    assert call_out_point.ActuatorCallOutPoint is ActuatorCapability


# ---------------------------------------------------------------------------
# Ports are the authority; contract is derived (BT-18-012, BT-18-021)
# ---------------------------------------------------------------------------


@pytest.mark.spec("BT-18-012")
def test_contract_is_derived_from_the_ports() -> None:
    contract = _Declared.contract
    assert dict(contract.outputs) == {_OUT: int}
    assert dict(contract.refusal_fields) == {_CODE: str}
    assert contract.refusal_reason_key == REFUSAL_REASON_KEY


@pytest.mark.spec("BT-18-012")
def test_a_declaration_cannot_set_contract_by_hand() -> None:
    with pytest.raises(TypeError, match="derived from its declared ports"):

        class _HandContract(EvaluatorCapability):
            contract = CallOutContract(outputs={_OUT: int})


@pytest.mark.spec("BT-18-021")
def test_a_bound_class_takes_the_declaration_unchanged() -> None:
    assert _AnswersYes.declaration() is _Declared
    assert _Declared.declaration() is _Declared
    assert _AnswersYes.OUTPUT_PORTS == _Declared.OUTPUT_PORTS
    assert _AnswersYes.contract == _Declared.contract


@pytest.mark.spec("BT-18-021")
@pytest.mark.parametrize(
    "attribute", ["INPUT_PORTS", "OUTPUT_PORTS", "REFUSAL_PORTS"]
)
def test_a_bound_class_cannot_restate_ports(attribute: str) -> None:
    with pytest.raises(TypeError, match="does not restate them"):
        type("_Restates", (_Declared,), {attribute: {}})


@pytest.mark.parametrize(
    ("ports", "match"),
    [
        ({_OUT: str}, "not a PortInformation"),
        ({_OUT: _port(object)}, "concrete class"),
        ({_OUT: _port(list[str])}, "concrete class"),  # type: ignore[arg-type]
        (
            {_OUT: PortInformation(data_type=str, default_value="x")},
            "declares a default",
        ),
        ({_OUT: _port(str, required=False)}, "is optional"),
    ],
    ids=[
        "not-port-information",
        "object-type",
        "generic-alias",
        "default",
        "optional",
    ],
)
def test_a_declaration_refuses_a_port_it_cannot_enforce(
    ports: dict[str, object], match: str
) -> None:
    with pytest.raises(TypeError, match=match):
        type("_Bad", (EvaluatorCapability,), {"OUTPUT_PORTS": ports})


def test_ports_must_be_a_mapping() -> None:
    with pytest.raises(TypeError, match="not a mapping"):
        type("_NotMapping", (EvaluatorCapability,), {"OUTPUT_PORTS": [_OUT]})


def test_a_port_cannot_be_both_read_and_written() -> None:
    with pytest.raises(TypeError, match="both input and written"):
        type(
            "_Overlap",
            (EvaluatorCapability,),
            {
                "INPUT_PORTS": {_OUT: _port(str)},
                "OUTPUT_PORTS": {_OUT: _port(str)},
            },
        )


def test_an_optional_input_port_is_allowed() -> None:
    cls: type[Capability] = type(
        "_OptionalInput",
        (RetrieverCapability,),
        {"INPUT_PORTS": {_IN: _port(str, required=False)}},
    )
    assert not cls.INPUT_PORTS[_IN].required


@pytest.mark.spec("BT-18-028")
def test_a_composer_declares_its_artifact() -> None:
    with pytest.raises(TypeError, match="declares no output port"):
        type("_NoArtifact", (ComposerCapability,), {})


@pytest.mark.spec("BT-18-028")
def test_an_actuator_declares_no_outputs() -> None:
    assert isinstance(ActuatorCapability.contract, ActuatorContract)
    with pytest.raises(TypeError, match="BT-18-028"):
        type(
            "_ActuatorWithOutput",
            (ActuatorCapability,),
            {"OUTPUT_PORTS": {_OUT: _port(str)}},
        )


def test_a_binary_evaluator_and_retriever_declare_nothing() -> None:
    for shape_base in (EvaluatorCapability, RetrieverCapability):
        cls: type[Capability] = type("_Binary", (shape_base,), {})
        assert cls.contract.outputs == {}


# ---------------------------------------------------------------------------
# get_input: the read side of the typed port (BTND-03-021)
# ---------------------------------------------------------------------------


@pytest.mark.spec("BTND-03-021")
def test_get_input_returns_a_value_of_the_declared_type() -> None:
    py_trees.blackboard.Blackboard.set(f"/{_IN}", "supplied")
    assert _AnswersYes("Reader").get_input(_IN) == "supplied"


def test_get_input_raises_when_nothing_is_on_the_port() -> None:
    with pytest.raises(NoDataAvailable):
        _AnswersYes("Reader").get_input(_IN)


def test_get_input_reads_a_stored_none_as_no_data() -> None:
    py_trees.blackboard.Blackboard.set(f"/{_IN}", None)
    with pytest.raises(NoDataAvailable):
        _AnswersYes("Reader").get_input(_IN)


def test_get_input_refuses_an_undeclared_port() -> None:
    with pytest.raises(KeyError, match="not an input port"):
        _AnswersYes("Reader").get_input(_OUT)


@pytest.mark.spec("BTND-03-021")
def test_get_input_raises_on_a_wrong_typed_value() -> None:
    py_trees.blackboard.Blackboard.set(f"/{_IN}", 42)
    with pytest.raises(TypeError, match="not of type str"):
        _AnswersYes("Reader").get_input(_IN)


# ---------------------------------------------------------------------------
# Enforcement through a tree run (BTND-03-021, BT-18-002)
# ---------------------------------------------------------------------------


def _beside_a_fallback(
    backend: Capability,
) -> py_trees.behaviour.Behaviour:
    """The seam first in a Selector whose fallback arm always succeeds.

    A node-local ``FAILURE`` would hand control to the fallback and the run
    would succeed; only a whole-tree failure ends it as an internal error.
    """
    return py_trees.composites.Selector(
        name="WithFallback",
        memory=False,
        children=[
            SynchronousCallOut(backend),
            py_trees.behaviours.Success(name="Fallback"),
        ],
    )


@pytest.mark.spec("BT-18-012")
@pytest.mark.spec("BT-18-002")
def test_yes_writes_every_declared_output_port() -> None:
    py_trees.blackboard.Blackboard.set(f"/{_IN}", "supplied")
    assert tick_call_out(_AnswersYes("Writer")) == Status.SUCCESS
    for key, port in _Declared.OUTPUT_PORTS.items():
        value = py_trees.blackboard.Blackboard.storage[f"/{key}"]
        assert isinstance(value, port.data_type)


@pytest.mark.spec("BTND-03-021")
def test_a_wrong_typed_input_fails_the_whole_tree_run(
    bt_scenario: BTTestScenario,
) -> None:
    result = bt_scenario.run(
        _beside_a_fallback(_AnswersYes("Reader")),
        probe_capability_input=42,
    )
    assert result.internal_error is True
    bt_scenario.assert_failure(
        result, reason="not of type str", allow_internal=True
    )


@pytest.mark.spec("BTND-03-021")
@pytest.mark.spec("BT-18-036")
def test_a_wrong_typed_output_fails_the_whole_tree_run(
    bt_scenario: BTTestScenario,
) -> None:
    result = bt_scenario.run(
        _beside_a_fallback(_AnswersWrongType("Writer")),
        probe_capability_input="supplied",
    )
    assert result.internal_error is True
    bt_scenario.assert_failure(
        result, reason="not the declared int", allow_internal=True
    )
    assert f"/{_OUT}" not in py_trees.blackboard.Blackboard.storage


def test_a_well_typed_run_succeeds_through_the_seam(
    bt_scenario: BTTestScenario,
) -> None:
    result = bt_scenario.run(
        _beside_a_fallback(_AnswersYes("Reader")),
        probe_capability_input="supplied",
    )
    assert result.internal_error is False
    assert result.status == Status.SUCCESS
