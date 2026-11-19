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
seed for a key it requires is a composition fault: the shared read
(:func:`~vultron.core.behaviors.act_key_ports.act_value`) raises a wiring
error naming the key, rather than the node deciding anything without it.
"""

from collections.abc import Callable, Iterator

import py_trees
import pytest

from test.core.behaviors.embargo.nodes.conftest import setup_blackboard
from test.support.act_runner import in_act
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.act_keys import (
    ACT_KEYS,
    CASE_ID,
    CASE_MANAGER_ID,
    CAUSE_ID,
    EMBARGO,
    EMBARGO_ID,
    INVITEE_ID,
    SENDER_ID,
    ActKey,
)
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
from vultron.core.models.embargo_termination import (
    EmbargoTermination,
    TerminationCauseKind,
)
from vultron.core.states.embargo_register import TerminationReason
from vultron.errors import VultronWiringError

_Build = Callable[[], py_trees.behaviour.Behaviour]

#: Each moved node, built from configuration alone, and the act keys it
#: cannot run without.  Its optional keys (``/terminated_at``, ``/embargo``,
#: and ``/embargo_id`` on the timely guard) are not listed.
_NODES: list[tuple[_Build, tuple[ActKey, ...]]] = [
    (lambda: EmbargoAlreadyEndedNode(result_out={}), (CASE_ID,)),
    (EmbargoEndTimePassedNode, (CASE_ID,)),
    (PersistEmbargoEventNode, (EMBARGO,)),
    (
        lambda: ChooseTerminationCauseNode(
            kind=TerminationCauseKind.OTHER, chosen=ChosenTermination()
        ),
        (CASE_ID,),
    ),
    (CaptureActiveEmbargoNode, (CASE_ID,)),
    (
        lambda: SendEmbargoEndingNoticesNode(
            capture=CaptureActiveEmbargoNode()
        ),
        (CASE_ID,),
    ),
    (AwaitsEmbargoEndingNoticeNode, (CASE_ID,)),
    (ApplyAnnouncedEmbargoRevisionNode, (CASE_ID, EMBARGO_ID)),
    (AdoptRemovedEmbargoRevisionNode, (CASE_ID, EMBARGO_ID)),
    (
        lambda: EvaluateInviteExpiryNode(result_out={}),
        (CASE_ID, INVITEE_ID, EMBARGO_ID),
    ),
    (
        CommitAndApplyInviteExpiryNode,
        (CASE_ID, INVITEE_ID, EMBARGO_ID, CAUSE_ID),
    ),
    (ExpireOverdueInvitesNode, (CASE_ID,)),
    (ExpirePendingInvitesOnCloseNode, (CASE_ID,)),
    (
        lambda: ClearActiveEmbargoNode(termination=EmbargoTermination.early()),
        (CASE_ID, EMBARGO_ID),
    ),
    (HasEmbargoActiveNode, (CASE_ID,)),
    (SendAnnounceEmbargoEventNode, (CASE_ID, EMBARGO_ID)),
    (
        lambda: TerminationIsTimelyNode(
            termination=EmbargoTermination.early()
        ),
        (CASE_ID,),
    ),
    (
        lambda: SendTerminateEmbargoActivityNode(
            reason=TerminationReason.EARLY
        ),
        (CASE_ID, EMBARGO_ID, CASE_MANAGER_ID),
    ),
    (TeardownAskPendingNode, (CASE_ID, EMBARGO_ID)),
    (
        lambda: TerminationCauseIsAdmissibleNode(
            termination=EmbargoTermination.early()
        ),
        (CASE_ID, SENDER_ID),
    ),
    (
        lambda: CommitAndApplyEmbargoTerminationNode(
            result_out={}, termination=EmbargoTermination.early()
        ),
        (CASE_ID,),
    ),
]

#: Every (node, required act key) pair: each key is left unseeded once, with
#: every other required key seeded.
_CASES: list[tuple[_Build, ActKey, tuple[ActKey, ...]]] = [
    (build, key, keys) for build, keys in _NODES for key in keys
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


def test_every_listed_key_is_a_port_of_its_node() -> None:
    for build, keys in _NODES:
        remaps = type(build())._domain_port_remappings()  # type: ignore[attr-defined]
        assert {k.path for k in keys} <= set(remaps.values()), build


@pytest.mark.spec("BTND-01-008")
@pytest.mark.usefixtures("act_key_storage")
@pytest.mark.parametrize(
    ("build", "key", "keys"),
    _CASES,
    ids=[f"{type(b()).__name__}-{k.name}" for b, k, _ in _CASES],
)
def test_a_node_ticked_without_its_key_seeded_raises_naming_the_key(
    build: _Build, key: ActKey, keys: tuple[ActKey, ...]
) -> None:
    node = build()
    storage = py_trees.blackboard.Blackboard.storage
    for other in keys:
        if other is not key:
            storage[other.path] = "urn:uuid:stand-in"
    storage.pop(key.path, None)
    setup_blackboard(
        SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://example.org/users/vendor",
        )
    )
    tree = py_trees.trees.BehaviourTree(root=node)
    tree.setup()

    with in_act(), pytest.raises(VultronWiringError, match=key.path):
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
