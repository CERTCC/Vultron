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
"""Architecture boundary test: core layer must not import from wire layer.

``vultron/core/`` is the innermost layer in the hexagonal architecture.  It
MUST NOT import from ``vultron/wire/`` — neither at module level nor via
deferred (local) imports.  The wire layer is an adapter and depends on core,
not the other way around.

Spec: ARCH-01-001; HP-04-001 (``specs/handler-protocol.yaml``).

HP-04-001 leans on this boundary: a handler reads activity data as typed
fields of its ``VultronEvent`` subclass and never re-reads the inbound wire
activity.  With no core → wire import there is no path from a handler to the
AS2 parser or the semantic extractor, and the second test below pins the
other half — ``VultronEvent.activity`` (and every subclass narrowing of it)
resolves to the core ``VultronActivity``, never a wire ``as_*`` class.

Ratchet pattern
---------------
``KNOWN_VIOLATIONS`` documents every pre-existing violation awaiting
migration.  The test asserts::

    actual_violations == KNOWN_VIOLATIONS

This means:

* **Adding a new violation** causes the test to **fail** immediately.
* **Fixing a violation** also causes the test to **fail** until the resolved
  entry is removed from ``KNOWN_VIOLATIONS``.

Remove entries from ``KNOWN_VIOLATIONS`` one by one as each violation is
fixed.  When the set is empty the boundary is completely clean.
"""

import ast
import types
import typing

import vultron.core.models.events  # noqa: F401 — registers every event subclass
from test.architecture import _corpus
from vultron.core.models.activity import VultronActivity
from vultron.core.models.events import CreateReportReceivedEvent
from vultron.core.models.events.base import VultronEvent

_WIRE_MODULE = "vultron.wire"

_CORE_ROOT = _corpus.REPO_ROOT / "vultron" / "core"


def _imports_from_wire(tree: ast.AST) -> bool:
    """Return True if *tree* contains any import from vultron.wire.

    Detects both top-level and deferred (local) imports, catching violations
    like ``from vultron.wire.as2.factories import ...`` placed inside a
    function body.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == _WIRE_MODULE or module.startswith(_WIRE_MODULE + "."):
                return True
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == _WIRE_MODULE or alias.name.startswith(
                    _WIRE_MODULE + "."
                ):
                    return True
    return False


def _collect_violations() -> frozenset[str]:
    """Return repo-relative paths of core files that import from wire."""
    violations: set[str] = set()
    for py_file, tree in _corpus.files_mentioning(
        _WIRE_MODULE, under=_CORE_ROOT
    ):
        if _imports_from_wire(tree):
            violations.add(py_file.relative_to(_corpus.REPO_ROOT).as_posix())
    return frozenset(violations)


# ---------------------------------------------------------------------------
# Known pre-existing violations awaiting migration.
# These files import wire types that have not yet been abstracted behind ports.
# Remove an entry from this set when the violation is resolved.
# ---------------------------------------------------------------------------
KNOWN_VIOLATIONS: frozenset[str] = frozenset()


def test_core_does_not_import_wire():
    """vultron/core/ must not import from vultron/wire/ at any code path.

    Spec: ARCH-01-001

    See module docstring for the ratchet strategy.
    """
    actual = _collect_violations()
    new_violations = actual - KNOWN_VIOLATIONS
    resolved = KNOWN_VIOLATIONS - actual

    diff_lines: list[str] = []
    if new_violations:
        diff_lines.append("NEW violations (core must not import from wire):")
        diff_lines.extend(f"  + {v}" for v in sorted(new_violations))
    if resolved:
        diff_lines.append(
            "RESOLVED violations (remove these entries from KNOWN_VIOLATIONS):"
        )
        diff_lines.extend(f"  - {v}" for v in sorted(resolved))

    assert actual == KNOWN_VIOLATIONS, "\n\n" + "\n".join(diff_lines)


# ---------------------------------------------------------------------------
# HP-04-001: the activity a handler reads is the core type, never a wire class
# ---------------------------------------------------------------------------


_EVENTS_PACKAGE = "vultron.core.models.events"


def _event_subclasses() -> frozenset[type[VultronEvent]]:
    """Every ``VultronEvent`` subclass the events package defines.

    ``__subclasses__()`` is process-wide, so a test-local stub subclass
    defined elsewhere in the session is excluded by module — otherwise the
    check would depend on collection order.
    """
    found: set[type[VultronEvent]] = set()
    pending: list[type[VultronEvent]] = list(VultronEvent.__subclasses__())
    while pending:
        cls = pending.pop()
        if cls in found:
            continue
        found.add(cls)
        pending.extend(cls.__subclasses__())
    return frozenset(
        cls
        for cls in found
        if cls.__module__ == _EVENTS_PACKAGE
        or cls.__module__.startswith(_EVENTS_PACKAGE + ".")
    )


def _member_types(hint: object) -> frozenset[object]:
    """The concrete members of *hint*, unwrapping ``X | None`` / ``Optional[X]``."""
    if typing.get_origin(hint) in (types.UnionType, typing.Union):
        return frozenset(typing.get_args(hint)) - {type(None)}
    return frozenset({hint})


def test_vultron_event_activity_is_the_core_activity_type():
    """HP-04-001: ``VultronEvent.activity`` resolves to the core ``VultronActivity``.

    Optional on the base (subclasses that always carry one narrow it to
    required), and never a wire ``as_*`` class.
    """
    hint = typing.get_type_hints(VultronEvent)["activity"]

    assert _member_types(hint) == {VultronActivity}, hint
    assert VultronActivity.__module__.startswith("vultron.core."), (
        VultronActivity.__module__
    )
    assert not VultronActivity.__name__.startswith("as_")


def test_every_event_subclass_carries_a_core_activity():
    """HP-04-001: no subclass re-types ``activity`` as a wire class.

    A subclass may drop the ``None`` branch (an activity it always carries)
    but the object it carries is always the core ``VultronActivity``.
    """
    subclasses = _event_subclasses()
    # Guard against a vacuous pass: the events package must have registered
    # its concrete subclasses through the import above.
    assert CreateReportReceivedEvent in subclasses

    offenders = {
        cls.__name__: hint
        for cls in subclasses
        if _member_types(hint := typing.get_type_hints(cls)["activity"])
        != {VultronActivity}
    }
    assert offenders == {}, (
        "VultronEvent subclasses whose `activity` is not the core "
        f"VultronActivity (HP-04-001): {offenders}"
    )
