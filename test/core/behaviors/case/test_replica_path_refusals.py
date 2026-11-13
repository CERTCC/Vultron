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

"""The not-CASE_MANAGER refusals a received tree states itself (#6394).

A tree that declares the manager path alone has the path stage refuse every
other receiver; a replica whose case names no CASE_MANAGER is told the case
has none (CM-02-014).  A tree whose replica path does act, but still owes
the replica a refusal, states it past its guards with
:class:`ReplicaRefusalNode`, and the runner reads the reason whole, as the
path stage's own (HP-01-005, HP-01-039).  No handler reads the
DataLayer after the run to decide them.
"""

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from test.support.objects import make
from vultron.core.behaviors.case.nodes.incomplete_activity import (
    ActivityUnsupportedNode,
)
from vultron.core.behaviors.case.nodes.received_path import (
    ReceivedPath,
    ReceivedPathNode,
    ReplicaRefusalNode,
    undeclared_path_reason,
)
from vultron.core.behaviors.case.received_run import (
    door_refusal,
    incomplete_activity_refusal,
    path_refusal,
)
from vultron.core.behaviors.case_id_scope import with_case_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.enums.roles import CVDRole

CASE_ID = "https://example.org/cases/replica-refusals"
MANAGER_ID = "https://example.org/actors/coordinator"
VENDOR_ID = "https://example.org/actors/vendor"
OWNER_ID = "https://example.org/actors/owner"

NOT_MANAGER = f"not the CASE_MANAGER of case '{CASE_ID}'"
NO_MANAGER = f"case '{CASE_ID}' has no CASE_MANAGER"


def _participant(suffix: str, actor_id: str, *roles: CVDRole):
    return make(
        CaseParticipant,
        id_=f"{CASE_ID}/participants/{suffix}",
        attributed_to=actor_id,
        context=CASE_ID,
        case_roles=list(roles),
    )


def _replica(*, with_manager: bool) -> BTTestScenario:
    """The vendor's replica of the case, with or without a CASE_MANAGER."""
    scenario = BTTestScenario(actor_id=VENDOR_ID)
    vendor = _participant("vendor", VENDOR_ID, CVDRole.VENDOR)
    members = [vendor]
    if with_manager:
        members.append(
            _participant("manager", MANAGER_ID, CVDRole.CASE_MANAGER)
        )
    scenario.seed(
        *members,
        make(
            VulnerabilityCase,
            id_=CASE_ID,
            name="REPLICA-REFUSALS",
            attributed_to=OWNER_ID,
            case_participants=[m.id_ for m in members],
            actor_participant_index={
                m.attributed_to: m.id_
                for m in members  # type: ignore[misc]
            },
        ),
    )
    return scenario


def _run(
    scenario: BTTestScenario, node: py_trees.behaviour.Behaviour
) -> py_trees.behaviour.Behaviour:
    root = py_trees.composites.Sequence(
        name="ProofBT", memory=False, children=[with_case_id(node, CASE_ID)]
    )
    scenario.run(root, actor_id=VENDOR_ID)
    return root


@pytest.mark.spec("CM-02-014")
@pytest.mark.spec("HP-01-039")
def test_undeclared_path_reason_names_a_case_with_no_manager() -> None:
    """At a replica whose case names no CASE_MANAGER, the one reason says
    so; on any other path the flag changes nothing."""
    assert (
        undeclared_path_reason(
            ReceivedPath.PARTICIPANT_REPLICA,
            {ReceivedPath.CASE_MANAGER},
            CASE_ID,
            case_names_no_manager=True,
        )
        == NO_MANAGER
    )
    assert undeclared_path_reason(
        ReceivedPath.NO_CASE,
        {ReceivedPath.CASE_MANAGER},
        CASE_ID,
        case_names_no_manager=True,
    ) == (f"holds no replica of case '{CASE_ID}'")


@pytest.mark.spec("HP-01-005")
@pytest.mark.spec("CM-02-014")
@pytest.mark.parametrize(
    ("with_manager", "reason"),
    [(True, NOT_MANAGER), (False, NO_MANAGER)],
    ids=["case-names-a-manager", "case-names-none"],
)
def test_the_path_stage_refuses_a_replica_for_a_manager_only_tree(
    with_manager: bool, reason: str
) -> None:
    """A manager-only tree is refused at a replica, and the reason says
    whether the case names a CASE_MANAGER at all."""
    stage = ReceivedPathNode(
        declared=frozenset({ReceivedPath.CASE_MANAGER}), label="ProofBT"
    )

    root = _run(_replica(with_manager=with_manager), stage)

    assert stage.status is Status.FAILURE
    assert stage.resolved_path is ReceivedPath.PARTICIPANT_REPLICA
    refusal = path_refusal(root)
    assert refusal is not None
    assert refusal.disposition is HandlerDisposition.REFUSED
    assert refusal.reason == reason


@pytest.mark.spec("HP-01-005")
@pytest.mark.spec("CM-02-014")
@pytest.mark.parametrize(
    ("with_manager", "reason"),
    [(True, NOT_MANAGER), (False, NO_MANAGER)],
    ids=["case-names-a-manager", "case-names-none"],
)
def test_a_replica_refusal_node_is_read_as_the_path_stages_refusal(
    with_manager: bool, reason: str
) -> None:
    """The tree states the replica's refusal, and the runner reads it whole
    through the same door reading as the path stage's."""
    node = ReplicaRefusalNode(CASE_ID)

    root = _run(_replica(with_manager=with_manager), node)

    assert node.status is Status.FAILURE
    refusal = door_refusal(root)
    assert refusal is not None
    assert refusal.disposition is HandlerDisposition.REFUSED
    assert refusal.reason == reason


@pytest.mark.spec("CM-30-003")
def test_an_unsupported_activity_is_refused_with_its_reason_whole() -> None:
    """An unsupported message type is refused like an incomplete one: the
    guard's reason is the whole refusal (CLP-10-018)."""
    reason = "this message type is not supported"
    root = py_trees.composites.Sequence(
        name="ProofBT",
        memory=False,
        children=[ActivityUnsupportedNode(reason)],
    )
    root.tick_once()

    refusal = incomplete_activity_refusal(root)
    assert refusal is not None
    assert refusal.disposition is HandlerDisposition.REFUSED
    assert refusal.reason == reason
