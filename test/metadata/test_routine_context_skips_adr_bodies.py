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

"""Routine task context routes through decision records without their bodies.

ADR-0127 takes decision-record bodies out of routine agent context, and
MS-11-008 makes that enforceable on the skill text itself:

- ``deepen-context`` routes through records by the generated title index
  (``docs/adr/index.md``) and the requirements' ``adr:`` edges
  (``spec-dump --adr``);
- it carries a written list of the skills that read bodies in full, each with
  its reason, and the list names at least the skills the decision names;
- no skill off that list instructs an agent to read a record body, and each
  listed skill that lives in this repository weighs what it reads by the
  shared weighting guidance.

The exception list is read from the skill text, so it has one source: adding a
skill to the table is what lets it read bodies.
"""

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).parents[2]
_SKILLS = _REPO_ROOT / ".agents" / "skills"
_DEEPEN = _SKILLS / "deepen-context" / "SKILL.md"
_WEIGHING = _SKILLS / "shared" / "weighing-decision-records.md"
_WEIGHING_REF = ".agents/skills/shared/weighing-decision-records.md"

_EXCEPTION_HEADING = "#### Skills that read record bodies"

#: The skills ADR-0127 names as keeping full body access: decision auditing,
#: record authoring, the learning workflow, issue planning and pull-request
#: triage. Record authoring is a user-level skill outside this repository.
_REQUIRED_EXCEPTIONS = frozenset(
    {
        "decision-audit",
        "create-architectural-decision-record",
        "learn",
        "plan-issue",
        "pr-triage",
    }
)

#: An instruction to read a record body: a reading verb, then within the same
#: clause a record file path (not the index, the template or the archive), a
#: "full/whole/entire record", or a "record body/file". The scan is whole-file
#: text, so a clause folded across a line break is still found.
BODY_READ_RE = re.compile(
    r"""
    \b(?:read|reads|reading|load|loads|loading|open|opens|study)\b
    [^.:;|]{0,80}?
    (?:
        docs/adr/(?!index\.md|_adr-template\.md|archived/)
      | \b(?:full|whole|entire)\s+(?:ADR|decision[ -]record|record)s?\b
      | \b(?:ADR|decision[ -]record|record)s?\s+(?:bod(?:y|ies)|files?)\b
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def body_read_instructions(text: str) -> list[tuple[int, str]]:
    """Return ``(line, matched text)`` for each record-body read instruction."""
    return [
        (text.count("\n", 0, m.start()) + 1, " ".join(m.group(0).split()))
        for m in BODY_READ_RE.finditer(text)
    ]


def _exception_section(text: str) -> str:
    """The exception-list section of ``deepen-context``, heading to next heading."""
    start = text.index(_EXCEPTION_HEADING)
    rest = text[start + len(_EXCEPTION_HEADING) :]
    end = re.search(r"^#{1,4} ", rest, re.MULTILINE)
    return text[
        start : start
        + len(_EXCEPTION_HEADING)
        + (end.start() if end else len(rest))
    ]


def exception_table(text: str) -> dict[str, str]:
    """Map each skill in the exception table to its stated reason."""
    rows: dict[str, str] = {}
    for line in _exception_section(text).splitlines():
        match = re.match(r"^\|\s*`([\w-]+)`\s*\|\s*(.*?)\s*\|\s*$", line)
        if match:
            rows[match.group(1)] = match.group(2)
    return rows


def _deepen_text() -> str:
    return _DEEPEN.read_text(encoding="utf-8")


def _routine_skill_files(exceptions: set[str]) -> list[Path]:
    """Every skill markdown file outside the excepted skills' directories."""
    return sorted(
        path
        for path in _SKILLS.rglob("*.md")
        if path.relative_to(_SKILLS).parts[0] not in exceptions
    )


@pytest.mark.spec("MS-11-008")
def test_deepen_context_routes_by_title_index_and_adr_edges() -> None:
    text = _deepen_text()
    assert "docs/adr/index.md" in text
    assert "spec-dump --adr" in text
    assert "RECORD_ONLY_EXEMPTIONS" in text


@pytest.mark.spec("MS-11-008")
def test_exception_list_names_each_required_skill_with_a_reason() -> None:
    table = exception_table(_deepen_text())
    missing = sorted(_REQUIRED_EXCEPTIONS - table.keys())
    assert not missing, f"exception list omits {missing}"
    unexplained = sorted(name for name, why in table.items() if len(why) < 20)
    assert not unexplained, f"exception rows give no reason: {unexplained}"


@pytest.mark.spec("MS-11-008")
def test_no_routine_skill_instructs_reading_a_record_body() -> None:
    text = _deepen_text()
    exceptions = set(exception_table(text))
    files = _routine_skill_files(exceptions)
    assert _DEEPEN in files, "deepen-context must itself be scanned"
    hits: list[str] = []
    for path in files:
        body = path.read_text(encoding="utf-8")
        if path == _DEEPEN:
            body = body.replace(_exception_section(body), "")
        hits.extend(
            f"{path.relative_to(_REPO_ROOT)}:{line}: {match}"
            for line, match in body_read_instructions(body)
        )
    assert not hits, (
        "Route through records by title and adr: edge (deepen-context Step "
        "2), or add the skill to its exception list with a reason "
        "(MS-11-008):\n" + "\n".join(hits)
    )


@pytest.mark.spec("MS-11-008")
def test_each_in_repo_exception_skill_weighs_what_it_reads() -> None:
    """The weighting guidance survives wherever bodies are still read."""
    assert _WEIGHING.is_file()
    weighing = _WEIGHING.read_text(encoding="utf-8")
    assert "challengeable" in weighing
    assert "prose hedges" in weighing
    in_repo = sorted(
        name
        for name in exception_table(_deepen_text())
        if (_SKILLS / name).is_dir()
    )
    assert {"decision-audit", "learn", "plan-issue", "pr-triage"} <= set(
        in_repo
    ), "a required exception skill was renamed or removed from the repo"
    unweighed = [
        name
        for name in in_repo
        if _WEIGHING_REF
        not in (_SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    ]
    assert not unweighed, f"exception skills not pointing at {_WEIGHING_REF}"
    assert _WEIGHING_REF in _deepen_text()


@pytest.mark.parametrize(
    "text",
    [
        # The pre-ADR-0127 deepen-context Step 2 instruction.
        "Read the full ADR file for any decision that is in scope",
        "read the full ADR, every spec whose rationale cites it",
        "load the governing specs, relevant plan files, docs/adr/, notes/",
        "Read the ADR body\n for each in-scope decision",
        "open docs/adr/0099-one-object-model.md",
        "study the whole decision record",
    ],
)
def test_detector_catches_each_body_read_shape(text: str) -> None:
    assert body_read_instructions(text), text


@pytest.mark.parametrize(
    "text",
    [
        "Grep the generated sections of `docs/adr/index.md` for the terms.",
        "Read the ADR index (`docs/adr/index.md`) for titles.",
        "verify it follows `docs/adr/_adr-template.md`",
        "Retired ADRs live in `docs/adr/archived/`",
        "PYTHONPATH= uv run spec-dump --adr ADR-0127 --text",
        "read the files it names in Step 1. They state the rule in full.",
    ],
)
def test_detector_passes_routing_instructions(text: str) -> None:
    assert not body_read_instructions(text), text
