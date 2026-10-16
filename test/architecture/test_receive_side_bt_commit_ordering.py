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

"""
Structural ratchets for receive-side BT composition (CLP-10-006, CLP-10-010).

1. No tree factory under ``vultron/core/behaviors/`` may call
   ``create_guarded_commit_case_ledger_entry_tree`` directly.  Every
   receive-side BT composes through ``create_receive_activity_tree``, which
   fixes the stage order intake → door guards → clock decisions → guards →
   commit → effects.  Only
   ``vultron/core/behaviors/case/receive_activity_tree.py`` — which *defines*
   both factories — is exempt.
2. No rejection validator sits in an effect stage (``replica_effects``,
   ``manager_effects`` or ``refusal_effects``; CLP-10-009).
3. No node that any factory uses as a protocol effect appears as a
   precondition guard anywhere — a corpus-derived check that no effect
   precedes the commit (CLP-10-006 verification).  The refusal-effects
   stage runs only when a guard refuses, so on an accepted delivery its
   nodes never run ahead of the commit; ``test_refusal_stage.py`` pins that
   at run time and ``test_receive_activity_tree.py`` that the factory gates
   it (CLP-10-022).
4. No built received tree commits ahead of its guarded commit except inside
   the clock-decision stage, and there only from a decision's own commit
   nodes — one per AS2 activity the decision needs — never the received
   activity's, and no other protocol-effect node runs inside the stage
   (CLP-10-025).

The intake-first ratchet — every receive-side factory returns the shared
factory's result, with the bypassing and nesting factories as exact sets
(CLP-10-017) — is ``test_receive_side_intake_first.py``, which imports its
helpers from here.

Each is a ratchet: a new violation fails immediately rather than silently
accumulating debt.
"""

import ast

import py_trees
import pytest

from test.architecture import _corpus

# Exempt files: may contain direct calls (definition site only).
EXEMPT_FILES = {
    "vultron/core/behaviors/case/receive_activity_tree.py",
}

BEHAVIORS_ROOT = _corpus.REPO_ROOT / "vultron" / "core" / "behaviors"
FORBIDDEN_CALL = "create_guarded_commit_case_ledger_entry_tree"


