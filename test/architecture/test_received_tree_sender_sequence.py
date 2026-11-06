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

"""Every tree that receives a numbered activity judges its number, once.

A participant numbers each case activity it sends the CASE_MANAGER that
states a ``ledgerPosition`` (SYNC-21-001), and the CASE_MANAGER judges each
sender's numbers in order (SYNC-21-008).  ``create_receive_activity_tree``
places the sender-sequence stage
(:func:`~vultron.core.behaviors.sync.sender_sequence_stage.create_sender_sequence_stage`)
in every tree whose sender guard names its sender and case; a tree goes
without it only by naming a registered ``SenderSequenceExemption``.  A tree
that handles a numbered activity and lacks the stage never moves the
sender's expected number past it, so the sender's next activity is held for
a whole wait (SYNC-21-010, SYNC-21-011).  These checks keep that from
happening:

1. **Pinned exemption set** ``SENDER_SEQUENCE_EXEMPTION_USES``: which tree
   passes each exemption (ARCH-18-001, ARCH-18-002).
2. The registry is the module's whole list, each entry with its reason.
3. Every received tree, built as it runs, holds the stage at most once,
   right after the ledger position answer; no tree module composes it.
4. Every routed semantic whose activity its sender numbers, received at the
   case's CASE_MANAGER, runs a tree that holds the stage.  The semantics
   come from ``SEMANTIC_REGISTRY`` and each is built from its vocabulary
   example, numbered by the sender's own rule
   (:func:`~vultron.wire.as2.factories.sender_sequence_case_ids`), so a new
   semantic is covered without an edit here.  The use case runs up to its
   one tree execution (ADR-0135), which is captured, not run.  Building the
   39 use cases costs about a second, over TB-13-004's 0.5 s SHOULD; the
   builds are cached so the checks share one.
"""

import ast
import functools
import inspect
from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import py_trees
import pytest

