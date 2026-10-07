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
"""Intake-first ratchet for receive-side tree factories (CLP-10-017, ADR-0111).

Every receive-side tree factory *returns* the result of
``create_receive_activity_tree``, so the intake node is the first child of
every received tree.  A factory that never calls the shared factory runs no
intake; one that calls it but nests the result under a hand-built root runs a
guard or a branch ahead of intake.  Both are held as exact sets (ARCH-18-001)
that only shrink.  A receive-side factory is one a module under
``vultron/core/use_cases/received/`` calls, or one whose name says so.

Companion to ``test_receive_side_bt_commit_ordering.py``, which owns the
stage-order ratchets (guarded commit only through the factory, no rejection
validator among the effects, no effect node used as a guard) and the helpers
this module imports from it.
"""

import ast
import re

import pytest

from test.architecture import _corpus
from test.architecture.test_receive_side_bt_commit_ordering import (
    BEHAVIORS_ROOT,
    RECEIVE_ACTIVITY_TREE_CALL,
    _call_name,
)

#: A tree factory whose name says it handles a received activity.
_RECEIVE_FACTORY_NAME = re.compile(r"^create_.*(received|receive).*_tree$")
_TREE_FACTORY_NAME = re.compile(r"_tree$")

_RECEIVED_USE_CASES_ROOT = (
    _corpus.REPO_ROOT / "vultron" / "core" / "use_cases" / "received"
)


def _factories_called_from_received_use_cases() -> set[str]:
    """Names of ``*_tree`` factories a received-side use case calls.

    The received use-case package is the authority on which trees are
    receive-side: a factory it calls builds a tree that runs on a received
    activity, whatever the factory is named.
    """
    called: set[str] = set()
    for _, tree in _corpus.files_mentioning(
        "_tree(", under=_RECEIVED_USE_CASES_ROOT
    ):
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and (name := _call_name(node.func)) is not None
                and _TREE_FACTORY_NAME.search(name)
            ):
                called.add(name)
    return called


def _locals_bound_to_calls(func: ast.FunctionDef) -> dict[str, str]:
    """Local name → bare callee name for every ``name = X(...)`` in *func*."""
    assigned: dict[str, str] = {}
    for node in ast.walk(func):
        if not (
            isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
        ):
            continue
        if (name := _call_name(node.value.func)) is None:
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                assigned[target.id] = name
    return assigned


def _root_call_names(func: ast.FunctionDef) -> set[str]:
    """Bare names of the calls whose result *func* returns.

    Covers ``return X(...)`` and ``root = X(...); return root``.  A factory
    whose every return is the shared factory's result puts intake first; one
    that returns a hand-built composite around it does not, whatever it calls
    inside.
    """
    assigned = _locals_bound_to_calls(func)
    roots: set[str] = set()
    for node in ast.walk(func):
        if not isinstance(node, ast.Return) or node.value is None:
            continue
        value = node.value
        if isinstance(value, ast.Call):
            if (name := _call_name(value.func)) is not None:
                roots.add(name)
        elif isinstance(value, ast.Name) and value.id in assigned:
            roots.add(assigned[value.id])
    return roots


#: Per receive-side factory: (rel_path, every name it calls, root call names).
_Factory = tuple[str, set[str], set[str]]


def _receive_factories() -> dict[str, _Factory]:
    """Map each receive-side factory name to what it calls and what it returns.

    A factory under ``vultron/core/behaviors/`` is receive-side when a
    received use case calls it, or when its name says so (a factory only
    reached through another factory).
    """
    from_use_cases = _factories_called_from_received_use_cases()
    factories: dict[str, _Factory] = {}
    for py_file, tree in _corpus.files_mentioning(
        "_tree(", under=BEHAVIORS_ROOT
    ):
        rel_path = str(py_file.relative_to(_corpus.REPO_ROOT))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name == RECEIVE_ACTIVITY_TREE_CALL:
                continue
            if not (
                node.name in from_use_cases
                or _RECEIVE_FACTORY_NAME.match(node.name)
            ):
                continue
            called = {
                name
                for call in ast.walk(node)
                if isinstance(call, ast.Call)
                and (name := _call_name(call.func)) is not None
            }
            factories[node.name] = (rel_path, called, _root_call_names(node))
    return factories