def _is_forbidden_call(node: ast.AST) -> bool:
    """Return True if node is a Call to the forbidden function name."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name) and func.id == FORBIDDEN_CALL:
        return True
    return bool(
        isinstance(func, ast.Attribute) and func.attr == FORBIDDEN_CALL
    )


def _find_violations() -> list[tuple[str, int]]:
    """Return (relative_path, line_no) for each forbidden call outside exempt files."""
    violations: list[tuple[str, int]] = []
    for py_file, tree in _corpus.files_mentioning(
        FORBIDDEN_CALL, under=BEHAVIORS_ROOT
    ):
        rel_path = str(py_file.relative_to(_corpus.REPO_ROOT))
        if rel_path in EXEMPT_FILES:
            continue
        for node in ast.walk(tree):
            if _is_forbidden_call(node):
                assert isinstance(node, ast.Call)
                violations.append((rel_path, node.lineno))
    return violations


def test_no_direct_calls_to_guarded_commit_outside_factory_module() -> None:
    """Only receive_activity_tree.py may call create_guarded_commit_case_ledger_entry_tree.

    All receive-side tree factories must use create_receive_activity_tree,
    which enforces commit-before-effects ordering (CLP-10-006).
    """
    violations = _find_violations()
    if violations:
        lines = "\n".join(
            f"  {path}:{line_no}" for path, line_no in violations
        )
        pytest.fail(
            f"Found {len(violations)} direct call(s) to"
            f" `{FORBIDDEN_CALL}` outside the exempt factory module.\n"
            f"Use `create_receive_activity_tree` instead (CLP-10-006):\n"
            f"{lines}"
        )


# ---------------------------------------------------------------------------
# CLP-10-009 ratchet: rejection validators must not appear in an effect stage
# ---------------------------------------------------------------------------

#: Node classes whose only role is to REFUSE an assertion (return FAILURE to
#: reject).  These are precondition guards and MUST appear in
#: ``precondition_guards``, never in an effect stage.
REJECTION_VALIDATORS = {
    "ValidateRMTransitionNode",
    "CheckCaseStatusIdempotencyNode",
    "CheckCsEphemeralStateNode",
    "CheckCsHistoryPrefixNode",
    "FinalizeCsFilterNode",
    "RequireCaseForReport",
}

RECEIVE_ACTIVITY_TREE_CALL = "create_receive_activity_tree"

#: The factory's effect-stage keywords: the BT-17-008 ``replica_effects`` /
#: ``manager_effects`` (which replaced the retired ``effect_nodes``, #4307) and
#: the ``refusal_effects`` that run only when a guard refuses (CLP-10-022).
#: A refusal effect is a protocol effect too: the same node used as a guard
#: elsewhere would run ahead of a commit on an accepted delivery.
EFFECT_KEYWORDS = frozenset(
    {"replica_effects", "manager_effects", "refusal_effects"}
)


def _validator_violations_in_call(
    call: ast.Call, rel_path: str
) -> list[tuple[str, int, str]]:
    """Return violations for one create_receive_activity_tree(...) call."""
    violations: list[tuple[str, int, str]] = []
    for kw in call.keywords:
        if kw.arg not in EFFECT_KEYWORDS:
            continue
        if not isinstance(kw.value, ast.List):
            continue
        for elem in kw.value.elts:
            if not isinstance(elem, ast.Call):
                continue
            name = _corpus.callee_name(elem.func)
            if name in REJECTION_VALIDATORS:
                violations.append((rel_path, elem.lineno, name))
    return violations


def _violations_in_tree(
    tree: ast.AST, rel_path: str
) -> list[tuple[str, int, str]]:
    """Return all CLP-10-009 violations found in an already-parsed tree."""
    violations: list[tuple[str, int, str]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and _corpus.callee_name(node.func) == RECEIVE_ACTIVITY_TREE_CALL
        ):
            violations.extend(_validator_violations_in_call(node, rel_path))
    return violations


def _find_validators_in_effect_nodes() -> list[tuple[str, int, str]]:
    """Return (rel_path, line_no, validator_name) for each violation."""
    violations: list[tuple[str, int, str]] = []
    for py_file, tree in _corpus.files_mentioning(
        RECEIVE_ACTIVITY_TREE_CALL, under=BEHAVIORS_ROOT
    ):
        rel_path = str(py_file.relative_to(_corpus.REPO_ROOT))
        violations.extend(_violations_in_tree(tree, rel_path))
    return violations


@pytest.mark.spec("CLP-10-009")
def test_no_rejection_validators_in_effect_nodes() -> None:
    """Rejection validators must not appear in an effect stage of create_receive_activity_tree.

    A node that refuses an inbound assertion (returns FAILURE) is a
    precondition guard and MUST be placed in ``precondition_guards``.
    Placing it in an effect stage causes it to run after GuardedCommit,
    producing a canonical ledger entry the actor then refuses to apply
    (canonical/replica divergence, ISSUE-2254, CLP-10-009).
    """
    violations = _find_validators_in_effect_nodes()
    if violations:
        lines = "\n".join(
            f"  {path}:{line_no}  ({name})"
            for path, line_no, name in violations
        )
        pytest.fail(
            f"Found {len(violations)} rejection validator(s) in an effect"
            " stage of create_receive_activity_tree.\n"
            "Move them to precondition_guards (CLP-10-009, ISSUE-2254):\n"
            f"{lines}"
        )


# ---------------------------------------------------------------------------
# CLP-10-006 ratchet: no protocol-effect node precedes the commit.  A node any
# factory places in an effect stage is, by that factory's own declaration, a
# protocol effect; the same node in another factory's ``precondition_guards``
# would run before the commit.
# ---------------------------------------------------------------------------


def _list_arg_names(call: ast.Call, arg: str) -> set[str]:
    """Bare callee names of the elements of the ``arg=[...]`` keyword list."""
    for kw in call.keywords:
        if kw.arg != arg or not isinstance(kw.value, ast.List):
            continue
        return {
            name
            for elem in kw.value.elts
            if isinstance(elem, ast.Call)
            and (name := _corpus.callee_name(elem.func)) is not None
        }
    return set()


def _stage_rosters() -> tuple[set[str], dict[str, list[str]]]:
    """Return (names used as effects anywhere, guard names → factory sites)."""
    effects: set[str] = set()
    guards: dict[str, list[str]] = {}
    for py_file, tree in _corpus.files_mentioning(
        RECEIVE_ACTIVITY_TREE_CALL, under=BEHAVIORS_ROOT
    ):
        rel_path = str(py_file.relative_to(_corpus.REPO_ROOT))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and _corpus.callee_name(node.func)
                == RECEIVE_ACTIVITY_TREE_CALL
            ):
                continue
            for keyword in EFFECT_KEYWORDS:
                effects |= _list_arg_names(node, keyword)
            for name in _list_arg_names(node, "precondition_guards"):
                guards.setdefault(name, []).append(f"{rel_path}:{node.lineno}")
    return effects, guards


@pytest.mark.spec("CLP-10-006")
def test_no_effect_node_is_used_as_a_precondition_guard() -> None:
    """A node used as a protocol effect anywhere never precedes the commit anywhere."""
    effects, guards = _stage_rosters()
    assert effects, "no effect_nodes found — corpus prefilter drifted?"
    offenders = {
        name: sites for name, sites in guards.items() if name in effects
    }
    if offenders:
        lines = "\n".join(
            f"  {name} used as a guard at {', '.join(sites)}"
            for name, sites in sorted(offenders.items())
        )
        pytest.fail(
            "Protocol-effect nodes placed before the commit (CLP-10-006):\n"
            f"{lines}"
        )


# ---------------------------------------------------------------------------
# CLP-10-025 ratchet: no commit runs ahead of the guards except inside the
# clock-decision stage, and there only the stage's own commit — never the
# received activity's.  Asked of the *built* trees, so a commit reached
# through a helper or a nested factory is seen where it runs.
# ---------------------------------------------------------------------------

GUARDED_COMMIT_NAME = "GuardedCommitCaseLedgerEntryBT"


def _commit_node_types() -> tuple[type, ...]:
    """Every node class that commits a ledger entry.

    ``CreateLogEntryNode`` mints in-tree; ``CommitCaseLedgerEntryNode`` is the
    received activity's commit.  The others commit a CASE_MANAGER-authored
    activity they build themselves in a nested tree only they can see, so
    they are named here to be checked: ``ExpireOverdueOwnershipOfferNode``
    (the Offer expiry, which Offer is known only when it runs),
    ``_CommitCaseManagerActivityBase`` (the termination ``Remove``,
    ``CommitAndApplyEmbargoTerminationNode``),
    ``EmitCaseStatusUpdateNode`` (the ``Add(CaseStatus)`` that follows an EM
    change) and ``ReissueStubInvitesNode`` (each re-issued stub ``Invite``).
    """
    from vultron.core.behaviors.case.nodes.lifecycle import (
        CommitCaseLedgerEntryNode,
    )
    from vultron.core.behaviors.case.nodes.ownership_offer_expiry import (
        ExpireOverdueOwnershipOfferNode,
    )
    from vultron.core.behaviors.case.nodes.stub_reissue import (
        ReissueStubInvitesNode,
    )
    from vultron.core.behaviors.case_manager_commit import (
        _CommitCaseManagerActivityBase,
    )
    from vultron.core.behaviors.case_status_snapshot import (
        EmitCaseStatusUpdateNode,
    )
    from vultron.core.behaviors.sync.nodes import CreateLogEntryNode

    return (
        CommitCaseLedgerEntryNode,
        CreateLogEntryNode,
        ExpireOverdueOwnershipOfferNode,
        _CommitCaseManagerActivityBase,
        EmitCaseStatusUpdateNode,
        ReissueStubInvitesNode,
    )


def _decision_commit_types() -> tuple[type, ...]:
    """The commit nodes a clock decision may hold: every one but the
    received activity's (CLP-10-025)."""
    from vultron.core.behaviors.case.nodes.lifecycle import (
        CommitCaseLedgerEntryNode,
    )

    return tuple(
        t for t in _commit_node_types() if t is not CommitCaseLedgerEntryNode
    )


