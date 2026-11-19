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

"""The end-time and termination-cascade nodes read their per-act values from
act keys (BTND-01-008, #6505).

Each node takes only configuration in its constructor.  A node ticked with no
seed for a key it requires is a composition fault: the read raises, naming
the key, rather than the node deciding anything without it.
"""

from collections.abc import Callable, Iterator
from datetime import datetime
from typing import cast

import py_trees
import pytest
from py_trees.ports import NoDataAvailable

from test.core.behaviors.embargo.nodes.conftest import setup_blackboard
from test.support.act_runner import in_act
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.act_keys import ACT_KEYS, ActKey, vocabulary_key
from vultron.core.behaviors.case.nodes.leave.settle import (
    ExpirePendingInvitesOnCloseNode,
)
from vultron.core.behaviors.case_manager_commit import (
    _CommitCaseManagerActivityBase,
)
from vultron.core.behaviors.embargo.end_time_tree import (
    EmbargoAlreadyEndedNode,
    EmbargoEndTimePassedNode,
)
from vultron.core.behaviors.embargo.nodes.cascade import (
    PersistEmbargoEventNode,
)
from vultron.core.behaviors.embargo.nodes.chosen_cause import (
    ChooseTerminationCauseNode,
    ChosenTermination,
)
from vultron.core.behaviors.embargo.nodes.emit import _SendEmbargoActivityBase
from vultron.core.behaviors.embargo.nodes.ending_notice import (
    CaptureActiveEmbargoNode,
    SendEmbargoEndingNoticesNode,
)
from vultron.core.behaviors.embargo.nodes.ending_notice_replica import (
    AdoptRemovedEmbargoRevisionNode,
    ApplyAnnouncedEmbargoRevisionNode,
    AwaitsEmbargoEndingNoticeNode,
)
from vultron.core.behaviors.embargo.nodes.expiry import (
    EvaluateInviteExpiryNode,
)
from vultron.core.behaviors.embargo.nodes.expiry_commit import (
    CommitAndApplyInviteExpiryNode,
)
from vultron.core.behaviors.embargo.nodes.invitation_expiry import (
    ExpireOverdueInvitesNode,
)
from vultron.core.behaviors.embargo.nodes.teardown import (
    ClearActiveEmbargoNode,
    SendAnnounceEmbargoEventNode,
)
from vultron.core.behaviors.embargo.nodes.teardown_guards import (
    HasEmbargoActiveNode,
    TerminationIsTimelyNode,
)
from vultron.core.behaviors.embargo.nodes.terminate import (
    SendTerminateEmbargoActivityNode,
    TeardownAskPendingNode,
)
from vultron.core.behaviors.embargo.nodes.termination_cause_guard import (
    TerminationCauseIsAdmissibleNode,
)
from vultron.core.behaviors.embargo.nodes.termination_commit import (
    CommitAndApplyEmbargoTerminationNode,
)
from vultron.core.models._helpers import now_utc
from vultron.core.models.embargo_termination import (
    EmbargoTermination,
    TerminationCauseKind,
)
from vultron.core.states.embargo_register import TerminationReason
from vultron.errors import VultronWiringError

#: Each moved node, built from configuration alone.
_BUILDERS: list[Callable[[], py_trees.behaviour.Behaviour]] = [
    lambda: EmbargoAlreadyEndedNode(result_out={}),
    EmbargoEndTimePassedNode,
    PersistEmbargoEventNode,
    lambda: ChooseTerminationCauseNode(
        kind=TerminationCauseKind.OTHER, chosen=ChosenTermination()
    ),
    CaptureActiveEmbargoNode,
    lambda: SendEmbargoEndingNoticesNode(capture=CaptureActiveEmbargoNode()),
    AwaitsEmbargoEndingNoticeNode,
    ApplyAnnouncedEmbargoRevisionNode,
    AdoptRemovedEmbargoRevisionNode,
    lambda: EvaluateInviteExpiryNode(result_out={}),
    CommitAndApplyInviteExpiryNode,
    ExpireOverdueInvitesNode,
    ExpirePendingInvitesOnCloseNode,
    lambda: ClearActiveEmbargoNode(termination=EmbargoTermination.early()),
    HasEmbargoActiveNode,
    SendAnnounceEmbargoEventNode,
    lambda: TerminationIsTimelyNode(termination=EmbargoTermination.early()),
    lambda: SendTerminateEmbargoActivityNode(reason=TerminationReason.EARLY),
    TeardownAskPendingNode,
    lambda: TerminationCauseIsAdmissibleNode(
        termination=EmbargoTermination.early()
    ),
    lambda: CommitAndApplyEmbargoTerminationNode(
        result_out={}, termination=EmbargoTermination.early()
    ),
]