def _calls_shared_factory(
    name: str,
    factories: dict[str, _Factory],
    seen: frozenset[str] = frozenset(),
) -> bool:
    """True if *name* calls the shared factory anywhere, directly or via another factory."""
    _, called, _ = factories[name]
    if RECEIVE_ACTIVITY_TREE_CALL in called:
        return True
    return any(
        _calls_shared_factory(other, factories, seen | {name})
        for other in called
        if other in factories and other not in seen
    )


def _composes_through_shared_factory(
    name: str,
    factories: dict[str, _Factory],
    seen: frozenset[str] = frozenset(),
) -> bool:
    """True if every root *name* returns is the shared factory's result.

    Directly, or through another receive-side factory that is.  A factory
    that returns nothing recognisable (no ``return X(...)`` and no local bound
    from one) does not compose.
    """
    _, _, roots = factories[name]
    if not roots:
        return False
    return all(
        root == RECEIVE_ACTIVITY_TREE_CALL
        or (
            root in factories
            and root not in seen
            and _composes_through_shared_factory(
                root, factories, seen | {name}
            )
        )
        for root in roots
    )


#: Receive-side factories that never call the shared factory and therefore
#: run no intake node (CLP-10-017).  Exact set (ARCH-18-001): remove an
#: entry in the commit that moves the factory (ARCH-18-002).
#: ADR-0111 detail 7 named the two that composed the CASE_MANAGER gate
#: directly; those moved with #3870.  The rest moved with #3871–#3874, #3935
#: and #4288.  What remains synthesises an entry or runs after a received
#: activity was already handled; none processes a received activity of its
#: own, so each entry below names the spec or ADR that keeps it here.
#: ``create_commit_log_entry_tree`` is not in the set: it is the subtree the
#: commit node runs, not a tree a received handler calls (#3935).
KNOWN_FACTORIES_BYPASSING_INTAKE: frozenset[str] = frozenset(
    {
        # embargo — a CM-10-006 follow-on, not a receive-activity tree: it is
        # given no activity and sends what the fan-out withheld once the gate
        # admits a participant, so it has no received activity to archive
        # (CM-10-006, ADR-0118).
        "embargo_admission_backfill_tree",
        # expiry tree — the CASE_MANAGER-gated expiry evaluation called from
        # AcceptInviteToEmbargoOnCaseReceivedUseCase; synthesises and commits an
        # expiry entry without processing the received activity itself
        # (CM-28-009, CM-28-014, BT-17-001, ADR-0118).
        "create_invite_expiry_tree",
        # honour-late-accept tree — the CASE_MANAGER-gated honour decision
        # called from AcceptInviteToEmbargoOnCaseReceivedUseCase for the
        # EMB-17-001 branch; commits a synthesised honour entry, not a received
        # one, then applies EXPIRED/DECLINED → SIGNATORY (ADR-0118, RSH-08-004).
        "create_honour_late_accept_tree",
        # noop-ledger-entry tree — called from _commit_noop_ledger_entry in
        # AcceptInviteToEmbargoOnCaseReceivedUseCase for the EMB-17-004 no-op
        # branch; commits a synthesised entry, not a received one (ADR-0118).
        # create_commit_log_entry_tree is no longer called directly from
        # received use case files (ARCH-18-002).
        "create_noop_ledger_entry_tree",
        # re-invite tree — called from _handle_emb17_routing for the EMB-17-003
        # stale-embargo branch; commits the manager's own emission under its
        # CASE_MANAGER gate, not a received assertion (EMB-17-011).
        "create_reinvite_stale_accepter_tree",
    }
)

