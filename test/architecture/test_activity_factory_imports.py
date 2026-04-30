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
"""Architecture boundary test: vocab.activities import enforcement.

``vultron.wire.as2.vocab.activities`` contains internal Pydantic validator
subclasses used exclusively by the factory layer.  Production code (core,
adapters, demo) and test code (use-case tests, BT tests) **MUST** construct
activities via factory functions in ``vultron.wire.as2.factories`` instead of
importing these internal classes directly.

Spec: AF-05-001, AF-06-001, AF-06-002

Ratchet pattern
---------------
``ALLOWED_PREFIXES`` lists repo-relative path prefixes where imports from
``vultron.wire.as2.vocab.activities`` are *expected and legitimate*.

``KNOWN_VIOLATIONS`` documents every pre-existing violation that has not yet
been migrated (AF.8–10 migration debt).  The test asserts::

    actual_violations == KNOWN_VIOLATIONS

This means:

* **Adding a new violation** (growing ``actual``) causes the test to **fail**
  immediately — no new imports of internal classes are allowed.
* **Fixing a violation** (shrinking ``actual``) also causes the test to
  **fail** until the resolved entry is removed from ``KNOWN_VIOLATIONS`` —
  keeping the allowlist tidy.

Remove entries from ``KNOWN_VIOLATIONS`` one by one as each call site in
AF.8–10 is migrated to factory functions.  When the set is empty the boundary
is completely clean.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]  # test/architecture/ → test/ → repo root

_VOCAB_ACTIVITIES = "vultron.wire.as2.vocab.activities"

# ---------------------------------------------------------------------------
# Paths that are ALLOWED to import from vultron.wire.as2.vocab.activities
# ---------------------------------------------------------------------------
# Only the narrowest set that genuinely needs the internal classes:
#   - vocab/activities/ itself (the class definitions)
#   - factories/         (factory functions directly instantiate these classes)
#   - test/wire/as2/vocab/ (white-box tests for the vocabulary layer)
#   - test/architecture/   (this file)
ALLOWED_PREFIXES: tuple[str, ...] = (
    "vultron/wire/as2/vocab/activities/",
    "vultron/wire/as2/factories/",
    "test/wire/as2/vocab/",
    "test/architecture/",
)

# ---------------------------------------------------------------------------
# Known pre-existing violations  (AF.8–10 migration debt)
# ---------------------------------------------------------------------------
# Remove entries as each call site is migrated to vultron.wire.as2.factories.
KNOWN_VIOLATIONS: frozenset[str] = frozenset(
    {
        # --- vultron/ source violations ---
        "vultron/core/behaviors/case/nodes.py",
        "vultron/core/behaviors/case/suggest_actor_tree.py",
        "vultron/core/behaviors/report/nodes.py",
        "vultron/core/use_cases/received/actor.py",
        "vultron/core/use_cases/received/note.py",
        "vultron/core/use_cases/received/sync.py",
        "vultron/core/use_cases/triggers/actor.py",
        "vultron/core/use_cases/triggers/case.py",
        "vultron/core/use_cases/triggers/embargo.py",
        "vultron/core/use_cases/triggers/note.py",
        "vultron/core/use_cases/triggers/report.py",
        "vultron/core/use_cases/triggers/sync.py",
        "vultron/demo/exchange/acknowledge_demo.py",
        "vultron/demo/exchange/establish_embargo_demo.py",
        "vultron/demo/exchange/initialize_case_demo.py",
        "vultron/demo/exchange/initialize_participant_demo.py",
        "vultron/demo/exchange/invite_actor_demo.py",
        "vultron/demo/exchange/manage_case_demo.py",
        "vultron/demo/exchange/manage_embargo_demo.py",
        "vultron/demo/exchange/manage_participants_demo.py",
        "vultron/demo/exchange/receive_report_demo.py",
        "vultron/demo/exchange/status_updates_demo.py",
        "vultron/demo/exchange/suggest_actor_demo.py",
        "vultron/demo/exchange/transfer_ownership_demo.py",
        "vultron/demo/exchange/trigger_demo.py",
        "vultron/demo/scenario/multi_vendor_demo.py",
        "vultron/demo/scenario/three_actor_demo.py",
        "vultron/demo/scenario/two_actor_demo.py",
        "vultron/demo/utils.py",
        "vultron/semantic_registry.py",
        # --- test/ violations ---
        "test/adapters/driven/test_db_record.py",
        "test/adapters/driven/test_sqlite_backend.py",
        "test/adapters/driving/fastapi/routers/test_trigger_actor.py",
        "test/adapters/driving/fastapi/routers/test_trigger_embargo.py",
        "test/adapters/driving/fastapi/test_outbox.py",
        "test/core/behaviors/case/test_nodes.py",
        "test/core/use_cases/received/test_actor_announce_case.py",
        "test/core/use_cases/received/test_actor.py",
        "test/core/use_cases/received/test_case.py",
        "test/core/use_cases/received/test_embargo.py",
        "test/core/use_cases/received/test_note.py",
        "test/core/use_cases/received/test_reject_sync.py",
        "test/core/use_cases/received/test_status.py",
        "test/core/use_cases/received/test_sync.py",
        "test/core/use_cases/triggers/test_actor_triggers.py",
        "test/core/use_cases/triggers/test_embargo.py",
        "test/core/use_cases/triggers/test_service.py",
        "test/core/use_cases/triggers/test_trignotify.py",
        "test/test_semantic_activity_patterns.py",
        # --- vultron/wire/as2/vocab/examples/ violations ---
        "vultron/wire/as2/vocab/examples/actor.py",
        "vultron/wire/as2/vocab/examples/case.py",
        "vultron/wire/as2/vocab/examples/embargo.py",
        "vultron/wire/as2/vocab/examples/note.py",
        "vultron/wire/as2/vocab/examples/participant.py",
        "vultron/wire/as2/vocab/examples/report.py",
        "vultron/wire/as2/vocab/examples/status.py",
    }
)


def _imports_from_vocab_activities(source_path: Path) -> bool:
    """Return True if the file imports from ``vultron.wire.as2.vocab.activities``."""
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == _VOCAB_ACTIVITIES or module.startswith(
                _VOCAB_ACTIVITIES + "."
            ):
                return True
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == _VOCAB_ACTIVITIES or alias.name.startswith(
                    _VOCAB_ACTIVITIES + "."
                ):
                    return True
    return False


def _collect_violations() -> frozenset[str]:
    """Return repo-relative paths of files that violate the boundary rule."""
    violations: set[str] = set()
    for py_file in REPO_ROOT.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        rel = py_file.relative_to(REPO_ROOT).as_posix()
        if any(rel.startswith(prefix) for prefix in ALLOWED_PREFIXES):
            continue
        if _imports_from_vocab_activities(py_file):
            violations.add(rel)
    return frozenset(violations)


def test_vocab_activities_boundary():
    """No file outside the allowed layer may import internal vocab activity classes.

    Spec: AF-05-001, AF-06-001

    See module docstring for the ratchet strategy.  To add a migration:

    1. Rewrite the call site to use ``vultron.wire.as2.factories``.
    2. Remove the corresponding entry from ``KNOWN_VIOLATIONS``.
    3. Run this test to confirm the set shrinks as expected.
    """
    actual = _collect_violations()
    new_violations = actual - KNOWN_VIOLATIONS
    resolved = KNOWN_VIOLATIONS - actual

    diff_lines: list[str] = []
    if new_violations:
        diff_lines.append(
            "NEW violations (must migrate to factories or add to KNOWN_VIOLATIONS):"
        )
        diff_lines.extend(f"  + {v}" for v in sorted(new_violations))
    if resolved:
        diff_lines.append(
            "RESOLVED violations (remove these entries from KNOWN_VIOLATIONS):"
        )
        diff_lines.extend(f"  - {v}" for v in sorted(resolved))

    assert actual == KNOWN_VIOLATIONS, "\n\n" + "\n".join(diff_lines)
