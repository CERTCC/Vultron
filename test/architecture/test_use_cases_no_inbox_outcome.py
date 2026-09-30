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
"""Architecture ratchet: use cases never speak ``InboxOutcome`` (HP-01-004).

A handler reports what *it* did in its own vocabulary — a ``HandlerResult``
carrying a ``HandlerDisposition`` — and ``DispatchNode`` alone maps that onto
``InboxOutcome.status`` (``processed`` / ``deferred`` / ``rejected``).  A use
case that names ``InboxOutcome`` or ``InboxOutcomeStatus``, or imports from
the inbox-pipeline package, has pulled pipeline vocabulary into the core
use-case layer (ADR-0095).

The scan covers every module under ``vultron/core/use_cases/`` and fails on
any name — bare, attribute, or imported — equal to one of the forbidden class
names.  It does not forbid the inbox *package*: ``received/unknown.py``
legitimately reaches its dead-letter BT tree.  ``KNOWN_VIOLATIONS`` is empty
and the assertion is bidirectional (ARCH-18-001), so the first offender fails.

Spec: HP-01-004 (``specs/handler-protocol.yaml``); UCORG-05-011; ADR-0095.
Corpus: TB-13-001 (shared ``_corpus`` scan, substring prefilter).
"""

import ast

from test.architecture import _corpus

_USE_CASES_ROOT = _corpus.REPO_ROOT / "vultron" / "core" / "use_cases"

_FORBIDDEN_NAMES = frozenset({"InboxOutcome", "InboxOutcomeStatus"})

#: Substring prefilter (TB-13-002).
_FRAGMENTS = ("InboxOutcome",)


def _names_inbox_outcome(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id in _FORBIDDEN_NAMES
    if isinstance(node, ast.Attribute):
        return node.attr in _FORBIDDEN_NAMES
    if isinstance(node, ast.ImportFrom):
        return any(alias.name in _FORBIDDEN_NAMES for alias in node.names)
    return False


def _inbox_outcome_sites(tree: ast.AST) -> list[str]:
    """Return one ``"line N: <reason>"`` string per offending node in *tree*."""
    sites: list[str] = []
    for node in ast.walk(tree):
        if _names_inbox_outcome(node):
            sites.append(
                f"line {_corpus.node_line(node)}: names InboxOutcome vocabulary"
            )
    return sites


def _collect_violations() -> dict[str, list[str]]:
    violations: dict[str, list[str]] = {}
    for py_file, tree in _corpus.files_mentioning(
        *_FRAGMENTS, under=_USE_CASES_ROOT
    ):
        sites = _inbox_outcome_sites(tree)
        if sites:
            rel = py_file.relative_to(_corpus.REPO_ROOT).as_posix()
            violations[rel] = sites
    return violations


KNOWN_VIOLATIONS: frozenset[str] = frozenset()


def test_use_cases_do_not_reference_inbox_outcome() -> None:
    """HP-01-004: no use case names ``InboxOutcome`` or ``InboxOutcomeStatus``.

    See module docstring for the ratchet strategy.
    """
    # Guard against a vacuous pass: the root must actually be in the corpus.
    assert (
        next(_corpus.all_sources(under=_USE_CASES_ROOT), None) is not None
    ), f"no Python sources found under {_USE_CASES_ROOT}"

    found = _collect_violations()
    actual = frozenset(found)
    new_violations = actual - KNOWN_VIOLATIONS
    resolved = KNOWN_VIOLATIONS - actual

    diff_lines: list[str] = []
    if new_violations:
        diff_lines.append(
            "NEW violations (a use case reports a HandlerDisposition; only"
            " DispatchNode maps it onto InboxOutcome — HP-01-004):"
        )
        for path in sorted(new_violations):
            diff_lines.append(f"  + {path}")
            diff_lines.extend(f"      {site}" for site in found[path])
    if resolved:
        diff_lines.append(
            "RESOLVED violations (remove these entries from KNOWN_VIOLATIONS):"
        )
        diff_lines.extend(f"  - {v}" for v in sorted(resolved))

    assert actual == KNOWN_VIOLATIONS, "\n\n" + "\n".join(diff_lines)


# ---------------------------------------------------------------------------
# Synthetic detector-validation tests
# ---------------------------------------------------------------------------


def _sites(source: str) -> list[str]:
    return _inbox_outcome_sites(_corpus.parse_inline(source))


def test_detector_flags_an_inbox_outcome_import() -> None:
    [site] = _sites(
        "from vultron.core.behaviors.inbox.models import InboxOutcome\n"
    )
    assert "InboxOutcome" in site


def test_detector_ignores_the_dead_letter_tree_import() -> None:
    """The inbox *package* is not forbidden — only the outcome vocabulary."""
    assert (
        _sites(
            "from vultron.core.behaviors.inbox.dead_letter_tree import (\n"
            "    create_store_dead_letter_tree,\n"
            ")\n"
        )
        == []
    )


def test_detector_flags_a_bare_inbox_outcome_name() -> None:
    [site] = _sites(
        "def execute(self):\n    return InboxOutcome(status='processed')\n"
    )
    assert "InboxOutcome" in site


def test_detector_flags_an_attribute_inbox_outcome_status() -> None:
    [site] = _sites("status = models.InboxOutcomeStatus.REJECTED\n")
    assert "InboxOutcome" in site


def test_detector_ignores_handler_result_vocabulary() -> None:
    assert (
        _sites(
            "from vultron.core.models.use_case_result import HandlerResult\n"
            "def execute(self) -> HandlerResult:\n"
            "    return HandlerResult.deferred('awaiting predecessor')\n"
        )
        == []
    )