def _early_commits(root: py_trees.behaviour.Behaviour) -> list[str]:
    """Commits *root* runs before its guarded commit that CLP-10-025 forbids.

    A commit ahead of the guarded commit is allowed only inside a
    :class:`ClockDecisionStage`, and there only the decision's own
    CASE_MANAGER-authored entries, one per AS2 activity it needs
    (:func:`_decision_commit_types`); the received activity's commit
    (``CommitCaseLedgerEntryNode``) inside the stage would commit the
    activity's own assertion before the guards judge it.  A tree with no
    guarded commit has no "ahead of the commit" and reports nothing.
    """
    from vultron.core.behaviors.case.nodes.clock_decision_stage import (
        ClockDecisionStage,
    )
    from vultron.core.behaviors.case.nodes.lifecycle import (
        CommitCaseLedgerEntryNode,
    )

    names = [child.name for child in root.children]
    if GUARDED_COMMIT_NAME not in names:
        return []
    ahead = root.children[: names.index(GUARDED_COMMIT_NAME)]
    commits = _commit_node_types()
    found: list[str] = []

    def walk(node: py_trees.behaviour.Behaviour, in_stage: bool) -> None:
        in_stage = in_stage or isinstance(node, ClockDecisionStage)
        if isinstance(node, commits) and (
            not in_stage or isinstance(node, CommitCaseLedgerEntryNode)
        ):
            where = "in the clock-decision stage" if in_stage else "outside"
            found.append(f"{type(node).__name__} ({where})")
        for child in node.children:
            walk(child, in_stage)

    for child in ahead:
        walk(child, in_stage=False)
    return found


