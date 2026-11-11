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
"""A wrong-typed optional port value fails the tree; it never reads as absent.

``_try_get_input()`` is the optional-port read about 30 nodes share, through
both ports bases.  It turns absence into ``None``.  A value of the wrong
``data_type`` must raise instead, so ``BTBridge`` fails the whole tree run
rather than letting the node go on as if nothing was supplied (BTND-03-021).
"""

import py_trees
import pytest
from py_trees.common import Status
from py_trees.ports import PortInformation

import vultron.core.behaviors as behaviors_pkg
from test.core.behaviors.bt_harness import BTTestScenario
from test.core.behaviors.port_contract import iter_port_node_classes
from vultron.core.behaviors.helpers.ports_base import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
    _OptionalPortRead,
)

_PORT = "probe"
_KEY = f"/{_PORT}"


class _ConditionReadsProbe(DataLayerConditionWithPorts):
    INPUT_PORTS = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        _PORT: PortInformation(data_type=str, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {_PORT: _KEY}

    def initialise(self) -> None:
        super().initialise()
        self.probe = self._try_get_input(_PORT)

    def update(self) -> Status:
        return Status.SUCCESS


class _ActionReadsProbe(DataLayerActionWithPorts):
    INPUT_PORTS = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        _PORT: PortInformation(data_type=str, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {_PORT: _KEY}

    def initialise(self) -> None:
        super().initialise()
        self.probe = self._try_get_input(_PORT)

    def update(self) -> Status:
        return Status.SUCCESS


_NODE_CLASSES = [_ConditionReadsProbe, _ActionReadsProbe]
_IDS = ["condition", "action"]


@pytest.fixture(autouse=True)
def _clean_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


@pytest.mark.spec("BTND-03-021")
@pytest.mark.parametrize("node_cls", _NODE_CLASSES, ids=_IDS)
class TestOptionalPortRead:
    def test_absent_value_reads_as_none(self, node_cls: type) -> None:
        node = node_cls(name="probe-reader")
        node.setup()
        assert node._try_get_input(_PORT) is None

    def test_key_holding_none_reads_as_none(self, node_cls: type) -> None:
        # py_trees raises NotImplementedError for a stored None; that is
        # absence too, not a type mismatch.
        node = node_cls(name="probe-reader")
        node.setup()
        py_trees.blackboard.Blackboard.set(_KEY, None)
        assert node._try_get_input(_PORT) is None

    def test_value_of_declared_type_is_returned(self, node_cls: type) -> None:
        node = node_cls(name="probe-reader")
        node.setup()
        py_trees.blackboard.Blackboard.set(_KEY, "supplied")
        assert node._try_get_input(_PORT) == "supplied"

    def test_wrong_typed_value_raises_not_none(self, node_cls: type) -> None:
        node = node_cls(name="probe-reader")
        node.setup()
        py_trees.blackboard.Blackboard.set(_KEY, 42)
        with pytest.raises(TypeError, match="not of type"):
            node._try_get_input(_PORT)

    def test_wrong_typed_value_fails_the_tree_run(
        self, bt_scenario: BTTestScenario, node_cls: type
    ) -> None:
        result = bt_scenario.run(node_cls(name="probe-reader"), probe=42)
        # A wrong-typed value is a wiring error, so the run is an internal
        # error, and its reason names the type mismatch rather than absence.
        assert result.internal_error is True
        bt_scenario.assert_failure(
            result, reason="not of type", allow_internal=True
        )


@pytest.mark.spec("BTND-03-021")
def test_no_node_overrides_the_shared_optional_read() -> None:
    """Every ports node reads optional ports through ``_OptionalPortRead``.

    A node class that defined its own ``_try_get_input()`` could catch
    ``TypeError`` and read a wrong-typed value as absent, and the probe-node
    tests above would stay green.  The roster is discovered reflectively, so a
    node added later is checked too.
    """
    roster = list(iter_port_node_classes(behaviors_pkg))
    assert roster, "reflective walk found no typed-Ports node classes"
    shared = _OptionalPortRead._try_get_input
    overriding = sorted(
        f"{cls.__module__}.{cls.__qualname__}"
        for cls in roster
        if not issubclass(cls, _OptionalPortRead)
        or cls._try_get_input is not shared
    )
    assert overriding == []