from test.architecture import _corpus
from test.architecture._received_tree_builds import built_received_trees
from test.architecture._vocab_example_corpus import activity_examples
from test.architecture.test_received_tree_case_manager_gate import (
    _receive_calls,
)
from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_participant,
)
from test.support.received import received_event, stamped
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge.bt_bridge import BTBridge
from vultron.core.behaviors.case.receive_activity_tree import (
    ReceivedActivityTree,
)
from vultron.core.behaviors.sync.ledger_position_stage import (
    LEDGER_POSITION_GATE_NAME,
)
from vultron.core.behaviors.sync.nodes import sender_sequence
from vultron.core.behaviors.sync.nodes.sender_sequence import (
    SENDER_SEQUENCE_EXEMPTIONS,
    SenderSequenceExemption,
    SequenceOrderStage,
)
from vultron.core.behaviors.sync.sender_sequence_stage import (
    SENDER_SEQUENCE_GATE_NAME,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events.base import (
    LedgerPositionedEvent,
    MessageSemantics,
)
from vultron.semantic_registry import SEMANTIC_REGISTRY
from vultron.semantic_registry._entry import SemanticEntry
from vultron.wire.as2.factories import sender_sequence_case_ids
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.examples._base import case as example_case

_KEYWORD = "sender_sequence_exemption"
_STAGE_BUILDER = "create_sender_sequence_stage"
_FACTORY = "vultron/core/behaviors/case/receive_stages/decisions.py"

# permanent: SYNC-21-001 (each entry is a recorded exemption decision)
SENDER_SEQUENCE_EXEMPTION_USES: frozenset[tuple[str, str, str]] = frozenset(
    {
        # A Read(CaseLedgerEntry) is a request about the ledger, not a case
        # event, so its sender numbers it not (SYNC-21-001, CLP-02-013).
        (
            "LEDGER_REQUEST_TAKES_NO_NUMBER",
            "vultron/core/behaviors/sync/read_tree.py",
            "create_read_log_entry_tree",
        ),
    }
)


def _exemption_uses() -> frozenset[tuple[str, str, str]]:
    uses: set[tuple[str, str, str]] = set()
    for rel, scope, call in _receive_calls():
        for kw in call.keywords:
            if kw.arg != _KEYWORD:
                continue
            assert isinstance(kw.value, ast.Name), (
                f"{rel}:{scope}: pass a registered exemption constant from"
                " sender_sequence.py, not an inline value"
            )
            uses.add((kw.value.id, rel, scope))
    return frozenset(uses)


def _stages(
    tree: py_trees.behaviour.Behaviour,
) -> list[py_trees.behaviour.Behaviour]:
    return [n for n in tree.iterate() if isinstance(n, SequenceOrderStage)]


@pytest.mark.spec("SYNC-21-001")
@pytest.mark.spec("ARCH-18-001")
def test_sender_sequence_exemption_uses_are_pinned() -> None:
    actual = _exemption_uses()
    expected = SENDER_SEQUENCE_EXEMPTION_USES
    assert actual == expected, (
        f"NEW: {sorted(actual - expected)}; a new exemption use is a"
        " decision — pin it here with its reason."
        f" STALE: {sorted(expected - actual)}; remove it (ARCH-18-002)"
    )


@pytest.mark.spec("SYNC-21-001")
def test_the_exemption_set_is_closed_and_reasoned() -> None:
    constants = {
        name: value
        for name, value in inspect.getmembers(sender_sequence)
        if isinstance(value, SenderSequenceExemption)
    }
    assert {c.name for c in constants.values()} == set(
        SENDER_SEQUENCE_EXEMPTIONS
    )
    for exemption in constants.values():
        assert SENDER_SEQUENCE_EXEMPTIONS[exemption.name] is exemption
    used = {constant for constant, _, _ in SENDER_SEQUENCE_EXEMPTION_USES}
    assert used == set(constants)


@pytest.mark.spec("CLP-10-005")
@pytest.mark.spec("SYNC-21-008")
def test_every_received_tree_judges_the_number_at_most_once() -> None:
    """A tree nesting a factory-built subtree (the close arm) still judges
    the number once: a second judgment would read its own admission as a
    repeat."""
    twice = {
        f"{rel}:{scope}": len(_stages(tree))
        for (rel, scope), tree in built_received_trees().items()
        if len(_stages(tree)) > 1
    }
    assert twice == {}


@pytest.mark.spec("SYNC-21-023")
@pytest.mark.spec("CLP-10-010")
def test_the_stage_follows_the_ledger_position_answer() -> None:
    """It runs once the door and sender guards admit the activity and the
    position is answered, and before anything judges the act."""
    misplaced: list[str] = []
    placed = 0
    for (rel, scope), tree in built_received_trees().items():
        for received in tree.iterate():
            if not isinstance(received, ReceivedActivityTree):
                continue
            names = [child.name for child in received.children]
            if SENDER_SEQUENCE_GATE_NAME not in names:
                continue
            placed += 1
            index = names.index(SENDER_SEQUENCE_GATE_NAME)
            if names[index - 1] != LEDGER_POSITION_GATE_NAME:
                misplaced.append(f"{rel}:{scope} [{received.name}]")
    assert placed, "no received tree judges a sender sequence"
    assert misplaced == []


@pytest.mark.spec("CLP-10-005")
def test_only_the_factory_composes_the_stage() -> None:
    callers = {
        path.relative_to(_corpus.REPO_ROOT).as_posix()
        for path, tree in _corpus.files_mentioning(
            _STAGE_BUILDER, under=_corpus.REPO_ROOT / "vultron"
        )
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == _STAGE_BUILDER
    }
    assert callers == {_FACTORY}


# ---------------------------------------------------------------------------
# 4. Every numbered semantic, received at the CASE_MANAGER, judges its number.
# ---------------------------------------------------------------------------

_CASE_MANAGER = "https://example.org/sender-sequence-ratchet/case-manager"


def _seed_target_participant(
    dl: SqliteDataLayer, activity: as_Activity, case_id: str
) -> None:
    """Store the participant an ``Add(ParticipantStatus)`` targets.

    The use case reads the case from that record (HP-08-008); with no record
    it names no case, and the sender guard refuses the activity at the door,
    which counts no number (SYNC-21-023).  The example's target names
    another case's participant, so the record is seeded under the example's
    case.
    """
    target = _as_id(activity.target)
    assert target is not None
    dl.create(
        CaseParticipant(
            id_=target, attributed_to=_as_id(activity.actor), context=case_id
        )
    )


#: What the CASE_MANAGER must hold, past the case and the sender's
#: participant record, for a semantic's use case to name the case its tree
#: judges (any other gap would be a refusal at the door, SYNC-21-023).
_EXTRA_SEEDS: dict[
    MessageSemantics, Callable[[SqliteDataLayer, as_Activity, str], None]
] = {
    MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT: (
        _seed_target_participant
    ),
}


class _TreeCaptured(Exception):
    """Stops a use case at its one tree execution, the tree captured."""

    def __init__(self, tree: py_trees.behaviour.Behaviour) -> None:
        super().__init__(tree.name)
        self.tree = tree


def _capture(
    _bridge: BTBridge, tree: py_trees.behaviour.Behaviour, *_: Any, **__: Any
) -> None:
    raise _TreeCaptured(tree)


def _positioned_entries() -> list[SemanticEntry]:
    return [
        entry
        for entry in SEMANTIC_REGISTRY
        if entry.pattern is not None
        and entry.use_case_class is not None
        and isinstance(entry.event_class, type)
        and issubclass(entry.event_class, LedgerPositionedEvent)
    ]


def _example_for(entry: SemanticEntry) -> as_Activity | None:
    """*entry*'s first vocabulary example."""
    assert entry.pattern is not None
    for _, activity in sorted(activity_examples().items()):
        if entry.pattern.match(activity):
            return activity
    return None


def _tree_at_the_case_manager(
    entry: SemanticEntry, activity: as_Activity
) -> py_trees.behaviour.Behaviour | None:
    """The tree *entry*'s use case runs for *activity* at the CASE_MANAGER.

    *activity* is addressed to the CASE_MANAGER, as the sender addresses
    every activity it numbers (SYNC-21-001); each semantic gets a store of
    its own.
    """
    receiver = f"{_CASE_MANAGER}/{entry.semantics.name.lower()}"
    activity = activity.model_copy(update={"to": [receiver]})
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=receiver)
    case = example_case()
    seed_case_manager_participant(dl, case, receiver)
    seed_case_participant(dl, case, str(_as_id(activity.actor)))
    dl.create(case)
    if (seed := _EXTRA_SEEDS.get(entry.semantics)) is not None:
        seed(dl, activity, case.id_)
    event = received_event(activity).model_copy(
        update={"receiving_actor_id": receiver}
    )
    assert entry.use_case_class is not None
    with patch.object(BTBridge, "execute_with_setup", _capture):
        try:
            entry.use_case_class(dl, event).execute()
        except _TreeCaptured as captured:
            return captured.tree
        finally:
            dl.close()
    return None