@pytest.mark.spec("CLP-10-025")
@pytest.mark.spec("CLP-10-010")
def test_only_the_clock_decision_stage_commits_ahead_of_the_guards() -> None:
    """Every received tree commits ahead of its guards only from a clock
    decision's own commit nodes, one per AS2 activity the decision needs."""
    from test.architecture._received_tree_builds import built_received_trees
    from vultron.core.behaviors.case.nodes.clock_decision_stage import (
        ClockDecisionStage,
    )

    trees = built_received_trees()
    offenders = {
        f"{path}:{factory}": found
        for (path, factory), tree in trees.items()
        if (found := _early_commits(tree))
    }
    assert offenders == {}, (
        "Commits ahead of the guarded commit outside a clock decision's own"
        f" entry (CLP-10-025): {offenders}"
    )
    staged = {
        type(n).__name__
        for t in trees.values()
        for stage in t.iterate()
        if isinstance(stage, ClockDecisionStage)
        for n in stage.iterate()
        if isinstance(n, _commit_node_types())
    }
    # Both expiries and every entry of the end-time termination are seen
    # committing inside the stage, so the walk covers the nested committers
    # as well as the in-tree one.
    assert {
        "CreateLogEntryNode",
        "ExpireOverdueOwnershipOfferNode",
        "CommitAndApplyEmbargoTerminationNode",
        "EmitCaseStatusUpdateNode",
        "ReissueStubInvitesNode",
    } <= staged


