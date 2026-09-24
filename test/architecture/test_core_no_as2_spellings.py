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
"""Architecture boundary test: core code must not type an AS2 spelling.

ADR-0099 detail 2: core field names follow Python convention and the AS2
spelling lives in a Pydantic alias.  **Core code MUST NOT type an AS2
spelling** — it names ``in_reply_to``, never ``inReplyTo``.

Spec: ARCH-20-001; ADR-0099 detail 2.  Issue #3485 AC-1 and AC-4.

Declaration versus use
----------------------
The whole difficulty is that AS2 spellings *must* appear in core — 234 core
fields carry an AS2 alias, and that is the mechanism ADR-0099 chose.  A regex
over the file would flag every one of those and be useless.  So this ratchet
distinguishes **declaring** a spelling from **using** one, by position in the
AST rather than by spelling:

Declaration — allowed:
  the value of an ``alias=`` / ``validation_alias=`` / ``serialization_alias=``
  keyword argument, including a spelling nested inside an ``AliasChoices(...)``
  or ``AliasPath(...)`` in that position.  This is the ADR's mechanism.

Prose — allowed:
  a module, class or function docstring.  Docstrings describe the wire shape to
  a reader; they are not logic.  Note that a spelling merely *embedded* in a
  longer message (``f"{event_type}: payloadSnapshot.actor must be …"``) is not
  flagged either, because the literal as a whole is not a spelling — only a
  literal whose entire value is one AS2 field name is.  A dict key, a
  comparison operand and a translation-table entry are always exactly that, so
  nothing real escapes.

Use — forbidden:
  everything else.  A subscript, a ``.get()`` argument, a set or tuple of keys,
  a hand-written camelCase-to-snake_case map — anything core *reads or writes*
  by its AS2 name.

Core code that genuinely has to key an AS2-shaped mapping — the ledger payload
snapshot is the real case (CLP-07-001, RSH-05-009) — asks
:mod:`vultron.core.models.wire_keys` for the spelling, which reads it from the
field's own alias or derives it with the same ``to_camel`` generator the models
use.  That keeps the declaration the single source of truth.

Ratchet pattern
---------------
``KNOWN_VIOLATIONS`` documents every site awaiting migration.  The test asserts
``actual == KNOWN_VIOLATIONS``, so adding a violation fails immediately and
fixing one fails until its entry is removed.  It is empty and should stay that
way.
"""

import ast
import re
from pathlib import Path

from test.architecture import _corpus

_CORE_ROOT = _corpus.REPO_ROOT / "vultron" / "core"

#: An identifier-shaped camelCase word: one or more lowercase-initial segments
#: followed by at least one capitalised segment, and nothing else.  Anchored at
#: both ends deliberately — see "Declaration versus use" above.
#:
#: The anchoring also excludes the case-state pattern strings under
#: ``vultron/core/case_states/`` (``"v..P.."``, ``"vfDPx"``): they carry capitals
#: but are not identifiers, so they never match and need no exemption.
_AS2_SPELLING = re.compile(r"^[a-z][a-z0-9]*(?:[A-Z][a-z0-9]*)+$")

#: Keyword arguments whose value declares an AS2 spelling rather than using one.
_ALIAS_KEYWORDS = frozenset(
    {"alias", "validation_alias", "serialization_alias"}
)

# ---------------------------------------------------------------------------
# Known sites awaiting migration.  Entries are ``(repo-relative path, spelling)``
# and every entry MUST carry a comment saying why it cannot be derived from a
# field alias yet.
# ---------------------------------------------------------------------------
KNOWN_VIOLATIONS: frozenset[tuple[str, str]] = frozenset()


def _alias_declaration_literals(tree: ast.AST) -> set[int]:
    """Return ``id()`` of every string literal declaring a Pydantic alias.

    Walks the whole keyword value, so ``AliasChoices("rmState", "rm_state",
    "rm")`` is covered as well as a bare ``serialization_alias="rmState"``.
    """
    declared: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg not in _ALIAS_KEYWORDS:
                continue
            for sub in ast.walk(keyword.value):
                if isinstance(sub, ast.Constant) and isinstance(
                    sub.value, str
                ):
                    declared.add(id(sub))
    return declared