@functools.cache
def _numbered_semantic_trees() -> dict[
    str, py_trees.behaviour.Behaviour | str
]:
    """Each numbered semantic's tree at the CASE_MANAGER, or why none."""
    trees: dict[str, py_trees.behaviour.Behaviour | str] = {}
    for entry in _positioned_entries():
        name = entry.semantics.name
        activity = _example_for(entry)
        if activity is None:
            trees[name] = "no vocabulary example matches it"
            continue
        if not list(sender_sequence_case_ids(stamped(activity))):
            continue  # its sender numbers it not (SYNC-21-001)
        tree = _tree_at_the_case_manager(entry, activity)
        trees[name] = tree if tree is not None else "its use case ran no tree"
    return trees


@pytest.mark.spec("SYNC-21-008")
@pytest.mark.spec("SYNC-21-001")
def test_every_numbered_semantic_judges_its_number() -> None:
    """A numbered activity whose tree skips the stage is never counted, so
    its sender's next activity waits a whole hold (SYNC-21-010)."""
    trees = _numbered_semantic_trees()
    assert len(trees) > 10, f"too few numbered semantics resolved: {trees}"
    unresolved = {k: v for k, v in trees.items() if isinstance(v, str)}
    assert unresolved == {}, (
        "every numbered semantic must build its tree here; seed what its"
        " use case needs in _EXTRA_SEEDS"
    )
    missing = sorted(
        f"{name} ({tree.name})"
        for name, tree in trees.items()
        if not isinstance(tree, str) and not _stages(tree)
    )
    assert missing == [], (
        "these trees receive an activity its sender numbers but judge no"
        f" senderSequence: {missing}"
    )


@pytest.mark.spec("SYNC-21-001")
def test_the_ledger_request_is_the_only_positioned_semantic_left_unnumbered() -> (
    None
):
    """The sender's own rule leaves out exactly the ledger requests among the
    positioned semantics, so the check above skips nothing else."""
    numbered = set(_numbered_semantic_trees())
    unnumbered = {e.semantics.name for e in _positioned_entries()} - numbered
    assert unnumbered == {MessageSemantics.READ_CASE_LEDGER_ENTRY.name}
