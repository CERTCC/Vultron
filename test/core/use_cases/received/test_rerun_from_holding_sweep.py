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

"""Every received handling tree tolerates a re-run from holding (#5047 AC-1).

A run that ends with no verdict leaves its message's record in holding, and
the next delivery runs the handling tree again from the body held
(ADR-0154).  For every routed semantic, this sweep runs one delivery whose
first run reaches its tree's effects, then runs it again from holding, and
asserts by content that the second run committed and queued nothing new
(SYNC-09-002, OX-06-002, ID-02-003).

Each tree with refusal effects is also refused at the CASE_MANAGER and run
again, so its refusal effects are proved too.  Both kinds are also driven
down the longer path: the re-run is held for a replay, and the replay, which
reads as a first run because releasing the record deletes it, runs once more.

The subjects come from ``use_case_map()``: collection fails for a routed
semantic with no builder (``rerun_sweep``), and a tree whose first run built
a refusal stage fails when no refusal builder covers it.  Each builder must
reach its effects on the first run, so a builder refused at a door fails
rather than passing on an empty comparison.
"""

from typing import Any

import py_trees
import pytest

from test.support.ledger_rebuild import run_use_case
from test.support.received import received_event
from test.support.rerun_from_holding import (
    drained_rerun,
    effects,
    rerun_from_holding,
    rerun_then_replay,
)
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.behaviors.case.nodes.refusal_stage import (
    PreconditionGuardStage,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.received_activity_record import ReceivedStage
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.services.received_activity import (
    held_received_record,
    sealed_body_of,
)
from vultron.core.services.received_holding import (
    hold_for_replay,
    release_from_holding,
)
from vultron.semantic_registry import use_case_map
from vultron.wire.as2.parser import parse_activity

from ._ledger_network import BYSTANDER, MANAGER, LedgerNetwork
from .rerun_sweep import (
    APPLIED,
    NO_TREE,
    REFUSAL_UNREACHABLE,
    REFUSED,
    Scenario,
)
from .rerun_sweep.drained_failures import (
    CLASSES,
    DRAINED_FAILURES,
    PinnedDrainedFailure,
    drained_failure_classes,
    pinned_classes,
)
from .test_sender_sequence import _note_body


def _subjects() -> list[MessageSemantics]:
    """Every routed semantic; raise when one has no builder (collection).

    Raises:
        RuntimeError: a routed semantic has neither a builder nor a
            declared no-tree reason, or a builder names a semantic that is
            no longer routed.
    """
    routed = set(use_case_map())
    covered = set(APPLIED) | set(NO_TREE)
    missing = sorted(s.value for s in routed - covered)
    stale = sorted(
        s.value
        for s in (covered | set(REFUSED) | set(REFUSAL_UNREACHABLE)) - routed
    )
    both = sorted(
        s.value
        for s in (set(APPLIED) & set(NO_TREE))
        | (set(REFUSED) & set(REFUSAL_UNREACHABLE))
    )
    if missing or stale or both:
        raise RuntimeError(
            "re-run sweep subjects do not match use_case_map():"
            f" no builder for {missing}; builders for unrouted {stale};"
            f" two declarations (a builder and a no-tree reason, or a"
            f" refusal builder and an unreachable reason) for {both}"
            " (test/core/use_cases/received/rerun_sweep)"
        )
    return sorted(routed, key=lambda s: s.value)


_SUBJECTS = _subjects()
_TREE_SUBJECTS = [s for s in _SUBJECTS if s in APPLIED]
_REFUSAL_SUBJECTS = sorted(REFUSED, key=lambda s: s.value)


def _ids(semantics: list[MessageSemantics]) -> list[str]:
    return [s.value for s in semantics]


def _assert_doubled_nothing(
    semantic: MessageSemantics, doubled: list[str], first: Any, last: Any
) -> None:
    assert doubled == [], (
        f"{semantic.value}: a later run committed or queued again: {doubled}"
    )
    # Equal by content and by queue order: a second queue entry under an id
    # already queued is a second send too.
    assert last == first, f"{semantic.value}: the store changed again"


def _assert_built(semantic: MessageSemantics, scenario: Scenario) -> None:
    assert scenario.event.semantic_type is semantic, (
        f"{semantic.value}: the builder made a"
        f" {scenario.event.semantic_type.value} delivery"
    )


def _assert_reached(
    semantic: MessageSemantics, scenario: Scenario, before: Any, after: Any
) -> None:
    """The first run did something a re-run could do again."""
    if scenario.reached is not None:
        problem = scenario.reached(scenario.dl)
        assert problem is None, f"{semantic.value}: {problem}"
        return
    assert after != before, (
        f"{semantic.value}: the first run committed and queued nothing, so"
        " the re-run comparison would be empty"
    )


def _refusal_stages(
    tree: py_trees.behaviour.Behaviour,
) -> list[PreconditionGuardStage]:
    return [n for n in tree.iterate() if isinstance(n, PreconditionGuardStage)]


@pytest.mark.spec("SYNC-09-002", "OX-06-002", "ID-02-003", "CLP-10-005")
@pytest.mark.parametrize("semantic", _TREE_SUBJECTS, ids=_ids(_TREE_SUBJECTS))
def test_a_rerun_from_holding_commits_and_sends_nothing_twice(
    semantic: MessageSemantics, tree_runs: list[py_trees.behaviour.Behaviour]
) -> None:
    scenario = APPLIED[semantic]()
    _assert_built(semantic, scenario)
    before = effects(scenario.dl)
    # A builder may deliver set-up messages, which run trees of their own.
    start = len(tree_runs)

    rerun = rerun_from_holding(scenario.dl, scenario.event, run=scenario.run)

    assert rerun.first.disposition is scenario.disposition, (
        f"{semantic.value}: {rerun.first.reason}"
    )
    assert len(tree_runs) > start, (
        f"{semantic.value}: the first run ran no tree"
    )
    _assert_reached(semantic, scenario, before, rerun.after_first)
    _assert_doubled_nothing(
        semantic, rerun.doubled, rerun.after_first, rerun.after_second
    )
    has_refusal_stage = bool(_refusal_stages(tree_runs[start]))
    if semantic in REFUSAL_UNREACHABLE:
        assert has_refusal_stage, (
            f"{semantic.value}: declared refusal-unreachable, but its tree"
            " has no refusal stage; drop it from REFUSAL_UNREACHABLE"
        )
    elif has_refusal_stage and semantic not in REFUSED:
        pytest.fail(
            f"{semantic.value}: its tree has refusal effects, but no refusal"
            " builder drives them (rerun_sweep @refused)"
        )


@pytest.mark.spec("SYNC-09-002", "OX-06-002", "ID-02-003", "CLP-10-044")
@pytest.mark.parametrize("semantic", _TREE_SUBJECTS, ids=_ids(_TREE_SUBJECTS))
def test_a_replay_after_a_held_rerun_commits_and_sends_nothing_twice(
    semantic: MessageSemantics,
) -> None:
    """Crash, re-run, hold for a replay, replay: still nothing twice."""
    scenario = APPLIED[semantic]()
    before = effects(scenario.dl)

    replayed = rerun_then_replay(scenario.dl, scenario.event, run=scenario.run)

    assert replayed.rerun.first.disposition is scenario.disposition
    _assert_reached(semantic, scenario, before, replayed.rerun.after_first)
    _assert_doubled_nothing(
        semantic,
        replayed.doubled,
        replayed.rerun.after_first,
        replayed.after_replay,
    )


def _assert_refusal_reached(
    semantic: MessageSemantics, first: Any, before: Any, after: Any
) -> None:
    """The first run was refused and its refusal effects queued something.

    A refusal commits nothing for the refused act (CLP-10-048), so anything
    new in the ledger or the outbox is a refusal effect: the notice, or the
    RSH-06-004 note.  A delivery refused at a door changes neither.
    """
    assert first.disposition is HandlerDisposition.REFUSED, (
        f"{semantic.value}: the refusal builder's first run was"
        f" {first.disposition.value}: {first.reason}"
    )
    assert after != before, (
        f"{semantic.value}: the first run was refused ({first.reason}) but"
        " reached no refusal effect"
    )


@pytest.mark.spec("CLP-10-044", "CLP-05-001", "ID-04-004")
@pytest.mark.parametrize(
    "semantic", _REFUSAL_SUBJECTS, ids=_ids(_REFUSAL_SUBJECTS)
)
def test_a_refused_rerun_from_holding_answers_once(
    semantic: MessageSemantics, tree_runs: list[py_trees.behaviour.Behaviour]
) -> None:
    scenario = REFUSED[semantic]()
    _assert_built(semantic, scenario)
    before = effects(scenario.dl)
    start = len(tree_runs)

    rerun = rerun_from_holding(scenario.dl, scenario.event, run=scenario.run)

    _assert_refusal_reached(semantic, rerun.first, before, rerun.after_first)
    stages = _refusal_stages(tree_runs[start])
    assert stages and not stages[0].skipped_as_redelivery
    _assert_doubled_nothing(
        semantic, rerun.doubled, rerun.after_first, rerun.after_second
    )


@pytest.mark.spec("CLP-10-044", "CLP-05-001", "ID-04-004")
@pytest.mark.parametrize(
    "semantic", _REFUSAL_SUBJECTS, ids=_ids(_REFUSAL_SUBJECTS)
)
def test_a_refused_replay_after_a_held_rerun_answers_once(
    semantic: MessageSemantics,
) -> None:
    """The replay runs the refusal effects again; nothing is sent twice."""
    scenario = REFUSED[semantic]()
    _assert_built(semantic, scenario)
    before = effects(scenario.dl)

    replayed = rerun_then_replay(scenario.dl, scenario.event, run=scenario.run)

    _assert_refusal_reached(
        semantic, replayed.rerun.first, before, replayed.rerun.after_first
    )
    assert replayed.replay.disposition is HandlerDisposition.REFUSED
    _assert_doubled_nothing(
        semantic,
        replayed.doubled,
        replayed.rerun.after_first,
        replayed.after_replay,
    )


_TREELESS = sorted(NO_TREE, key=lambda s: s.value)


@pytest.mark.parametrize("semantic", _TREELESS, ids=_ids(_TREELESS))
def test_a_semantic_declared_treeless_runs_no_tree(
    semantic: MessageSemantics, tree_runs: list[py_trees.behaviour.Behaviour]
) -> None:
    reason, builder = NO_TREE[semantic]
    scenario = builder()
    _assert_built(semantic, scenario)
    before = effects(scenario.dl)
    start = len(tree_runs)

    scenario.run(scenario.dl, scenario.event)

    assert tree_runs[start:] == [], (
        f"{semantic.value} ran a tree; {reason!r} is stale"
    )
    assert effects(scenario.dl) == before


def _queued_announcements(dl: Any, before: Any, *, to: str) -> list[str]:
    """``Announce(CaseLedgerEntry)`` ids queued for *to* since *before*."""
    queued = {activity_id for activity_id, _ in before.outbox}
    found = []
    for activity_id in dl.outbox_list():
        body = read_sealed_body_dict(dl, activity_id) or {}
        entry = body.get("object") or {}
        if (
            activity_id not in queued
            and body.get("type") == "Announce"
            and isinstance(entry, dict)
            and entry.get("type") == "CaseLedgerEntry"
            and to in (body.get("to") or [])
        ):
            found.append(activity_id)
    return found


def _entry_index(dl: Any, announce_id: str) -> int:
    body = read_sealed_body_dict(dl, announce_id) or {}
    return int(body["object"]["logIndex"])


@pytest.mark.spec("SYNC-18-007", "SYNC-18-009", "SYNC-15-003", "OX-06-002")
def test_a_replay_after_a_held_rerun_answers_a_lagging_position_once() -> None:
    """The replay answers a lagging sender's position again; nothing is sent.

    The bystander has applied the first entry, and the second one's
    announcement to it was lost, when it sends a note: its stamped position
    lags the CASE_MANAGER's ledger, and the first run answers by replaying
    the entry it lacks (SYNC-18-007).  That replay is then delivered, so it
    leaves the outbox.  The re-run skips the answer (SYNC-18-009); the
    replay, whose record was released, reads as a first run and answers
    again, and must send nothing a second time.
    """
    net = LedgerNetwork("https://example.org/cases/rerun-sweep/lagging")
    manager_dl = net.stores[MANAGER]
    net.receive(MANAGER, _note_body(net, "first"))
    net.replay_ledger(BYSTANDER)
    net.receive(MANAGER, _note_body(net, "second"))
    net.lose(MANAGER, to=BYSTANDER, type_="Announce")
    body = net.stamp(
        _note_body(net, "lagging", actor=BYSTANDER), receiver=MANAGER
    )
    assert body["ledgerPosition"]["logIndex"] == 0, body["ledgerPosition"]
    event = received_event(
        parse_activity(body), as_sent=True, receiving_actor_id=MANAGER
    )
    before = effects(manager_dl)

    first = run_use_case(manager_dl, event)

    assert first.disposition is HandlerDisposition.APPLIED, first.reason
    answered = _queued_announcements(manager_dl, before, to=BYSTANDER)
    # The lag answer replayed the second entry; the note's own entry is the
    # third.
    assert [_entry_index(manager_dl, a) for a in answered] == [1, 2]
    net.lose(MANAGER, to=BYSTANDER, type_="Announce")
    delivered = effects(manager_dl)

    rerun = run_use_case(manager_dl, event)
    record = held_received_record(manager_dl, event.activity_id)
    assert record is not None and record.stage is ReceivedStage.HANDLED
    assert hold_for_replay(
        manager_dl, event.activity_id, sealed_body_of(record)
    )
    assert release_from_holding(manager_dl, event.activity_id) is not None
    replay = run_use_case(manager_dl, event)

    assert rerun.disposition is not HandlerDisposition.REFUSED, rerun.reason
    assert replay.disposition is not HandlerDisposition.REFUSED, replay.reason
    assert effects(manager_dl) == delivered


def _drained_params() -> list[Any]:
    """Every (path, kind, semantic), each pinned failure a strict xfail."""
    params = []
    for path in ("rerun", "replay"):
        for kind, table in (("applied", APPLIED), ("refused", REFUSED)):
            for semantic in sorted(table, key=lambda s: s.value):
                classes = DRAINED_FAILURES.get((path, kind, semantic))
                marks = (
                    [
                        pytest.mark.xfail(
                            strict=True,
                            raises=PinnedDrainedFailure,
                            reason=(
                                f"#5047 part 3, class {classes}: "
                                + "; ".join(
                                    CLASSES[c]
                                    for c in sorted(pinned_classes(classes))
                                )
                            ),
                        )
                    ]
                    if classes
                    else []
                )
                params.append(
                    pytest.param(
                        path,
                        kind,
                        semantic,
                        marks=marks,
                        id=f"{path}-{kind}-{semantic.value}",
                    )
                )
    return params


def test_every_pinned_drained_failure_names_a_scenario() -> None:
    """A pin with no scenario behind it is stale."""
    tables = {"applied": APPLIED, "refused": REFUSED}
    stale = sorted(
        f"{path}-{kind}-{semantic.value}"
        for path, kind, semantic in DRAINED_FAILURES
        if path not in ("rerun", "replay") or semantic not in tables[kind]
    )
    assert stale == []
    assert set(DRAINED_FAILURES.values()) <= {
        ", ".join(c) for c in ("A", "B", "C", "AB", "AC", "BC", "ABC")
    }


@pytest.mark.spec("SYNC-09-002", "OX-06-002", "CLP-05-006")
@pytest.mark.parametrize(("path", "kind", "semantic"), _drained_params())
def test_a_later_run_after_the_outbox_drained_sends_nothing_again(
    path: str, kind: str, semantic: MessageSemantics
) -> None:
    """The first run's sends are delivered before the later run.

    The inbox drains the outbox after each delivery, even one whose work
    raised (``_run_serialised``), so a re-run, and the replay of a re-run
    held for its retry, may find the first run's sends already gone.  The
    later run must commit nothing new and queue nothing at all.
    """
    scenario = (APPLIED if kind == "applied" else REFUSED)[semantic]()
    _assert_built(semantic, scenario)
    before = effects(scenario.dl)

    sender = str(scenario.event.actor_id)
    drained = drained_rerun(
        scenario.dl, scenario.event, replay=path == "replay", run=scenario.run
    )

    if kind == "applied":
        assert drained.first.disposition is scenario.disposition
        _assert_reached(semantic, scenario, before, drained.after_first)
    else:
        _assert_refusal_reached(
            semantic, drained.first, before, drained.after_first
        )
    pin = DRAINED_FAILURES.get((path, kind, semantic))
    if pin is not None and drained.sent_again:
        _raise_if_only_pinned(drained, pin, kind=kind, sender=sender)
    assert drained.sent_again == [], (
        f"{semantic.value}: the {path} sent again after the drain:"
        f" {drained.sent_again}"
    )


def _raise_if_only_pinned(
    drained: Any, pin: str, *, kind: str, sender: str
) -> None:
    """Raise the pinned failure when the sends match the pin, else fail.

    Raises:
        PinnedDrainedFailure: every item sent again is in a class the pin
            names, and every named class is seen; the strict ``xfail``
            accepts this exception alone.
    """
    seen, unexplained = drained_failure_classes(
        drained, kind=kind, sender=sender
    )
    expected = pinned_classes(pin)
    if seen == expected and not unexplained:
        raise PinnedDrainedFailure(
            f"class {pin}, as pinned: {drained.sent_again}"
        )
    pytest.fail(
        f"pinned as class {pin}, but the later run sent classes"
        f" {sorted(seen)} and items no class explains: {unexplained}"
        f" (sent again: {drained.sent_again})"
    )