#: Receive-side factories that call the shared factory but return a
#: hand-built composite around it, so a guard or a branch runs before intake
#: and a run that branch turns away leaves no archive (CLP-10-017,
#: CLP-10-018).  Exact set (ARCH-18-001), empty since the close-case tree
#: lifted intake to its root in #3870; a new entry needs the issue that
#: retires it named beside it.
KNOWN_FACTORIES_NESTING_INTAKE: frozenset[str] = frozenset()


def _exact_set_report(
    label: str,
    actual: frozenset[str],
    known: frozenset[str],
    factories: dict[str, _Factory],
    fix: str,
) -> list[str]:
    """Lines naming what joined and what left *known*, for the assertion message."""
    lines: list[str] = []
    if new := actual - known:
        lines.append(f"NEW receive-side factories {fix}:")
        lines.extend(f"  + {n}  ({factories[n][0]})" for n in sorted(new))
    if resolved := known - actual:
        lines.append(f"RESOLVED — remove from {label} (ARCH-18-002):")
        lines.extend(f"  - {n}" for n in sorted(resolved))
    return lines


@pytest.mark.spec("CLP-10-017")
def test_receive_side_factories_compose_through_shared_factory() -> None:
    """Every receive-side tree factory returns create_receive_activity_tree's result.

    A factory that never calls it gets no intake node, so a refused
    assertion leaves no record of what arrived (CLP-10-018); one that nests
    it under a hand-built root runs something ahead of intake.  Both sets
    are exact: they may only shrink.
    """
    factories = _receive_factories()
    assert factories, "no receive-side tree factories found — regex drifted?"
    bypassing = frozenset(
        n for n in factories if not _calls_shared_factory(n, factories)
    )
    nesting = frozenset(
        n
        for n in factories
        if n not in bypassing
        and not _composes_through_shared_factory(n, factories)
    )
    lines = _exact_set_report(
        "KNOWN_FACTORIES_BYPASSING_INTAKE",
        bypassing,
        KNOWN_FACTORIES_BYPASSING_INTAKE,
        factories,
        "bypassing create_receive_activity_tree (CLP-10-017 — compose"
        " through the shared factory)",
    ) + _exact_set_report(
        "KNOWN_FACTORIES_NESTING_INTAKE",
        nesting,
        KNOWN_FACTORIES_NESTING_INTAKE,
        factories,
        "nesting create_receive_activity_tree under a hand-built root"
        " (CLP-10-017 — return the shared factory's result so intake is the"
        " first child)",
    )
    assert (
        bypassing == KNOWN_FACTORIES_BYPASSING_INTAKE
        and nesting == KNOWN_FACTORIES_NESTING_INTAKE
    ), "\n\n" + "\n".join(lines)


@pytest.mark.spec("CLP-10-010")
@pytest.mark.spec("CLP-10-017")
def test_shared_factory_orders_intake_guards_commit_effects() -> None:
    """The four stages appear in CLP-10-010 order, intake first, with or without a commit."""
    from py_trees.behaviours import Success

    from vultron.core.behaviors.case.nodes.intake import (
        IntakeReceivedActivityNode,
    )
    from vultron.core.behaviors.case.receive_activity_tree import (
        create_receive_activity_tree,
    )

    guard = Success(name="Guard")
    effect = Success(name="Effect")
    tree = create_receive_activity_tree(
        name="OrderedBT",
        case_id="https://example.org/cases/order",
        precondition_guards=[guard],
        effect_nodes=[effect],
    )
    names = [child.name for child in tree.children]
    assert isinstance(tree.children[0], IntakeReceivedActivityNode)
    assert names == [
        "IntakeReceivedActivityNode",
        "Guard",
        "GuardedCommitCaseLedgerEntryBT",
        "Effect",
    ]

    no_commit = create_receive_activity_tree(
        name="NoCommitBT",
        case_id=None,
        precondition_guards=[Success(name="Guard")],
        effect_nodes=[Success(name="Effect")],
    )
    assert isinstance(no_commit.children[0], IntakeReceivedActivityNode)
    assert [c.name for c in no_commit.children] == [
        "IntakeReceivedActivityNode",
        "Guard",
        "Effect",
    ]
