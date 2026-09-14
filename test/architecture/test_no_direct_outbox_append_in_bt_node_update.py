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
"""Architecture ratchet: no direct ``outbox_append`` calls in BT node ``update()`` methods.

Every BT node that enqueues an outbound activity MUST do so through the
shared emit seam — ``_EmitSingleActivityBase._emit_through_seam()`` (or the
parent ``update()`` that calls it).  Direct ``outbox_append`` calls inside
``update()`` bypass the seam and prevent centralized hooks such as
outstanding-ask registration (ASK-04-008) and undelivered-activity
correlation (OX-14-001).

``vultron/core/behaviors/helpers.py`` is the authoritative seam file and is
excluded from this scan.

A ``KNOWN_VIOLATIONS`` ratchet tracks pre-existing call sites awaiting
migration.  The set is **exact**: new violations fail the test immediately,
and resolved violations (entries in ``KNOWN_VIOLATIONS`` that no longer
appear in the scan) also fail — prompting the entry to be removed from
``KNOWN_VIOLATIONS``.

Spec: OX-14-001 (``specs/outbox.yaml``), ASK-04-008 (``specs/protocol-asks.yaml``).
Issue: #2881 (consolidate outbound emit path).
"""

import ast
from pathlib import Path

from test.architecture import _corpus

_BEHAVIORS_ROOT = _corpus.REPO_ROOT / "vultron" / "core" / "behaviors"
_SEAM_FILE = _BEHAVIORS_ROOT / "helpers.py"


