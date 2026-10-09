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
   fixes the stage order intake → guards → commit → effects.  Only
   ``vultron/core/behaviors/case/receive_activity_tree.py`` — which *defines*
   both factories — is exempt.
2. No rejection validator sits in an effect stage (``effect_nodes``,
   ``replica_effects``, ``manager_effects`` or ``refusal_effects``;
   CLP-10-009).
3. No node that any factory uses as a protocol effect appears as a
   precondition guard anywhere — a corpus-derived check that no effect
   precedes the commit (CLP-10-006 verification).  The refusal-effects
   stage runs only when a guard refuses, so on an accepted delivery its
   nodes never run ahead of the commit; ``test_refusal_stage.py`` pins that
   at run time and ``test_receive_activity_tree.py`` that the factory gates
   it (CLP-10-022).

The intake-first ratchet — every receive-side factory returns the shared
factory's result, with the bypassing and nesting factories as exact sets
(CLP-10-017) — is ``test_receive_side_intake_first.py``, which imports its
helpers from here.

Each is a ratchet: a new violation fails immediately rather than silently
accumulating debt.
"""

import ast

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
# CLP-10-009 ratchet: rejection validators must not appear in effect_nodes
# ---------------------------------------------------------------------------

#: Node classes whose only role is to REFUSE an assertion (return FAILURE to
#: reject).  These are precondition guards and MUST appear in
#: ``precondition_guards``, never in ``effect_nodes``.
REJECTION_VALIDATORS = {
    "ValidateRMTransitionNode",
    "CheckCaseStatusIdempotencyNode",
    "CheckCsEphemeralStateNode",
    "CheckCsHistoryPrefixNode",
    "FinalizeCsFilterNode",
    "RequireCaseForReport",
}

RECEIVE_ACTIVITY_TREE_CALL = "create_receive_activity_tree"

#: The factory's effect-stage keywords: the legacy ``effect_nodes``, the
#: BT-17-008 ``replica_effects`` / ``manager_effects`` that replace it, and
#: the ``refusal_effects`` that run only when a guard refuses (CLP-10-022).
#: A refusal effect is a protocol effect too: the same node used as a guard
#: elsewhere would run ahead of a commit on an accepted delivery.
EFFECT_KEYWORDS = frozenset(
    {"effect_nodes", "replica_effects", "manager_effects", "refusal_effects"}
)


def _call_name(node: ast.expr) -> str | None:
    """Return the bare name of a Call expression, or None."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


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
            name = _call_name(elem.func)
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
            and _call_name(node.func) == RECEIVE_ACTIVITY_TREE_CALL
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
    """Rejection validators must not appear in effect_nodes of create_receive_activity_tree.

    A node that refuses an inbound assertion (returns FAILURE) is a
    precondition guard and MUST be placed in ``precondition_guards``.
    Placing it in ``effect_nodes`` causes it to run after GuardedCommit,
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
            f"Found {len(violations)} rejection validator(s) in effect_nodes"
            " of create_receive_activity_tree.\n"
            "Move them to precondition_guards (CLP-10-009, ISSUE-2254):\n"
            f"{lines}"
        )


# ---------------------------------------------------------------------------
# CLP-10-006 ratchet: no protocol-effect node precedes the commit.  A node any
# factory places in ``effect_nodes`` is, by that factory's own declaration, a
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
            and (name := _call_name(elem.func)) is not None
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
                and _call_name(node.func) == RECEIVE_ACTIVITY_TREE_CALL
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
