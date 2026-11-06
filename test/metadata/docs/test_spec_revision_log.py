"""The Protocol Specification's status block names its newest draft (#5914).

The status block (``docs/reference/vultron-spec/_status.md``), shown on the
specification's index and on its single-page edition, states the draft label,
the version identifier and the date. The revision log
(``docs/reference/vultron-spec/revision-log.md``) records each draft, newest
first. The two state the same three facts about the current draft, so a new
draft entry that leaves the status block behind would publish a wrong citation.
These tests hold the status block to the newest entry, and each entry to the
``draft-N`` identifier scheme the log defines.
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

_DATE = r"\d{4}-\d{2}-\d{2}"
_STATUS_TITLE = re.compile(r'^!!! note "Status: Draft (\d+)"$', re.MULTILINE)
_STATUS_ROW = re.compile(
    rf"^\s*\| Draft \| `(draft-\d+)` \| ({_DATE}) \|$", re.MULTILINE
)
_ENTRY_HEADING = re.compile(r"^## Draft (\d+)$", re.MULTILINE)
_ENTRY_VERSION = re.compile(
    r"^- \*\*Version:\*\* `(draft-\d+)`$", re.MULTILINE
)
_ENTRY_DATE = re.compile(rf"^- \*\*Date:\*\* ({_DATE})$", re.MULTILINE)


@dataclass(frozen=True)
class Draft:
    number: int
    version: str
    date: str


def _one(pattern: re.Pattern[str], text: str, where: str) -> re.Match[str]:
    matches = list(pattern.finditer(text))
    assert len(matches) == 1, (
        f"{where}: expected one match of {pattern.pattern!r}"
    )
    return matches[0]


def _status() -> Draft:
    text = STATUS.read_text(encoding="utf-8")
    row = _one(_STATUS_ROW, text, str(STATUS))
    title = _one(_STATUS_TITLE, text, str(STATUS))
    return Draft(int(title.group(1)), row.group(1), row.group(2))


def _entries() -> list[Draft]:
    text = REVISION_LOG.read_text(encoding="utf-8")
    headings = list(_ENTRY_HEADING.finditer(text))
    assert headings, f"{REVISION_LOG}: no '## Draft N' entry"
    entries = []
    for i, heading in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        body = text[heading.end() : end]
        where = f"{REVISION_LOG} § Draft {heading.group(1)}"
        entries.append(
            Draft(
                int(heading.group(1)),
                _one(_ENTRY_VERSION, body, where).group(1),
                _one(_ENTRY_DATE, body, where).group(1),
            )
        )
    return entries


def test_status_block_matches_newest_revision_log_entry() -> None:
    assert _status() == _entries()[0]


def test_status_block_title_names_its_version() -> None:
    status = _status()
    assert status.version == f"draft-{status.number}"


@pytest.mark.parametrize("entry", _entries(), ids=lambda e: e.version)
def test_entry_version_follows_draft_n_scheme(entry: Draft) -> None:
    assert entry.version == f"draft-{entry.number}"


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
