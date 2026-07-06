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
"""Architecture ratchet: wire vocab/objects/ classes must not shadow core model names.

All Vultron-specific wire vocabulary classes in
``vultron/wire/as2/vocab/objects/`` MUST use the ``as_`` prefix so they
cannot be confused with identically-named core domain models in
``vultron/core/models/``.  The ``as_`` prefix is already established for
base ActivityStreams types (``as_Activity``, ``as_Actor``, ``as_Object``) and
must be extended to every Vultron-specific wire object in that package.

Spec: ARCH-14-001 (``specs/architecture.yaml``).

Ratchet pattern
---------------
``KNOWN_VIOLATIONS`` documents every pre-existing name collision awaiting
the ``as_`` prefix migration (tracked in GitHub issue #1056).  The test
asserts::

    actual_collisions == KNOWN_VIOLATIONS

This means:
- A **new** collision (not in ``KNOWN_VIOLATIONS``) fails immediately —
  preventing any further regression.
- A **resolved** collision (in ``KNOWN_VIOLATIONS`` but no longer present)
  also fails — prompting the removal of that entry from ``KNOWN_VIOLATIONS``
  so the ratchet stays tight.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]  # test/architecture/ → test/ → repo root

_WIRE_OBJECTS = REPO_ROOT / "vultron" / "wire" / "as2" / "vocab" / "objects"
_CORE_MODELS = REPO_ROOT / "vultron" / "core" / "models"


def _class_names(directory: Path) -> dict[str, str]:
    """Return {class_name: repo-relative file path} for all non-private classes."""
    result: dict[str, str] = {}
    for py_file in directory.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and not node.name.startswith(
                "_"
            ):
                result[node.name] = py_file.relative_to(REPO_ROOT).as_posix()
    return result


def _collect_collisions() -> frozenset[str]:
    """Return the set of class names that appear in both wire and core."""
    wire_classes = _class_names(_WIRE_OBJECTS)
    core_classes = _class_names(_CORE_MODELS)
    return frozenset(wire_classes.keys() & core_classes.keys())


# ---------------------------------------------------------------------------
# Known pre-existing name collisions awaiting the as_ prefix migration.
#
# Each entry is a bare class name that exists in BOTH
#   vultron/wire/as2/vocab/objects/
# AND
#   vultron/core/models/
#
# Fix: add the as_ prefix to the wire class (ARCH-14-001).
# Migration tracked in issue #1056.
# ---------------------------------------------------------------------------
KNOWN_VIOLATIONS: frozenset[str] = frozenset(
    {
        "CaseActor",
        "CaseLedgerEntry",
        "CaseParticipant",
        "CaseReference",
        "CaseStatus",
        "EmbargoEvent",
        "EmbargoPolicy",
        "ParticipantStatus",
        "VulnerabilityCase",
        "VulnerabilityRecord",
        "VulnerabilityReport",
        "VultronApplication",
        "VultronGroup",
        "VultronOrganization",
        "VultronPerson",
        "VultronService",
    }
)


def test_wire_vocab_objects_do_not_shadow_core_model_names():
    """No class in wire/as2/vocab/objects/ may share a name with a core model class.

    Enforces ARCH-14-001.  See module docstring for the ratchet strategy.
    """
    actual = _collect_collisions()
    new_violations = actual - KNOWN_VIOLATIONS
    resolved = KNOWN_VIOLATIONS - actual

    diff_lines: list[str] = []
    if new_violations:
        diff_lines.append(
            "NEW violations — wire vocab class shadows a core model name "
            "(ARCH-14-001): add the as_ prefix to the wire class."
        )
        diff_lines.extend(f"  + {v}" for v in sorted(new_violations))
    if resolved:
        diff_lines.append(
            "RESOLVED violations — remove these entries from KNOWN_VIOLATIONS "
            "(as_ prefix migration #1056 complete for these classes):"
        )
        diff_lines.extend(f"  - {v}" for v in sorted(resolved))

    assert actual == KNOWN_VIOLATIONS, "\n\n" + "\n".join(diff_lines)