@pytest.mark.spec("CLP-10-025")
def test_no_protocol_effect_runs_in_the_clock_decision_stage() -> None:
    """A clock decision commits only its own CASE_MANAGER-authored entries
    and the changes they record, so no node a factory uses as a protocol
    effect runs inside the stage, where it would precede the guards, unless
    it commits an AS2 activity of the decision's own (a re-issued stub
    ``Invite`` of an end-time termination, CLP-10-025)."""
    from test.architecture._received_tree_builds import built_received_trees
    from vultron.core.behaviors.case.nodes.clock_decision_stage import (
        ClockDecisionStage,
    )

    effects, _ = _stage_rosters()
    offenders = {
        f"{path}:{factory}": sorted(found)
        for (path, factory), tree in built_received_trees().items()
        if (
            found := {
                type(n).__name__
                for stage in tree.iterate()
                if isinstance(stage, ClockDecisionStage)
                for n in stage.iterate()
                # py_trees composites are structure, not effects.
                if type(n).__name__ in effects
                and not type(n).__module__.startswith("py_trees")
                and not isinstance(n, _decision_commit_types())
            }
        )
    }
    assert offenders == {}, (
        "Protocol-effect nodes inside a clock-decision stage (CLP-10-025):"
        f" {offenders}"
    )


class TestEarlyCommitDetector:
    """The detector flags what the ratchet exists to catch."""

    @staticmethod
    def _tree(
        *ahead: py_trees.behaviour.Behaviour,
    ) -> py_trees.composites.Sequence:
        commit = py_trees.behaviours.Success(name=GUARDED_COMMIT_NAME)
        return py_trees.composites.Sequence(
            name="Root", memory=False, children=[*ahead, commit]
        )

    @staticmethod
    def _decision_commit() -> py_trees.behaviour.Behaviour:
        from vultron.core.behaviors.sync.commit_tree import (
            create_commit_log_entry_tree,
        )

        return create_commit_log_entry_tree(
            case_id="https://example.org/cases/c",
            object_id="https://example.org/objects/o",
            event_type="expired",
        )

    def test_a_commit_among_the_guards_is_flagged(self) -> None:
        tree = self._tree(self._decision_commit())

        assert _early_commits(tree) == ["CreateLogEntryNode (outside)"]

    def test_the_decisions_own_commit_inside_the_stage_is_allowed(
        self,
    ) -> None:
        from vultron.core.behaviors.case.nodes.clock_decision_stage import (
            ClockDecisionStage,
        )

        stage = ClockDecisionStage(
            name="ClockDecisions", decisions=[self._decision_commit()]
        )

        assert _early_commits(self._tree(stage)) == []

    @staticmethod
    def _end_time_decision() -> py_trees.behaviour.Behaviour:
        from datetime import UTC, datetime

        from vultron.core.behaviors.embargo.end_time_tree import (
            end_time_clock_decision,
        )

        return end_time_clock_decision(
            case_id="https://example.org/cases/c",
            now=datetime(2030, 1, 1, tzinfo=UTC),
        )

    def test_a_termination_decision_inside_the_stage_is_allowed(
        self,
    ) -> None:
        """Its several entries, one per AS2 activity, are all its own."""
        from vultron.core.behaviors.case.nodes.clock_decision_stage import (
            ClockDecisionStage,
        )

        stage = ClockDecisionStage(
            name="ClockDecisions", decisions=[self._end_time_decision()]
        )

        assert _early_commits(self._tree(stage)) == []

    def test_a_termination_decision_among_the_guards_is_flagged(
        self,
    ) -> None:
        found = _early_commits(self._tree(self._end_time_decision()))

        assert sorted(found) == [
            "CommitAndApplyEmbargoTerminationNode (outside)",
            "EmitCaseStatusUpdateNode (outside)",
            "ReissueStubInvitesNode (outside)",
        ]

    def test_the_activitys_commit_inside_the_stage_is_flagged(self) -> None:
        from vultron.core.behaviors.case.nodes.clock_decision_stage import (
            ClockDecisionStage,
        )
        from vultron.core.behaviors.case.nodes.lifecycle import (
            CommitCaseLedgerEntryNode,
        )

        stage = ClockDecisionStage(
            name="ClockDecisions",
            decisions=[
                CommitCaseLedgerEntryNode(case_id="https://example.org/c")
            ],
        )

        assert _early_commits(self._tree(stage)) == [
            "CommitCaseLedgerEntryNode (in the clock-decision stage)"
        ]

    def test_a_commit_after_the_guarded_commit_is_not_early(self) -> None:
        tree = self._tree()
        tree.add_child(self._decision_commit())

        assert _early_commits(tree) == []
