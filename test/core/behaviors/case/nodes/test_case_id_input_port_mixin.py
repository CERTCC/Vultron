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
"""``CaseIdInputPortMixin`` merges its ``case_id`` port into ``INPUT_PORTS``.

A mixin cannot extend a class attribute through ``super()``, so the mixin
adds the port from ``__init_subclass__`` (#3610). These tests pin that the
merge keeps the class's own ports, survives a subclass that redeclares
``INPUT_PORTS``, and fails fast when there is nothing to extend.
"""

import pytest
from py_trees.common import Status
from py_trees.ports import PortInformation

from vultron.core.behaviors.case.nodes.case_lookup import CaseIdInputPortMixin
from vultron.core.behaviors.helpers import DataLayerActionWithPorts


class _MixinProbeNode(CaseIdInputPortMixin, DataLayerActionWithPorts):
    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "probe": PortInformation(data_type=str, required=True),
    }

    def update(self) -> Status:
        return Status.SUCCESS


class _MixinProbeRedeclaringChild(_MixinProbeNode):
    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "child_only": PortInformation(data_type=str, required=True),
    }


@pytest.mark.spec("BTND-03-009")
def test_mixin_adds_optional_case_id_port() -> None:
    port = _MixinProbeNode.INPUT_PORTS["case_id"]
    assert port.data_type is str
    assert port.required is False


@pytest.mark.spec("BTND-03-009")
def test_mixin_keeps_the_class_own_ports() -> None:
    expected = {*DataLayerActionWithPorts.INPUT_PORTS, "probe", "case_id"}
    assert set(_MixinProbeNode.INPUT_PORTS) == expected


@pytest.mark.spec("BTND-03-009")
def test_mixin_does_not_mutate_the_parent_declaration() -> None:
    assert "case_id" not in DataLayerActionWithPorts.INPUT_PORTS


@pytest.mark.spec("BTND-03-009")
def test_subclass_redeclaring_input_ports_still_gets_case_id() -> None:
    ports = _MixinProbeRedeclaringChild.INPUT_PORTS
    assert "case_id" in ports
    assert "child_only" in ports
    assert "probe" not in ports


@pytest.mark.spec("BTND-03-009")
def test_mixing_class_can_be_instantiated() -> None:
    # py_trees >= 2.6 raises TypeError here for an undeclared ports class.
    assert _MixinProbeNode(name="probe").name == "probe"
    assert _MixinProbeRedeclaringChild(name="child").name == "child"


@pytest.mark.spec("BTND-03-009")
def test_mixin_without_input_ports_to_extend_fails_fast() -> None:
    with pytest.raises(AttributeError, match="INPUT_PORTS"):

        class _NoPortsToExtend(CaseIdInputPortMixin):
            pass
