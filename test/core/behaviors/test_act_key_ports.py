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
"""The act-key port helpers: declare, bind, and read a per-act key.

A moved node reads each per-act value from a vocabulary key (BTND-01-008).
An unseeded required key is a wiring fault named for the key (BT-25-008), an
empty string is no value (CS-08-002), and a wrong-typed value is never read
as "not supplied" (BTND-03-021).
"""

import pytest
from py_trees.ports import PortInformation

from test.core.behaviors.bt_harness import BTTestScenario
from vultron.core.behaviors.act_key_ports import (
    act_key_ports,
    act_key_remappings,
    act_value,
    optional_act_value,
)
from vultron.core.behaviors.act_key_scope import with_act_keys
from vultron.core.behaviors.act_keys import CASE_ID, SENDER_ID
from vultron.core.behaviors.sync.nodes.sender_sequence import (
    ClassifySequenceNumberNode,
)
from vultron.errors import VultronWiringError

_CASE = "https://example.org/cases/act-key-ports"
_SENDER = "https://example.org/actors/sender"


class _Node:
    """A stand-in with the one read the helpers make."""

    name = "Stand-in"

    def __init__(self, **ports: object) -> None:
        self._ports = ports

    def _try_get_input(self, key: str) -> object | None:
        return self._ports.get(key)


@pytest.mark.spec("BTND-03-022")
def test_each_key_gets_an_optional_port_bound_to_its_path() -> None:
    ports = act_key_ports(CASE_ID, SENDER_ID)
    assert set(ports) == {"case_id", "sender_id"}
    assert all(isinstance(p, PortInformation) for p in ports.values())
    assert not any(p.required for p in ports.values())
    assert act_key_remappings(CASE_ID, SENDER_ID) == {
        "case_id": "/case_id",
        "sender_id": "/sender_id",
    }


@pytest.mark.spec("BTND-01-008")
def test_a_seeded_key_is_read() -> None:
    assert act_value(_Node(case_id=_CASE), CASE_ID, str) == _CASE
    assert optional_act_value(_Node(case_id=_CASE), CASE_ID, str) == _CASE


@pytest.mark.spec("BTND-01-008")
def test_a_port_named_otherwise_is_read_by_its_name() -> None:
    node = _Node(named_case_id=_CASE)
    assert act_value(node, CASE_ID, str, port="named_case_id") == _CASE
    assert optional_act_value(node, CASE_ID, str) is None


@pytest.mark.spec("BT-25-008")
def test_an_unseeded_required_key_is_a_wiring_fault_naming_it() -> None:
    with pytest.raises(VultronWiringError, match="'/case_id'"):
        act_value(_Node(), CASE_ID, str)


@pytest.mark.spec("CS-08-002")
@pytest.mark.parametrize("value", [None, ""])
def test_no_value_and_an_empty_string_read_as_absent(value: object) -> None:
    assert optional_act_value(_Node(case_id=value), CASE_ID, str) is None
    with pytest.raises(VultronWiringError, match="'/case_id'"):
        act_value(_Node(case_id=value), CASE_ID, str)


@pytest.mark.spec("BTND-03-022")
def test_a_wrong_typed_value_raises_rather_than_reading_absent() -> None:
    with pytest.raises(VultronWiringError, match="holds a int, not a str"):
        optional_act_value(_Node(case_id=42), CASE_ID, str)


@pytest.mark.spec("BTND-01-008")
def test_an_unseeded_sequence_classifier_names_its_missing_sender() -> None:
    node = ClassifySequenceNumberNode()
    with pytest.raises(VultronWiringError, match="/sender_id"):
        _ = node.sender_id


@pytest.mark.spec("BTND-01-008")
def test_the_classifier_keeps_its_sender_after_the_scope_ends(
    bt_scenario: BTTestScenario,
) -> None:
    """The arms after it read the sender once the seed is restored."""
    node = ClassifySequenceNumberNode()
    bt_scenario.run(
        with_act_keys(node, {CASE_ID: _CASE, SENDER_ID: _SENDER}),
        activity=object(),
    )
    assert node.sender_id == _SENDER
    assert node.case_id == _CASE
