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
"""Ratchet: the Conformance Matrix reference page mirrors spec §12.

``docs/reference/conformance_matrix.md`` lays out the specification's two
conformance dimensions — capability sets (§12.2) and roles (§12.3) — as tables,
plus the named configurations §12.2 tabulates.  The specification is the
authority and the matrix is a view of it, so the page is hand-written but
every set it enumerates is checked here against the fragments that define it:

* the matrix's columns are exactly the ``#### <Name> capability set`` headings
  of ``_capability-sets.md``;
* its rows are exactly the roles tabulated in ``_role-taxonomy.md`` (§12.3.1
  process roles and §12.3.2 protocol authority roles), and the drive table
  names the same roles;
* the named-configurations table is the §12.2 table, cell for cell;
* every role requires Case Observer (§12.2: "Every actor that participates in
  any Vultron case MUST implement it"), and the two authority roles require
  the set that defines them (Case Owner → Case Decision, Case Manager → Case
  Hosting), which are the only *Required* cells outside that column.

A role added to, or renamed in, the specification therefore fails this test
until the matrix follows.  The test also fails if any table it relies on is
missing, so an edit that drops a heading cannot pass by producing nothing to
compare (DF-09-009).
"""

import re
from pathlib import Path

import pytest

from vultron.metadata.markdown_tables import MarkdownTable, iter_tables

REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PAGE = REPO_ROOT / "docs/reference/conformance_matrix.md"
CONFORMANCE_DIR = REPO_ROOT / "docs/reference/vultron-spec/_conformance"
CAPABILITY_SETS_FRAGMENT = CONFORMANCE_DIR / "_capability-sets.md"
ROLE_TAXONOMY_FRAGMENT = CONFORMANCE_DIR / "_role-taxonomy.md"

_CAPABILITY_SET_HEADING = re.compile(r"^#### (?P<name>.+?) capability set\s*$")
_MARKUP = re.compile(r"[*`]|\[([^\]]*)\]\([^)]*\)")

REQUIRED = "Required"
OPTIONAL = "Optional"

#: The capability set every participant implements (§12.2).
FLOOR_SET = "Case Observer"

#: The authority roles and the set that defines each (§12.2).
AUTHORITY_SETS = {
    "Case Owner": "Case Decision",
    "Case Manager": "Case Hosting",
}


def _plain(cell: str) -> str:
    """Strip emphasis, code spans and link syntax so cells compare as text."""
    return _MARKUP.sub(lambda m: m.group(1) or "", cell).strip()


def _table_under(text: str, heading: str, path: Path) -> MarkdownTable:
    """Return the one pipe table under *heading*, failing loudly if absent."""
    tables = [t for t in iter_tables(text) if t.heading == heading]
    assert len(tables) == 1, (
        f"{path}: expected exactly one table under {heading!r}, "
        f"found {len(tables)}"
    )
    return tables[0]


@pytest.fixture(scope="module")
def matrix_text() -> str:
    return MATRIX_PAGE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def spec_capability_sets() -> tuple[str, ...]:
    text = CAPABILITY_SETS_FRAGMENT.read_text(encoding="utf-8")
    names = tuple(
        m.group("name")
        for line in text.splitlines()
        if (m := _CAPABILITY_SET_HEADING.match(line))
    )
    assert names, f"{CAPABILITY_SETS_FRAGMENT}: no capability set headings"
    return names


@pytest.fixture(scope="module")
def spec_roles() -> tuple[str, ...]:
    text = ROLE_TAXONOMY_FRAGMENT.read_text(encoding="utf-8")
    process = _table_under(
        text, "12.3.1 Process Roles", ROLE_TAXONOMY_FRAGMENT
    )
    authority = _table_under(
        text,
        "12.3.2 Protocol Coordination Roles (protocol authority)",
        ROLE_TAXONOMY_FRAGMENT,
    )
    roles = tuple(
        _plain(r) for r in process.column("Role") + authority.column("Role")
    )
    assert roles, f"{ROLE_TAXONOMY_FRAGMENT}: role tables are empty"
    return roles


@pytest.fixture(scope="module")
def matrix_table(matrix_text: str) -> MarkdownTable:
    return _table_under(matrix_text, "Capability sets by role", MATRIX_PAGE)


def test_matrix_columns_are_the_spec_capability_sets(
    matrix_table: MarkdownTable, spec_capability_sets: tuple[str, ...]
) -> None:
    assert matrix_table.columns[0] == "Role"
    assert tuple(_plain(c) for c in matrix_table.columns[1:]) == tuple(
        spec_capability_sets
    )


def test_matrix_rows_are_the_spec_roles(
    matrix_table: MarkdownTable, spec_roles: tuple[str, ...]
) -> None:
    assert tuple(_plain(r) for r in matrix_table.column("Role")) == spec_roles


def test_drive_table_names_the_spec_roles(
    matrix_text: str, spec_roles: tuple[str, ...]
) -> None:
    drive = _table_under(
        matrix_text, "Transitions each role may drive", MATRIX_PAGE
    )
    assert tuple(_plain(r) for r in drive.column("Role")) == spec_roles


def test_every_cell_is_required_or_optional(
    matrix_table: MarkdownTable,
) -> None:
    for row in matrix_table.rows:
        assert len(row) == len(matrix_table.columns), row
        for cell in row[1:]:
            assert _plain(cell) in {REQUIRED, OPTIONAL}, row


def test_every_role_requires_the_floor_set(
    matrix_table: MarkdownTable,
) -> None:
    assert set(_plain(c) for c in matrix_table.column(FLOOR_SET)) == {REQUIRED}


def test_authority_roles_require_their_defining_set_and_nothing_else_does(
    matrix_table: MarkdownTable,
) -> None:
    required_outside_floor: dict[str, set[str]] = {}
    for row in matrix_table.rows:
        role = _plain(row[0])
        for name, cell in zip(matrix_table.columns[1:], row[1:], strict=False):
            if _plain(name) != FLOOR_SET and _plain(cell) == REQUIRED:
                required_outside_floor.setdefault(role, set()).add(
                    _plain(name)
                )
    assert required_outside_floor == {
        role: {capability_set}
        for role, capability_set in AUTHORITY_SETS.items()
    }


def test_named_configurations_match_the_spec_table(matrix_text: str) -> None:
    spec_text = CAPABILITY_SETS_FRAGMENT.read_text(encoding="utf-8")
    spec = _table_under(
        spec_text, "Named configurations", CAPABILITY_SETS_FRAGMENT
    )
    matrix = _table_under(matrix_text, "Named configurations", MATRIX_PAGE)
    assert tuple(_plain(c) for c in matrix.columns) == tuple(
        _plain(c) for c in spec.columns
    )
    assert tuple(
        tuple(_plain(c) for c in row) for row in matrix.rows
    ) == tuple(tuple(_plain(c) for c in row) for row in spec.rows)
    assert spec.rows, "the spec's named-configurations table is empty"
