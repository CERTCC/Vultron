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
"""Architecture ratchet: direct VFD/RM/PXA dimension write sites in behaviors.

AC-7 (issue #2081): audit confirms that all ``VfdDimension(state=…)``,
``RmDimension(state=…)``, and ``PxaDimension(state=…)`` call sites within
``vultron/core/behaviors/`` fall into one of the following exempt categories:

- **validated-write** — ``status.py`` delegates to ``CreateParticipantStatusNode``
  which now validates transitions (the fix in this PR).
- **bootstrap-seeding** — ``owner.py`` and ``common.py``: deliberate known-state
  writes for newly-joining participants where no prior state exists.
- **guard-predicate** — ``develop_fix.py`` / ``deploy_fix.py``: ``VfdDimension``
  used as a read-only state helper (``is_fix_ready()``, ``is_fix_deployed()``),
  not as a DataLayer write.
- **rm-transitions** — ``rm_transitions.py``: tracked separately under the RM
  state machine; each write is guarded by its own upstream BT condition.
- **case-proposal** — ``case_proposal_received_tree.py``: bootstrap-seeding on
  first-time receipt of a case proposal, no prior state available.

This test records the exact set of write sites found during the AC-7 audit.
New sites not in ``AUDITED_WRITE_SITES`` fail immediately (regression guard).
Sites in ``AUDITED_WRITE_SITES`` that no longer appear also fail (stale entry).

Spec: SDO-02-004, BTND-10-001 (``specs/behavior-tree-node-design.yaml``).
Issue: #2081, #1896.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
_BEHAVIORS_ROOT = REPO_ROOT / "vultron" / "core" / "behaviors"

# Dimension constructors that constitute a state write.
_WRITE_CONSTRUCTORS: frozenset[str] = frozenset(
    {"VfdDimension", "RmDimension", "PxaDimension"}
)

# Each entry is (relative_path_from_behaviors_root, constructor_name).
AUDITED_WRITE_SITES: frozenset[tuple[str, str]] = frozenset(
    {
        # validated-write: inside CreateParticipantStatusNode, after transition check
        ("case/nodes/participant/status.py", "PxaDimension"),
        ("case/nodes/participant/status.py", "RmDimension"),
        ("case/nodes/participant/status.py", "VfdDimension"),
        # bootstrap-seeding: new participant, no prior state
        ("case/nodes/participant/owner.py", "RmDimension"),
        ("case/nodes/participant/common.py", "RmDimension"),
        ("case/nodes/participant/common.py", "VfdDimension"),
        # guard-predicate: VfdDimension used as helper, not persisted
        ("report/nodes/develop_fix.py", "VfdDimension"),
        ("report/nodes/deploy_fix.py", "VfdDimension"),
        # rm-transitions: guarded by upstream BT conditions
        ("report/nodes/rm_transitions.py", "RmDimension"),
        # case-proposal: bootstrap on first receipt
        ("case/case_proposal_received_tree.py", "RmDimension"),
    }
)


def _constructor_name(call: ast.Call) -> str | None:
    """Return the constructor name if *call* is a tracked dimension write, else None."""
    func = call.func
    name = None
    if isinstance(func, ast.Name):
        name = func.id
    elif isinstance(func, ast.Attribute):
        name = func.attr
    if name not in _WRITE_CONSTRUCTORS:
        return None
    if not any(kw.arg == "state" for kw in call.keywords):
        return None
    return name


def _write_sites_in_file(py_file: Path, root: Path) -> set[tuple[str, str]]:
    """Return (rel_path, constructor_name) pairs for each write site in *py_file*."""
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    rel = str(py_file.relative_to(root))
    return {
        (rel, name)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for name in (_constructor_name(node),)
        if name is not None
    }


def _collect_write_sites(root: Path) -> set[tuple[str, str]]:
    """Return (relative_path, constructor_name) pairs for each write site found."""
    found: set[tuple[str, str]] = set()
    for py_file in root.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        found |= _write_sites_in_file(py_file, root)
    return found


def test_vfd_rm_pxa_write_sites_match_audit():
    """AC-7: dimension write sites in behaviors/ match the audited set exactly."""
    found = _collect_write_sites(_BEHAVIORS_ROOT)

    new_sites = found - AUDITED_WRITE_SITES
    removed_sites = AUDITED_WRITE_SITES - found

    messages: list[str] = []
    if new_sites:
        lines = "\n".join(
            f"  {rel} — {ctor}" for rel, ctor in sorted(new_sites)
        )
        messages.append(
            f"NEW unaudited write sites found (add to AUDITED_WRITE_SITES"
            f" after classifying):\n{lines}"
        )
    if removed_sites:
        lines = "\n".join(
            f"  {rel} — {ctor}" for rel, ctor in sorted(removed_sites)
        )
        messages.append(
            f"Previously-audited write sites no longer present"
            f" (remove from AUDITED_WRITE_SITES):\n{lines}"
        )

    assert not messages, "\n\n".join(messages)