#: A stand-in value for a seeded key, by the port's declared type; the read
#: under test raises before any node logic sees it.
_STAND_INS: dict[type, object] = {
    str: "urn:uuid:stand-in",
    datetime: now_utc(),
}


def _required_act_keys(node: py_trees.behaviour.Behaviour) -> list[ActKey]:
    """The act keys *node* declares as required input ports, in port order."""
    remaps = type(node)._domain_port_remappings()  # type: ignore[attr-defined]
    keys: list[ActKey] = []
    for port, info in type(node).INPUT_PORTS.items():  # type: ignore[attr-defined]
        key = vocabulary_key(remaps.get(port, ""))
        if info.required and isinstance(key, ActKey):
            keys.append(key)
    return keys


#: Every (node, required act key) pair: each key is left unseeded once, with
#: every other required key seeded.
_CASES: list[tuple[Callable[[], py_trees.behaviour.Behaviour], ActKey]] = [
    (build, key) for build in _BUILDERS for key in _required_act_keys(build())
]


@pytest.fixture
def act_key_storage() -> Iterator[None]:
    """Put every act key the test touches back as it was."""
    storage = py_trees.blackboard.Blackboard.storage
    saved = {
        k.path: storage[k.path] for k in ACT_KEYS.values() if k.path in storage
    }
    yield
    for key in ACT_KEYS.values():
        storage.pop(key.path, None)
    storage.update(saved)


def test_every_moved_node_declares_a_required_act_key() -> None:
    assert all(_required_act_keys(build()) for build in _BUILDERS)


@pytest.mark.spec("BTND-01-008")
@pytest.mark.usefixtures("act_key_storage")
@pytest.mark.parametrize(
    ("build", "key"),
    _CASES,
    ids=[f"{type(b()).__name__}-{k.name}" for b, k in _CASES],
)
def test_a_node_ticked_without_its_key_seeded_raises_naming_the_key(
    build: Callable[[], py_trees.behaviour.Behaviour], key: ActKey
) -> None:
    node = build()
    storage = py_trees.blackboard.Blackboard.storage
    for other in _required_act_keys(node):
        if other is not key:
            storage[other.path] = _STAND_INS[cast(type, other.value_type)]
    storage.pop(key.path, None)
    setup_blackboard(
        SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://example.org/users/vendor",
        )
    )
    tree = py_trees.trees.BehaviourTree(root=node)
    tree.setup()

    with in_act(), pytest.raises(NoDataAvailable, match=key.path):
        tree.tick()


@pytest.mark.spec("BTND-01-008")
@pytest.mark.parametrize(
    "base", [_SendEmbargoActivityBase, _CommitCaseManagerActivityBase]
)
def test_a_base_built_with_no_case_and_no_case_port_is_a_wiring_fault(
    base: type,
) -> None:
    """``case_id=None`` is only for a subclass that reads ``/case_id``."""

    # A name of its own per base: py_trees registers port classes by name.
    no_case_port = type(f"_NoCasePort{base.__name__}", (base,), {})
    kwargs: dict[str, object] = {"case_id": None}
    if base is _CommitCaseManagerActivityBase:
        kwargs["semantic_type"] = "Remove"
    with pytest.raises(VultronWiringError, match="/case_id"):
        no_case_port(**kwargs)
