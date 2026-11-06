"""The Protocol Specification's status block names its newest draft (#5914).

The status block (``docs/reference/vultron-spec/_status.md``), shown on the
specification's index and on its single-page edition, states the draft label,
the version identifier, the status and the date. The revision log
(``docs/reference/vultron-spec/revision-log.md``) records each draft, newest
first, with the same properties. Both state the same facts about the current
draft, so a new draft entry, or a release of the current one, that leaves the
status block behind would publish a wrong citation. These tests hold the status
block to the newest entry, and each entry to the ``draft-N`` identifier scheme
the log defines.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from vultron.metadata.base import repo_root

SPEC_DIR = repo_root() / "docs" / "reference" / "vultron-spec"
STATUS = SPEC_DIR / "_status.md"
REVISION_LOG = SPEC_DIR / "revision-log.md"
SPEC_INDEX = SPEC_DIR / "index.md"
FULL_PAGE = SPEC_DIR / "full.md"

# The H2 sections of the revision log that are not draft entries.
NON_ENTRY_SECTIONS = {"Version identifiers"}

_STATUS_TITLE = re.compile(r'^!!! note "Status: Draft (\d+)"$', re.MULTILINE)
_H2 = re.compile(r"^## (.+)$", re.MULTILINE)
_ENTRY_HEADING = re.compile(r"Draft (\d+)")


def _row(name: str, value: str) -> re.Pattern[str]:
    return re.compile(rf"^\s*\| {name} \| {value} \|$", re.MULTILINE)


_VERSION_ROW = _row("Version", r"`(draft-\d+)`")
_STATUS_ROW = _row("Status", r"(\S[^|]*\S)")
_DATE_ROW = _row("Date", r"(\d{4}-\d{2}-\d{2})")


@dataclass(frozen=True)
class Draft:
    number: int
    version: str
    status: str
    date: str


def _one(pattern: re.Pattern[str], text: str, where: str) -> str:
    matches = list(pattern.finditer(text))
    assert len(matches) == 1, (
        f"{where}: expected one match of {pattern.pattern!r}"
    )
    return matches[0].group(1)


def _properties(number: int, text: str, where: str) -> Draft:
    return Draft(
        number,
        _one(_VERSION_ROW, text, where),
        _one(_STATUS_ROW, text, where),
        _one(_DATE_ROW, text, where),
    )


def _status() -> Draft:
    text = STATUS.read_text(encoding="utf-8")
    number = int(_one(_STATUS_TITLE, text, str(STATUS)))
    return _properties(number, text, str(STATUS))


def _entries() -> list[Draft]:
    text = REVISION_LOG.read_text(encoding="utf-8")
    headings = [
        h for h in _H2.finditer(text) if h.group(1) not in NON_ENTRY_SECTIONS
    ]
    assert headings, f"{REVISION_LOG}: no '## Draft N' entry"
    entries = []
    for i, heading in enumerate(headings):
        title = heading.group(1)
        match = _ENTRY_HEADING.fullmatch(title)
        assert match, (
            f"{REVISION_LOG}: section '## {title}' is neither a draft entry "
            f"('## Draft N') nor one of {sorted(NON_ENTRY_SECTIONS)}"
        )
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        body = text[heading.end() : end]
        entries.append(
            _properties(int(match.group(1)), body, f"{REVISION_LOG} § {title}")
        )
    return entries


def test_status_block_matches_newest_revision_log_entry() -> None:
    assert _status() == _entries()[0]


def test_status_block_title_names_its_version() -> None:
    status = _status()
    assert status.version == f"draft-{status.number}"


def test_status_block_citation_example_names_its_version_and_date() -> None:
    status = _status()
    citation = (
        f"Vultron Protocol Specification, `{status.version}`, {status.date}."
    )
    assert citation in STATUS.read_text(encoding="utf-8")


def test_entry_versions_follow_draft_n_scheme() -> None:
    for entry in _entries():
        assert entry.version == f"draft-{entry.number}", entry


def test_entries_are_newest_first_with_no_gap() -> None:
    numbers = [entry.number for entry in _entries()]
    assert numbers == list(range(len(numbers), 0, -1))


def test_entry_dates_do_not_decrease() -> None:
    dates = [entry.date for entry in reversed(_entries())]
    assert dates == sorted(dates)


@pytest.mark.parametrize("page", [SPEC_INDEX, FULL_PAGE], ids=lambda p: p.name)
def test_page_includes_status_block(page: Path) -> None:
    text = page.read_text(encoding="utf-8")
    assert '{% include-markdown "./_status.md" %}' in text


def test_spec_index_links_revision_log() -> None:
    assert "](revision-log.md)" in SPEC_INDEX.read_text(encoding="utf-8")
