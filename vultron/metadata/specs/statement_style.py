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
"""Plain requirement text: one obligation, in short sentences (MS-03).

Two properties of a ``statement:`` can be read off its text:

- **Compound** (MS-03-001): it holds more than one RFC 2119 keyword. A keyword
  inside backticks is a quoted name, not an obligation (SR-12-010 quotes
  ``SHOULD``), so it is not counted; a negated keyword such as ``MUST NOT`` is
  one (:mod:`vultron.metadata.rfc2119`).
- **Long** (MS-03-003): one of its sentences is over
  :data:`SENTENCE_WORD_LIMIT` words. A code span counts as one word.

The corpus has a backlog of both, so neither fails ``spec-lint`` corpus-wide.
``spec-lint --changed-since REF`` checks each requirement whose ``statement:``
the branch added or changed (MS-03-007): a compound one is an error, a long
sentence a warning. A change to any other field leaves the check alone, so a
rationale backfill or a link audit is not forced to split what it touches. A
PR-only growth guard under ``test/architecture/`` holds the same rule in CI
(:func:`unexcused_compound_statements`).
``spec-lint --list-compound`` lists the whole backlog by spec file.

A requirement that must keep two keywords carries
``lint_suppress: [compound_statement]`` with the reason in a YAML comment
(:func:`~vultron.metadata.specs.yaml_items.suppression_reason`). A suppression
with no reason does not count.

Requirements: specs/meta-specifications.yaml MS-03-001, MS-03-003, MS-03-007.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from vultron.metadata.rfc2119 import keywords_in, strip_code_spans
from vultron.metadata.specs.registry import SpecRegistry, load_registry
from vultron.metadata.specs.schema import (
    BehavioralSpec,
    LintWarningCode,
    StatementSpec,
)
from vultron.metadata.specs.yaml_items import (
    SpecItem,
    iter_blocks,
    suppression_reason,
)

SENTENCE_WORD_LIMIT = 25
"""The most words one sentence of a ``statement:`` should hold (MS-03-003)."""

_CODE = LintWarningCode.COMPOUND_STATEMENT

Spec = BehavioralSpec | StatementSpec

#: A sentence ends at ``.``, ``!`` or ``?`` before a capital or an opening
#: mark.
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\"'])")
#: Abbreviations whose final dot ends no sentence, even before a capital.
_ABBREVIATION_RE = re.compile(
    r"(?<![\w.])(?:e\.g|i\.e|etc|vs|cf|U\.S|No|Fig|Sec)\.(?=\s)"
)
_WORD_RE = re.compile(r"\w")
_PREVIEW_WORDS = 8


@dataclass(frozen=True)
class LongSentence:
    """One sentence of a statement over :data:`SENTENCE_WORD_LIMIT` words.

    Attributes:
        number: The sentence's position in the statement, from 1.
        words: How many words it holds.
        opening: Its first few words, so the author can find it.
    """

    number: int
    words: int
    opening: str


def is_compound(statement: str) -> bool:
    """Whether *statement* holds more than one unquoted RFC 2119 keyword."""
    return len(keywords_in(statement)) > 1


def long_sentences(
    statement: str, limit: int = SENTENCE_WORD_LIMIT
) -> list[LongSentence]:
    """The sentences of *statement* with more than *limit* words."""
    # A code span is one word, and its dots must not end a sentence; nor
    # does an abbreviation's.
    prose = strip_code_spans(statement, "code")
    prose = _ABBREVIATION_RE.sub(lambda m: m.group(0).replace(".", ""), prose)
    found: list[LongSentence] = []
    for number, sentence in enumerate(
        _SENTENCE_END_RE.split(prose.strip()), start=1
    ):
        words = [w for w in sentence.split() if _WORD_RE.search(w)]
        if len(words) > limit:
            opening = " ".join(sentence.split()[:_PREVIEW_WORDS])
            found.append(LongSentence(number, len(words), opening))
    return found


def spec_items(spec_dir: Path) -> dict[str, tuple[Path, SpecItem]]:
    """Each requirement ID in *spec_dir* with its file and raw YAML lines."""
    items: dict[str, tuple[Path, SpecItem]] = {}
    for path in sorted(spec_dir.glob("*.yaml")):
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        for block in iter_blocks(lines):
            if isinstance(block, SpecItem):
                items[block.spec_id] = (path, block)
    return items


def _is_suppressed(spec: Spec) -> bool:
    return _CODE in set(spec.lint_suppress or [])


def _excused(
    spec_id: str, spec: Spec, items: Mapping[str, tuple[Path, SpecItem]]
) -> bool:
    """Whether *spec* suppresses the check and gives its reason."""
    entry = items.get(spec_id)
    return (
        _is_suppressed(spec)
        and entry is not None
        and suppression_reason(entry[1], _CODE) is not None
    )


def _compound_problem(
    spec_id: str,
    registry: SpecRegistry,
    items: Mapping[str, tuple[Path, SpecItem]],
) -> str | None:
    """The error for a compound *spec_id*, or ``None`` when it may stand."""
    spec = registry.all_specs[spec_id]
    statement = spec.statement
    if not is_compound(statement):
        return None
    if _excused(spec_id, spec, items):
        return None
    if _is_suppressed(spec):
        return (
            f"{spec_id}: lint_suppress: [{_CODE}] gives no reason. Write the "
            f"list one entry per line and put the reason in a YAML comment on "
            f"the {_CODE} entry or the line before it (MS-03-007)."
        )
    keywords = ", ".join(keywords_in(statement))
    return (
        f"{spec_id}: statement holds more than one RFC 2119 keyword "
        f"({keywords}); a requirement states one obligation (MS-03-001). "
        f"Split it: the original ID keeps the main obligation and each other "
        f"one gets a new ID (notes/spec-authoring-rules.md). A keyword quoted "
        f"in backticks is not counted."
    )


def _long_sentence_warnings(spec_id: str, statement: str) -> list[str]:
    return [
        f"[WARN] {spec_id}: statement sentence {s.number} has {s.words} "
        f"words, over {SENTENCE_WORD_LIMIT} (MS-03-003): "
        f'"{s.opening} ..."'
        for s in long_sentences(statement)
    ]


@dataclass(frozen=True)
class StatementReport:
    """What the statement checks found in the changed requirements."""

    errors: list[str]
    warnings: list[str]


def check_changed_statements(
    registry: SpecRegistry,
    spec_dir: Path,
    changed: Iterable[str],
) -> StatementReport:
    """MS-03 findings for each requirement in *changed* that *registry* holds.

    *changed* names the requirements whose ``statement:`` the branch added or
    changed; *spec_dir* is read for the comments that give a suppression its
    reason.
    """
    ids = sorted(i for i in changed if i in registry.all_specs)
    items = spec_items(spec_dir)
    errors: list[str] = []
    warnings: list[str] = []
    for spec_id in ids:
        problem = _compound_problem(spec_id, registry, items)
        if problem is not None:
            errors.append(problem)
        statement = registry.all_specs[spec_id].statement
        warnings.extend(_long_sentence_warnings(spec_id, statement))
    return StatementReport(errors, warnings)


def unexcused_compound_statements(repo_root: Path) -> frozenset[str]:
    """Each compound statement under *repo_root* with no reasoned suppression.

    One item per requirement, as ``"<ID>: <statement>"``: the PR-only growth
    guard (MS-03-007) compares the merge base with the working tree, so a
    statement added or reworded is new there. Removing a compound statement's
    reasoned suppression makes it new too, though ``--changed-since`` reads
    only statement changes; any other field change leaves its item as it was.
    """
    spec_dir = repo_root / "specs"
    registry = load_registry(spec_dir)
    items = spec_items(spec_dir)
    return frozenset(
        f"{spec_id}: {spec.statement}"
        for spec_id, spec in registry.all_specs.items()
        if is_compound(spec.statement) and not _excused(spec_id, spec, items)
    )


def compound_listing(registry: SpecRegistry, spec_dir: Path) -> list[str]:
    """Every compound requirement in the corpus, grouped by spec file.

    A requirement whose suppression gives a reason is left out: it is not
    backlog. The last line totals the listed requirements.
    """
    items = spec_items(spec_dir)
    by_file: dict[str, list[str]] = {}
    for spec_id, spec in registry.all_specs.items():
        if not is_compound(spec.statement):
            continue
        if _excused(spec_id, spec, items):
            continue
        path = items[spec_id][0].name if spec_id in items else "(unknown)"
        count = len(keywords_in(spec.statement))
        by_file.setdefault(path, []).append(f"  {spec_id}  {count} keywords")
    lines: list[str] = []
    for path in sorted(by_file):
        rows = sorted(by_file[path])
        lines.append(f"{path} ({len(rows)})")
        lines.extend(rows)
    total = sum(len(rows) for rows in by_file.values())
    lines.append(
        f"{total} compound requirement(s) in {len(by_file)} spec file(s) "
        f"(MS-03-001)"
    )
    return lines


__all__ = [
    "SENTENCE_WORD_LIMIT",
    "LongSentence",
    "StatementReport",
    "check_changed_statements",
    "compound_listing",
    "is_compound",
    "long_sentences",
    "spec_items",
    "unexcused_compound_statements",
]
