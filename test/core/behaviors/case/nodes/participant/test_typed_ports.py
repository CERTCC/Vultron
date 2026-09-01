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

"""Typed-Ports tests for the ``participant_case`` blackboard contract (#2907).

Every node in ``vultron/core/behaviors/case/nodes/participant/`` that hands a
case object over the ``participant_case`` key declares it as
``data_type=VulnerabilityCase``, not ``data_type=object``.  The reader side
relies on that declaration: since #2490 replaced the ``isinstance`` guards with
``cast()``, py_trees' port type check is the only thing standing between a
wrong-typed blackboard value and an ``AttributeError`` raised deep inside
``update()``.

The node roster is discovered by walking the package rather than hard-coded,
so a new node that declares ``participant_case`` as ``object`` re-opens the
regression instead of slipping past a stale list.

Covers BTND-03-009 (the typed port declaration is the node's blackboard
contract), BTND-03-011 (inputs are read through ``get_input()``) and
BTND-03-012 (outputs are written through ``_set_output()``).
"""

from typing import Any, Iterator

import py_trees
import pytest

import vultron.core.behaviors.case.nodes.participant as participant_pkg
from vultron.core.models.case import VulnerabilityCase
from test.core.behaviors.bt_harness import BTTestScenario
from test.core.behaviors.port_contract import (
    PortDecl,
    decl_id,
    discover_port_declarations,
)

PORT = "participant_case"
#: Physical blackboard key the nodes bind ``participant_case`` to when
#: constructed without a ``report_id`` (``_seg`` falls back to ``"default"``).
PORT_KEY = f"/{PORT}_default"

ACTOR_ID = "https://example.org/actors/vendor"
PARTICIPANT_ACTOR_ID = "https://example.org/actors/reporter"
CASE_ID = "https://example.org/cases/case-001"

#: Constructor kwargs for every node in the discovered roster.  A node whose
#: constructor needs an argument must be registered here; the coverage test
#: below fails if the roster grows beyond this table, so a new node cannot be
#: silently dropped from the enforcement tests.
CONSTRUCTOR_KWARGS: dict[str, dict[str, Any]] = {
    "PersistOwnerCaseNode": {},
    "AdvanceOwnerRmToAcceptedNode": {},
    "RecordOwnerJoinedEventNode": {},
    "AttachOwnerParticipantToCaseNode": {},
    "AttachParticipantToCaseNode": {
        "participant_actor_id": PARTICIPANT_ACTOR_ID
    },
    "RecordParticipantAddedEventNode": {},
    "CaseHasActiveEmbargoNode": {},
    "CaseHasNoActiveEmbargoNode": {},
    "SeedParticipantAsSignatoryNode": {
        "participant_actor_id": PARTICIPANT_ACTOR_ID
    },
}


READERS, WRITERS = discover_port_declarations(participant_pkg, [PORT])


def _build(node_cls: type) -> Any:
    return node_cls(**CONSTRUCTOR_KWARGS[node_cls.__name__])


# ---------------------------------------------------------------------------
# Roster discovery — the ratchet only works if it finds the nodes
# ---------------------------------------------------------------------------


class TestRosterDiscovery:
    def test_readers_and_writers_are_both_found(self) -> None:
        """Guard against a refactor that silently empties the parametrize."""
        assert READERS, "no participant_case readers discovered"
        assert WRITERS, "no participant_case writers discovered"

    def test_constructor_table_matches_the_discovered_roster(self) -> None:
        """The table and the roster stay in step in both directions.

        Missing entries would drop a node from the enforcement tests; stale
        ones would outlive the node they name and never be noticed.
        """
        discovered = {cls.__name__ for cls, _ in READERS + WRITERS}
        assert discovered == set(CONSTRUCTOR_KWARGS)


# ---------------------------------------------------------------------------
# Declaration contract — every participant_case port is VulnerabilityCase
# ---------------------------------------------------------------------------


