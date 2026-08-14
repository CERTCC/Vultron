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

"""AC-7 architecture ratchet: audit VFD/RM/PXA dimension write sites.

AST-scans ``vultron/core/behaviors/`` for every ``VfdDimension``,
``RmDimension``, and ``PxaDimension`` constructor call and asserts the result
matches the audited set below.

A new unclassified constructor call fails this test immediately, which forces
an explicit audit decision:

- If the site is already protected (trigger guard, received-path filter, or a
  classified bootstrap/predicate use), add it to ``AUDITED_SITES`` with a
  comment stating why.
- If it is a new user-driven write outside the protected paths, add transition
  validation before merging.

Per specs/behavior-tree-node-design.yaml BTND-10-001.
Closes #2081 AC-7, #1903.
"""

import ast
import pathlib
from collections import Counter

# ---------------------------------------------------------------------------
# Audited sites — (path_relative_to_behaviors_root, constructor_name)
# One entry per call-site occurrence (multiplicity matters).
#
# Classification key:
#   PROTECTED  — user-driven write covered by ValidateTriggerTransitionsNode
#                (trigger path) or FilterParticipantStatusDimensionsNode
#                (received path)
#   BOOTSTRAP  — initial / authoritative seeding write; no prior state to
#                violate; outside the scope of transition validation
#   PREDICATE  — read-only dimension instantiation (guard / is_*() checks),
#                no DataLayer write
#   RM-TRACKED — RM transition nodes documented in rm_transitions.py;
#                tracked separately per BTND-10-001 / issue #2081
#   FILTER     — carry-forward writes inside FilterParticipantStatusDimensions-
#                Node (received path); the filter adjudicates before writing
#   REPLICATE  — authoritative ledger-replication write with monotonic ratchet
# ---------------------------------------------------------------------------
AUDITED_SITES: list[tuple[str, str]] = sorted(
    [
        # PROTECTED — CreateParticipantStatusNode (trigger + received paths)
        ("case/nodes/participant/status.py", "PxaDimension"),
        ("case/nodes/participant/status.py", "RmDimension"),
        ("case/nodes/participant/status.py", "VfdDimension"),
        # BOOTSTRAP — case_proposal_received_tree: seeds RM.RECEIVED/VALID/ACCEPTED
        ("case/case_proposal_received_tree.py", "RmDimension"),
        ("case/case_proposal_received_tree.py", "RmDimension"),
        ("case/case_proposal_received_tree.py", "RmDimension"),
        # BOOTSTRAP — participant/common.py: initial accepted-status builder
        ("case/nodes/participant/common.py", "RmDimension"),
        ("case/nodes/participant/common.py", "RmDimension"),
        ("case/nodes/participant/common.py", "RmDimension"),
        ("case/nodes/participant/common.py", "RmDimension"),
        ("case/nodes/participant/common.py", "VfdDimension"),
        # BOOTSTRAP — owner.py: initial owner RM state seeding
        ("case/nodes/participant/owner.py", "RmDimension"),
        ("case/nodes/participant/owner.py", "RmDimension"),
        # PREDICATE — deploy_fix.py: VfdDimension.is_fix_deployed() / is_fix_ready()
        ("report/nodes/deploy_fix.py", "VfdDimension"),
        ("report/nodes/deploy_fix.py", "VfdDimension"),
        # PREDICATE — develop_fix.py: VfdDimension.is_fix_ready()
        ("report/nodes/develop_fix.py", "VfdDimension"),
        # RM-TRACKED — rm_transitions.py: RM.VALID / RM.INVALID / RM.CLOSED writes
        ("report/nodes/rm_transitions.py", "RmDimension"),
        ("report/nodes/rm_transitions.py", "RmDimension"),
        ("report/nodes/rm_transitions.py", "RmDimension"),
        # FILTER — FilterParticipantStatusDimensionsNode carry-forward
        ("status/nodes/dimension_filter.py", "PxaDimension"),
        ("status/nodes/dimension_filter.py", "RmDimension"),
        ("status/nodes/dimension_filter.py", "VfdDimension"),
        # REPLICATE — participant_status_effect.py: monotonic RM ratchet
        ("sync/nodes/participant_status_effect.py", "RmDimension"),
    ]
)


def _collect_sites() -> list[tuple[str, str]]:
    """Return sorted (rel_path, constructor_name) pairs from an AST scan."""
    target_names = {"VfdDimension", "RmDimension", "PxaDimension"}
    root = pathlib.Path("vultron/core/behaviors")
    found: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(), filename=str(path))
        except SyntaxError:  # pragma: no cover
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name: str | None = None
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name in target_names:
                rel = str(path.relative_to("vultron/core/behaviors"))
                # Normalise path separators for cross-platform consistency.
                found.append((rel.replace("\\", "/"), name))
    return sorted(found)


def test_audited_write_sites_unchanged() -> None:
    """All VfdDimension/RmDimension/PxaDimension sites match the audited set.

    A NEW site (file or extra call in an existing file) causes this test to
    fail with a clear diff so the reviewer can decide which classification
    label applies.  A REMOVED site also fails — the audited list must stay
    current.
    """
    actual = _collect_sites()
    actual_counts = Counter(actual)
    expected_counts = Counter(AUDITED_SITES)

    new_sites = actual_counts - expected_counts
    removed_sites = expected_counts - actual_counts

    messages: list[str] = []
    if new_sites:
        messages.append(
            "NEW unaudited dimension write sites found — classify and add to"
            " AUDITED_SITES:\n"
            + "\n".join(
                f"  + {path!r}  {ctor}" for path, ctor in sorted(new_sites)
            )
        )
    if removed_sites:
        messages.append(
            "Sites in AUDITED_SITES no longer present — remove from list:\n"
            + "\n".join(
                f"  - {path!r}  {ctor}" for path, ctor in sorted(removed_sites)
            )
        )
    assert not messages, "\n\n".join(messages)
