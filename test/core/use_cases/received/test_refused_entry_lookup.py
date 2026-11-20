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
"""The fault trees find their refused entry with a lookup node (BT-25-009).

A refused-entry fault names the ``Add(CaseLedgerEntry)`` it answers and
carries no case (ASK-07-006).  Each fault tree finds the entry, and so the
case, with :class:`FindRefusedLedgerEntry` ahead of its path stage; a miss
publishes nothing and :class:`RefusedLedgerEntryFound` refuses it with a
declared reason (BT-25-010).  The tree has one shape for every fault.
"""

from types import SimpleNamespace
from typing import Any

import py_trees
import pytest
from py_trees.common import Status

from test.support.act_runner import run_tree
from vultron.core.behaviors.act_inputs import KeySource, tree_inputs
from vultron.core.behaviors.act_keys import (
    ANNOUNCE_ID,
    CASE_ID,
    REFUSED_ENTRY,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.lifecycle import (
    CommitCaseLedgerEntryNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    ReceivedActivityTree,
    create_receive_activity_tree,
)
from vultron.core.behaviors.sync.divergence_tree import (
    create_case_diverged_fault_tree,
)
from vultron.core.behaviors.sync.hash_mismatch_tree import (
    create_hash_mismatch_fault_tree,
)
from vultron.core.behaviors.sync.nodes.refused_entry import (
    FindRefusedLedgerEntry,
    RefusedLedgerEntryFound,
    unnamed_entry_reason,
)
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.use_cases.received.fault import (
    CreateProcessingFaultReceivedUseCase,
)
from vultron.errors import VultronWiringError

from ._ledger_network import BYSTANDER, MANAGER, OWNER, LedgerNetwork

_CAUSE = "https://example.org/activities/the-act"
_RULE = CreateProcessingFaultReceivedUseCase.sender_entitlement


class _Probe(py_trees.behaviour.Behaviour):
    """Record what the lookup left on the blackboard for later nodes."""

    def __init__(self) -> None:
        super().__init__(name="Probe")
        self.seen: dict[str, Any] = {}

    def update(self) -> Status:
        storage = py_trees.blackboard.Blackboard.storage
        self.seen = {
            key.name: storage.get(key.path)
            for key in (CASE_ID, REFUSED_ENTRY, ANNOUNCE_ID)
        }
        return Status.SUCCESS


def _announced(name: str) -> tuple[LedgerNetwork, str]:
    """A network whose CASE_MANAGER announced an entry the bystander holds."""
    net = LedgerNetwork(f"https://example.org/cases/{name}")
    body = net.diverged_announcement(BYSTANDER, OWNER, _CAUSE)
    net.receive(BYSTANDER, body)
    return net, body["id"]


def _look_up(
    net: LedgerNetwork, as_actor: str, failed_activity_id: str | None
) -> tuple[Any, _Probe]:
    probe = _Probe()
    tree = py_trees.composites.Sequence(
        "Lookup", memory=False, children=[FindRefusedLedgerEntry(), probe]
    )
    result = run_tree(
        BTBridge(datalayer=net.stores[as_actor]),
        tree=tree,
        actor_id=as_actor,
        activity=SimpleNamespace(failed_activity_id=failed_activity_id),
    )
    return result, probe


@pytest.mark.spec("BT-25-009")
def test_the_lookup_publishes_the_entry_its_case_and_the_add() -> None:
    net, announce_id = _announced("refused-entry-lookup-hit")

    result, probe = _look_up(net, MANAGER, announce_id)

    assert result.status is Status.SUCCESS
    entry = probe.seen[REFUSED_ENTRY.name]
    assert isinstance(entry, CaseLedgerEntry)
    assert probe.seen[CASE_ID.name] == entry.case_id == net.case_id
    assert probe.seen[ANNOUNCE_ID.name] == announce_id


@pytest.mark.spec("BT-25-010")
@pytest.mark.parametrize(
    ("as_actor", "failed"),
    [
        pytest.param(MANAGER, None, id="no-in-reply-to"),
        pytest.param(MANAGER, "urn:uuid:not-stored", id="not-stored"),
        # The bystander holds the Add it received, but never sent it.
        pytest.param(BYSTANDER, "announce", id="not-sent-by-this-actor"),
    ],
)
def test_a_miss_publishes_nothing_and_never_refuses(
    as_actor: str, failed: str | None
) -> None:
    net, announce_id = _announced(f"refused-entry-miss-{as_actor[-6:]}")
    failed_id = announce_id if failed == "announce" else failed

    result, probe = _look_up(net, as_actor, failed_id)

    assert result.status is Status.SUCCESS
    assert set(probe.seen.values()) == {None}


@pytest.mark.spec("BT-25-010")
def test_the_miss_guard_refuses_with_its_declared_reason() -> None:
    net, _ = _announced("refused-entry-miss-guard")
    guard = RefusedLedgerEntryFound(
        answer="re-seed", requirement="SYNC-16-003"
    )

    result = run_tree(
        BTBridge(datalayer=net.stores[MANAGER]), tree=guard, actor_id=MANAGER
    )

    assert result.status is Status.FAILURE
    assert guard.declared_refusal == unnamed_entry_reason(
        answer="re-seed", requirement="SYNC-16-003"
    )
    assert guard.declared_refusal == (
        "the fault names no Add(CaseLedgerEntry) this actor sent, so it"
        " names no case to re-seed (SYNC-16-003, ASK-07-004)"
    )


@pytest.mark.spec("BT-25-010")
def test_the_miss_guard_admits_a_found_entry() -> None:
    net, announce_id = _announced("refused-entry-guard-hit")
    guard = RefusedLedgerEntryFound(
        answer="re-seed", requirement="SYNC-16-003"
    )
    tree = py_trees.composites.Sequence(
        "LookupAndGuard",
        memory=False,
        children=[FindRefusedLedgerEntry(), guard],
    )

    result = run_tree(
        BTBridge(datalayer=net.stores[MANAGER]),
        tree=tree,
        actor_id=MANAGER,
        activity=SimpleNamespace(failed_activity_id=announce_id),
    )

    assert result.status is Status.SUCCESS
    assert guard.declared_refusal is None


def _fault_trees(sender: str) -> dict[str, ReceivedActivityTree]:
    trees = {
        "case-diverged": create_case_diverged_fault_tree(
            sender_id=sender, sender_rule=_RULE, fault_published=None
        ),
        "hash-mismatch": create_hash_mismatch_fault_tree(
            sender_id=sender, sender_rule=_RULE
        ),
    }
    assert all(isinstance(t, ReceivedActivityTree) for t in trees.values())
    return {
        k: t for k, t in trees.items() if isinstance(t, ReceivedActivityTree)
    }


def _shape(tree: py_trees.behaviour.Behaviour) -> list[tuple[str, str]]:
    return [(type(n).__name__, n.name) for n in tree.iterate()]


@pytest.mark.spec("BT-25-009")
@pytest.mark.spec("BTND-01-009")
@pytest.mark.parametrize("kind", ["case-diverged", "hash-mismatch"])
def test_a_fault_tree_has_one_shape_and_publishes_what_it_finds(
    kind: str,
) -> None:
    """The tree takes no entry at build time, so every fault of its class
    runs the same tree; the lookup is the one source of its keys."""
    tree = _fault_trees("https://example.org/a")[kind]
    other = _fault_trees("https://example.org/b")[kind]

    assert _shape(tree) == _shape(other)
    assert [type(n).__name__ for n in tree.input_stages] == [
        "FindRefusedLedgerEntry"
    ]
    assert tree_inputs(tree).sources == {
        CASE_ID: KeySource.PUBLISHED,
        REFUSED_ENTRY: KeySource.PUBLISHED,
        ANNOUNCE_ID: KeySource.PUBLISHED,
    }
    # A fault is replication signalling, never ledgered (SYNC-16-002).
    assert not any(
        isinstance(n, CommitCaseLedgerEntryNode) for n in tree.iterate()
    )


@pytest.mark.spec("BT-25-009")
def test_commits_lookup_case_needs_a_lookup() -> None:
    with pytest.raises(VultronWiringError, match="needs case_lookup"):
        create_receive_activity_tree(
            name="NoLookupBT",
            case_id=None,
            precondition_guards=[],
            commits_lookup_case=False,
        )


@pytest.mark.spec("BT-25-010")
@pytest.mark.spec("BT-17-007")
def test_a_found_entry_does_not_leak_into_the_next_run() -> None:
    """The bridge restores every key the lookup publishes, so a later fault
    naming no entry is refused by the miss guard, not admitted on a stale
    entry."""
    net, announce_id = _announced("refused-entry-no-leak")
    _look_up(net, MANAGER, announce_id)
    storage = py_trees.blackboard.Blackboard.storage
    assert all(
        storage.get(key.path) is None
        for key in (CASE_ID, REFUSED_ENTRY, ANNOUNCE_ID)
    )

    guard = RefusedLedgerEntryFound(
        answer="re-seed", requirement="SYNC-16-003"
    )
    tree = py_trees.composites.Sequence(
        "LookupAndGuard",
        memory=False,
        children=[FindRefusedLedgerEntry(), guard],
    )
    result = run_tree(
        BTBridge(datalayer=net.stores[MANAGER]),
        tree=tree,
        actor_id=MANAGER,
        activity=SimpleNamespace(failed_activity_id=None),
    )

    assert result.status is Status.FAILURE
    assert guard.declared_refusal == unnamed_entry_reason(
        answer="re-seed", requirement="SYNC-16-003"
    )


@pytest.mark.spec("HP-01-036")
@pytest.mark.spec("HP-01-041")
def test_an_entry_whose_case_this_store_lacks_is_refused_on_the_no_case_side() -> (
    None
):
    """The lookup finds the entry but the store holds no case for it: the
    path stage reads the no-case path, the miss guard admits the found
    entry, and the sender guard's no-case side, which admits no sender,
    refuses it (HP-01-036).  Not reached in practice: the CASE_MANAGER
    stores every Add it sends beside the case."""
    from test.support.objects import authored_at, make
    from test.support.received import delivered_body
    from vultron.core.models.fault_classes import (
        VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_CASE_DIVERGED,
    )
    from vultron.core.models.use_case_result import HandlerDisposition
    from vultron.wire.as2.factories import create_processing_fault_activity
    from vultron.wire.as2.vocab.objects.processing_fault import (
        as_ProcessingFault,
    )

    net, announce_id = _announced("refused-entry-case-missing")
    fault = create_processing_fault_activity(
        actor=BYSTANDER,
        fault=make(
            as_ProcessingFault,
            failure_class=VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_CASE_DIVERGED,
            in_reply_to=announce_id,
        ),
        to=[MANAGER],
        at=authored_at(),
    )

    store = net.stores[MANAGER]
    case = store.read(net.case_id)
    assert case is not None
    assert store.delete("VulnerabilityCase", net.case_id)
    try:
        verdict = net.receive(MANAGER, delivered_body(fault))
    finally:
        # The network's own checks expect the case back.
        store.save(case)

    assert verdict.disposition is HandlerDisposition.REFUSED
    reason = verdict.reason or ""
    assert "No sender is entitled" in reason
    assert "names no Add(CaseLedgerEntry)" not in reason