def _docstring_literals(tree: ast.AST) -> set[int]:
    """Return ``id()`` of every module/class/function docstring literal."""
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(
            node,
            (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            continue
        body = getattr(node, "body", [])
        if not body or not isinstance(body[0], ast.Expr):
            continue
        value = body[0].value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            docstrings.add(id(value))
    return docstrings


def _spellings_used(tree: ast.AST) -> set[tuple[int, str]]:
    """Return ``(line, spelling)`` for each AS2 spelling *used* in *tree*."""
    exempt = _alias_declaration_literals(tree) | _docstring_literals(tree)
    used: set[tuple[int, str]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant):
            continue
        if not isinstance(node.value, str):
            continue
        if id(node) in exempt:
            continue
        if _AS2_SPELLING.match(node.value):
            used.add((node.lineno, node.value))
    return used


def _collect_violations() -> frozenset[tuple[str, str]]:
    """Return ``(repo-relative path, spelling)`` for every core-logic AS2 name."""
    violations: set[tuple[str, str]] = set()
    for py_file, tree in _corpus.all_trees(under=_CORE_ROOT):
        rel = py_file.relative_to(_corpus.REPO_ROOT).as_posix()
        for _line, spelling in _spellings_used(tree):
            violations.add((rel, spelling))
    return frozenset(violations)


def test_core_logic_types_no_as2_spelling():
    """No module under vultron/core/ uses an AS2 spelling outside an alias.

    Spec: ADR-0099 detail 2, ARCH-20-001.  Issue #3485 AC-1.

    See the module docstring for how a declaration is told from a use.
    """
    actual = _collect_violations()
    new_violations = actual - KNOWN_VIOLATIONS
    resolved = KNOWN_VIOLATIONS - actual

    diff_lines: list[str] = []
    if new_violations:
        diff_lines.append(
            "NEW AS2 spellings used in core logic (ADR-0099 detail 2 — name the"
            " core field and get the AS2 key from"
            " vultron.core.models.wire_keys):"
        )
        diff_lines.extend(
            f"  + {path}: {spelling!r}"
            for path, spelling in sorted(new_violations)
        )
    if resolved:
        diff_lines.append(
            "RESOLVED (remove these entries from KNOWN_VIOLATIONS):"
        )
        diff_lines.extend(
            f"  - {path}: {spelling!r}" for path, spelling in sorted(resolved)
        )

    assert actual == KNOWN_VIOLATIONS, "\n\n" + "\n".join(diff_lines)


def test_alias_declarations_are_not_flagged():
    """A field declaring an AS2 alias is a declaration, not a violation.

    Guards the discriminator itself: without it the ratchet above could be
    "passing" because it flags nothing at all, or because someone weakened it
    into a whole-file regex that had to exempt every real alias.
    """
    tree = _corpus.parse_inline(
        "from pydantic import AliasChoices, Field\n"
        "class M:\n"
        "    rm = Field(\n"
        "        validation_alias=AliasChoices('rmState', 'rm_state', 'rm'),\n"
        "        serialization_alias='rmState',\n"
        "    )\n"
        "    in_reply_to = Field(alias='inReplyTo')\n"
    )
    assert _spellings_used(tree) == set()


def test_core_logic_use_is_flagged():
    """Each shape the fixed sites had is still caught.

    One case per repaired category: the subscript write, the ``.get()`` read,
    the tuple of keys, the hand-written translation table, and the equality
    comparison.
    """
    tree = _corpus.parse_inline(
        "snapshot['offerId'] = offer_id\n"
        "value = snapshot.get('rmState')\n"
        "keys = ('rmState', 'vfState', 'dState', 'caseStatus')\n"
        "twins = {'rmState': 'rm_state'}\n"
        "flag = key == 'payloadSnapshot'\n"
    )
    assert {spelling for _line, spelling in _spellings_used(tree)} == {
        "offerId",
        "rmState",
        "vfState",
        "dState",
        "caseStatus",
        "payloadSnapshot",
    }


def test_prose_is_not_flagged():
    """A spelling inside a sentence is prose; a bare literal is not.

    The message string is how CLP-07 and RSH-05 diagnostics name the field they
    are complaining about, and rewriting them into snake_case would stop them
    matching the spec they cite.
    """
    tree = _corpus.parse_inline(
        '"""Module docstring naming inReplyTo and payloadSnapshot."""\n'
        "def f(event_type):\n"
        '    """Checks payloadSnapshot.published (CLP-07-011)."""\n'
        "    raise ValueError(\n"
        "        f'{event_type}: payloadSnapshot.actor must be a non-empty URI'\n"
        "    )\n"
    )
    assert _spellings_used(tree) == set()


def test_scan_actually_reaches_core_modules():
    """The corpus walk sees the core tree, so a green result means something."""
    scanned = [path for path, _tree in _corpus.all_trees(under=_CORE_ROOT)]
    assert len(scanned) > 100
    assert Path(_CORE_ROOT / "models" / "participant_status.py") in scanned