def _is_outbox_append_call(node: ast.AST) -> bool:
    """Return True if *node* is a direct ``outbox_append(...)`` call."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if not isinstance(func, ast.Attribute):
        return False
    return func.attr == "outbox_append"


def _walk_own_scope(node: ast.AST):
    """Yield descendants of *node* without crossing nested function scopes.

    Stops descending at ``FunctionDef``, ``AsyncFunctionDef``, or ``Lambda``
    that is *not* the root *node* itself, so inner helpers defined inside
    ``update()`` are not counted as direct violations of ``update()``.
    """
    yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(
            child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
        ):
            continue
        yield from _walk_own_scope(child)


def _collect_violations() -> frozenset[str]:
    """Return class names whose ``update()`` directly calls ``outbox_append``."""
    violations: set[str] = set()
    for py_file, tree in _corpus.files_mentioning(
        "outbox_append", under=_BEHAVIORS_ROOT
    ):
        if py_file == _SEAM_FILE:
            continue
        for cls_node in ast.walk(tree):
            if not isinstance(cls_node, ast.ClassDef):
                continue
            for method in ast.iter_child_nodes(cls_node):
                if not isinstance(
                    method, (ast.FunctionDef, ast.AsyncFunctionDef)
                ):
                    continue
                if method.name != "update":
                    continue
                for child in _walk_own_scope(method):
                    if _is_outbox_append_call(child):
                        violations.add(cls_node.name)
                        break
    return frozenset(violations)


# ---------------------------------------------------------------------------
# Known pre-existing violations awaiting migration to _EmitSingleActivityBase.
#
# Each class listed here calls ``outbox_append`` directly inside its
# ``update()`` method instead of routing through the shared emit seam.
# Remove an entry once that class's ``update()`` is refactored to use
# ``_emit_through_seam()`` (or the parent ``_EmitSingleActivityBase.update()``).
# Migration tracked in issue #2881.
# ---------------------------------------------------------------------------
KNOWN_VIOLATIONS: frozenset[str] = frozenset(
    {
        # case/accept_invite_tree.py
        "EmitAnnounceCaseToInviteeNode",
        # case/case_proposal_received_tree.py
        "_EmitAcceptCaseProposalNode",
        "_EmitCreateVulnerabilityCaseNode",
        # case/nodes/proposal.py
        "ProposeReportCaseToActorNode",
        # case/nodes/suggest_actor/emit.py
        "EmitOfferCaseParticipantToOwnerNode",
        "EmitNoteDuplicateRecommendationToOwnerNode",
        # case/nodes/suggest_actor/emit_response.py
        "EmitAcceptActorRecommendationNode",
        "EmitRejectActorRecommendationNode",
        # report/nodes/develop_fix.py
        "_EmitParticipantStatusActivityBase",
        # report/nodes/emit.py
        "_EmitCaseActorReportActivityBase",
        "EmitSubmitReportActivity",
        # status/nodes/cs_invariant_diagnostic.py
        "PxaEmInvariantDiagnosticNode",
        # status/nodes/lifecycle.py
        "EmitAddCaseStatusToSelfNode",
        "EmitCloseCaseNode",
        # status/nodes/rm_anomaly.py
        "EmitRMGapNoteNode",
        # sync/nodes/replay.py
        "AnnounceCaseOnGenesisRejectNode",
    }
)


def test_no_direct_outbox_append_in_bt_node_update():
    """BT node update() methods must not call outbox_append() directly.

    All outbound activity enqueuing must go through the shared emit seam
    (``_EmitSingleActivityBase._emit_through_seam()``).

    Spec: OX-14-001, ASK-04-008.  Issue: #2881.

    See module docstring for the ratchet strategy.
    """
    actual = _collect_violations()
    new_violations = actual - KNOWN_VIOLATIONS
    resolved = KNOWN_VIOLATIONS - actual

    diff_lines: list[str] = []
    if new_violations:
        diff_lines.append(
            "NEW violations (update() must not call outbox_append() directly"
            " — use _emit_through_seam() or subclass _EmitSingleActivityBase,"
            " OX-14-001 / ASK-04-008 / issue #2881):"
        )
        diff_lines.extend(f"  + {v}" for v in sorted(new_violations))
    if resolved:
        diff_lines.append(
            "RESOLVED violations (remove these entries from KNOWN_VIOLATIONS"
            " — migration #2881 complete for these classes):"
        )
        diff_lines.extend(f"  - {v}" for v in sorted(resolved))

    assert actual == KNOWN_VIOLATIONS, "\n\n" + "\n".join(diff_lines)


# ---------------------------------------------------------------------------
# Synthetic detector-validation tests
# ---------------------------------------------------------------------------


def test_detector_catches_direct_outbox_append_in_update(
    tmp_path: Path,
) -> None:
    """Confirm the scanner flags a direct outbox_append() call in update()."""
    violation_file = tmp_path / "synthetic_violation.py"
    violation_file.write_text(
        "class FakeNode:\n"
        "    def update(self):\n"
        "        self.datalayer.outbox_append('x')\n",
        encoding="utf-8",
    )
    source = violation_file.read_text()
    tree = _corpus.parse_inline(source)
    violations: set[str] = set()
    for cls_node in ast.walk(tree):
        if not isinstance(cls_node, ast.ClassDef):
            continue
        for method in ast.iter_child_nodes(cls_node):
            if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if method.name != "update":
                continue
            for child in _walk_own_scope(method):
                if _is_outbox_append_call(child):
                    violations.add(cls_node.name)
    assert "FakeNode" in violations


def test_detector_ignores_outbox_append_in_helper_method(
    tmp_path: Path,
) -> None:
    """Confirm the scanner does NOT flag outbox_append in a non-update() method."""
    clean_file = tmp_path / "synthetic_clean.py"
    clean_file.write_text(
        "class CleanNode:\n"
        "    def _emit_through_seam(self, activity_id, blob):\n"
        "        self.datalayer.outbox_append(activity_id)\n"
        "    def update(self):\n"
        "        self._emit_through_seam('x', '{}')\n",
        encoding="utf-8",
    )
    source = clean_file.read_text()
    tree = _corpus.parse_inline(source)
    violations: set[str] = set()
    for cls_node in ast.walk(tree):
        if not isinstance(cls_node, ast.ClassDef):
            continue
        for method in ast.iter_child_nodes(cls_node):
            if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if method.name != "update":
                continue
            for child in _walk_own_scope(method):
                if _is_outbox_append_call(child):
                    violations.add(cls_node.name)
    assert "CleanNode" not in violations


def test_detector_ignores_outbox_append_in_nested_inner_function(
    tmp_path: Path,
) -> None:
    """Confirm the scanner does NOT flag outbox_append inside an inner function in update()."""
    clean_file = tmp_path / "synthetic_nested.py"
    clean_file.write_text(
        "class NestedNode:\n"
        "    def update(self):\n"
        "        def _inner():\n"
        "            self.datalayer.outbox_append('x')\n"
        "        _inner()\n",
        encoding="utf-8",
    )
    source = clean_file.read_text()
    tree = _corpus.parse_inline(source)
    violations: set[str] = set()
    for cls_node in ast.walk(tree):
        if not isinstance(cls_node, ast.ClassDef):
            continue
        for method in ast.iter_child_nodes(cls_node):
            if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if method.name != "update":
                continue
            for child in _walk_own_scope(method):
                if _is_outbox_append_call(child):
                    violations.add(cls_node.name)
    assert "NestedNode" not in violations
