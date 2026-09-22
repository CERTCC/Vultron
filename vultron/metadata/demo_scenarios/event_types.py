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
"""Read a scenario harness's expected event types (ISSUE-3505).

Each ``test/ci/invariants/test_XXX_invariants.py`` declares one
``_XXX_EXPECTED_EVENT_TYPES`` constant, and Invariant 5 asserts the scenario's
authoritative log contains every entry in it.  That constant is therefore the
live answer to "which protocol event types does this scenario exercise", and two
``notes/`` tables mirror it: the tick matrix in
``notes/demo-ci-scenario-coverage.md`` and the ``Additional required`` column of
``notes/demo-ci-invariants.md``.  MS-16-002 requires such a mirror to be derived
or ratcheted rather than left as prose, so this module supplies the source side.

**Read by AST, not by import.**  ``test_universal_event_types.py`` reads the same
constant by importing the harness, which is right in a test — pytest is already
loaded and the fixtures are already importable.  It would be wrong here:
``uv run demo-scenarios --check`` is a pre-commit hook, and importing nine test
modules to answer a documentation question would execute their module-level
``globals().update(make_universal_invariant_tests(...))`` calls and make the hook
depend on the test environment.  Parsing the assignment costs nothing and cannot
run anything.

Requirements: ``specs/meta-specifications.yaml`` MS-16-002;
``specs/demo-ci.yaml`` DEMOCI-11-007;
``specs/multi-actor-demo.yaml`` DEMOMA-16-001.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from vultron.demo.scenario.registry import ScenarioSpec
from vultron.metadata.base import repo_root

#: The DEMOMA-16-001 universal event types, in the order the harnesses list
#: them.  Duplicated from ``test_universal_event_types._UNIVERSAL_EVENT_TYPES``
#: only in spelling: that tuple is the *test's* assertion about the harnesses,
#: and importing a test module from production tooling is the coupling this
#: module's docstring rejects.  The two are held together by
#: ``test_universal_event_types_agree_with_the_metadata_reader``.
UNIVERSAL_EVENT_TYPES: tuple[str, ...] = (
    "validate_report",
    "add_participant_status_to_participant",
    "close_case",
    "add_note_to_case",
    "engage_case",
)

_EXPECTED_CONST_RE = re.compile(r"^_[A-Z0-9_]+_EXPECTED_EVENT_TYPES$")


class HarnessEventTypeError(Exception):
    """A harness does not declare its expected event types readably."""


def _string_value(node: ast.expr) -> str | None:
    """Return the event-type string *node* carries, or ``None``.

    Two accepted spellings, matching what pytest accepts as a ``parametrize``
    argument: a bare string, or ``pytest.param("event_type", id=...)`` — the
    convention every harness actually uses.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Call) and node.args:
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value
    return None


def harness_event_types(
    spec: ScenarioSpec, root: Path | None = None
) -> tuple[str, ...] | None:
    """Return *spec*'s expected event types in declaration order.

    ``None`` when the harness file does not exist. A specified-but-unbuilt
    scenario has no harness, and reporting that as a table disagreement would
    make the planned register's own rows fail the tick check.

    Raises:
        HarnessEventTypeError: If the harness exists but declares no readable
            ``_XXX_EXPECTED_EVENT_TYPES``, or declares more than one. Raised
            rather than returning empty, because "this scenario exercises no
            event types" is never the true answer and would silently satisfy
            an all-blank row.
    """
    base = root or repo_root()
    path = base / spec.harness_path
    if not path.is_file():
        return None

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[str, tuple[str, ...]]] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        names = [
            target.id
            for target in node.targets
            if isinstance(target, ast.Name)
            and _EXPECTED_CONST_RE.match(target.id)
        ]
        if not names:
            continue
        if not isinstance(node.value, (ast.List, ast.Tuple)):
            raise HarnessEventTypeError(
                f"{spec.harness_path}: {names[0]} is not a list or tuple "
                "literal, so its event types cannot be read without executing "
                "the module (ISSUE-3505)."
            )
        values: list[str] = []
        for element in node.value.elts:
            value = _string_value(element)
            if value is None:
                raise HarnessEventTypeError(
                    f"{spec.harness_path}: {names[0]} holds an entry that is "
                    "neither a string nor pytest.param('<event_type>', …), so "
                    "the notes/ tables cannot be ratcheted against it "
                    "(ISSUE-3505)."
                )
            values.append(value)
        found.append((names[0], tuple(values)))

    if len(found) != 1:
        raise HarnessEventTypeError(
            f"{spec.harness_path} must declare exactly one "
            f"_XXX_EXPECTED_EVENT_TYPES constant at module level; found "
            f"{sorted(name for name, _values in found)}."
        )
    return found[0][1]


def additional_event_types(harness: tuple[str, ...]) -> frozenset[str]:
    """Return the event types *harness* requires beyond the universal block.

    The complement is what the ``Additional required`` column holds, so the
    comparison is against the constant rather than against everything the ledger
    records: ``notes/demo-ci-scenario-coverage.md`` documents event types that
    are recorded but deliberately excluded from the expected lists
    (``add_case_participant``), and a check reading the ledger would report
    those as missing rows.
    """
    return frozenset(harness) - frozenset(UNIVERSAL_EVENT_TYPES)


__all__ = [
    "UNIVERSAL_EVENT_TYPES",
    "HarnessEventTypeError",
    "additional_event_types",
    "harness_event_types",
]