@pytest.mark.spec("BTND-03-009")
class TestParticipantCasePortDeclarations:
    @pytest.mark.parametrize("decl", READERS, ids=decl_id)
    def test_reader_declares_vulnerability_case(self, decl: PortDecl) -> None:
        node_cls, port_name = decl
        port = node_cls.input_ports()[port_name]  # type: ignore[attr-defined]
        assert port.data_type is VulnerabilityCase
        assert port.required is True

    @pytest.mark.parametrize("decl", WRITERS, ids=decl_id)
    def test_writer_declares_vulnerability_case(self, decl: PortDecl) -> None:
        node_cls, port_name = decl
        port = node_cls.output_ports()[port_name]  # type: ignore[attr-defined]
        assert port.data_type is VulnerabilityCase
        assert port.required is True


# ---------------------------------------------------------------------------
# Enforcement — the declaration is load-bearing, not decorative
# ---------------------------------------------------------------------------


@pytest.mark.spec("BTND-03-011")
class TestParticipantCaseInputEnforcement:
    """A wrong-typed blackboard value is rejected at the port boundary."""

    @pytest.fixture(autouse=True)
    def _clear_blackboard(self) -> Iterator[None]:
        # py_trees' blackboard storage is a process-global singleton; a value
        # left behind here would be visible to the next test.
        py_trees.blackboard.Blackboard.storage.clear()
        yield
        py_trees.blackboard.Blackboard.storage.clear()

    @pytest.mark.parametrize("decl", READERS, ids=decl_id)
    def test_wrong_type_raises_type_error(self, decl: PortDecl) -> None:
        node_cls, port_name = decl
        node = _build(node_cls)
        node.setup()
        py_trees.blackboard.Blackboard.set(PORT_KEY, "not-a-case")
        with pytest.raises(TypeError, match="not of type"):
            node.get_input(port_name)

    @pytest.mark.parametrize("decl", READERS, ids=decl_id)
    def test_vulnerability_case_is_accepted(self, decl: PortDecl) -> None:
        node_cls, port_name = decl
        node = _build(node_cls)
        node.setup()
        case = VulnerabilityCase(id_=CASE_ID, name="Test Case")
        py_trees.blackboard.Blackboard.set(PORT_KEY, case)
        assert node.get_input(port_name) is case


@pytest.mark.spec("BTND-03-011")
class TestParticipantCaseTickLevelEnforcement:
    """The type check is reached on the real production read path.

    The nodes read through ``_try_get_input()``, which catches only
    ``NoDataAvailable`` and ``NotImplementedError`` — so the ``TypeError`` from
    a wrong-typed value propagates out of ``initialise()`` and
    ``BTBridge.execute_tree`` converts it into a tree-level FAILURE carrying
    the type-mismatch message.  Asserting on that message (not merely on
    FAILURE) is what distinguishes a rejected value from a node that quietly
    treated the junk as absent.
    """

    @pytest.mark.parametrize("decl", READERS, ids=decl_id)
    def test_junk_on_key_fails_tree_with_type_error(
        self, bt_scenario: BTTestScenario, decl: PortDecl
    ) -> None:
        result = bt_scenario.run(
            _build(decl[0]),
            actor_id=ACTOR_ID,
            **{f"{PORT}_default": "not-a-case"},
        )
        bt_scenario.assert_failure(result)
        errors = result.errors or []
        assert any(
            "not of type" in err for err in errors
        ), f"expected a port type-mismatch error, got {errors}"


@pytest.mark.spec("BTND-03-012")
class TestParticipantCaseOutputEnforcement:
    """The write side fails fast too, so the key can never hold junk."""

    @pytest.fixture(autouse=True)
    def _clear_blackboard(self) -> Iterator[None]:
        py_trees.blackboard.Blackboard.storage.clear()
        yield
        py_trees.blackboard.Blackboard.storage.clear()

    @pytest.mark.parametrize("decl", WRITERS, ids=decl_id)
    def test_writer_rejects_wrong_type_on_set_output(
        self, decl: PortDecl
    ) -> None:
        node_cls, port_name = decl
        node = _build(node_cls)
        node.setup()
        with pytest.raises(TypeError, match="not of type"):
            node._set_output(port_name, "not-a-case")

    @pytest.mark.parametrize("decl", WRITERS, ids=decl_id)
    def test_writer_accepts_vulnerability_case(self, decl: PortDecl) -> None:
        node_cls, port_name = decl
        node = _build(node_cls)
        node.setup()
        case = VulnerabilityCase(id_=CASE_ID, name="Test Case")
        node._set_output(port_name, case)
        assert py_trees.blackboard.Blackboard.get(PORT_KEY) is case
