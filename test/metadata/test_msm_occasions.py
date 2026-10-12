"""Tests for the occasion table generator and its loader (ADR-0128, #4430)."""

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

import posixpath
import re
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from vultron.core.models.events.base import MessageSemantics, VultronEvent
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.cs import CS_vf
from vultron.core.states.em import EM
from vultron.metadata.base import excluded_docs_spec, mkdocs_config
from vultron.metadata.file_loading import MetadataLoadError
from vultron.metadata.msm import occasions as gen
from vultron.metadata.msm._mapping import (
    OCCASION_TABLE_PATH,
    MappingStatus,
    OccasionTable,
    distinguished_by,
    load_occasion_table,
    section_heading,
)
from vultron.semantic_registry import SEMANTIC_REGISTRY
from vultron.semantic_registry._entry import SemanticEntry
from vultron.semantic_registry._occasion import (
    FieldValue,
    MessagePage,
    Occasion,
    ProtocolShorthand,
    StateContext,
)

_ROOT = Path(__file__).parents[2]
_DOCS = _ROOT / "docs"
_FRAGMENTS = _ROOT / gen.FRAGMENT_DIR
_LINK = re.compile(r"\]\(([^)\s]+)\)")


def _occasion(**overrides: Any) -> Occasion:
    fields: dict[str, Any] = {
        "when": "a stub situation arises",
        "anchor": "stub-situation",
        "heading": "Stub situation",
        "description": "Stands in for a real occasion.",
        "example": "stub_example",
    }
    fields.update(overrides)
    return Occasion(**fields)


class _StubEvent(VultronEvent):
    """Minimal event class for derivation tests."""


def _entry(
    *occasions: Occasion,
    semantics: MessageSemantics = MessageSemantics.CREATE_NOTE,
) -> SemanticEntry:
    return SemanticEntry(
        semantics=semantics,
        pattern=None,
        event_class=_StubEvent,
        use_case_class=object,
        phrase="{actor} did a thing",
        occasions=occasions,
        page=MessagePage.GENERAL,
    )


@pytest.fixture(scope="module")
def table() -> OccasionTable:
    return gen.derive_table(SEMANTIC_REGISTRY, _ROOT)


def _rows(table: OccasionTable) -> dict[str, Any]:
    return {
        row.anchor: (group, row)
        for group in table.groups
        for row in group.occasions
    }


# ---------------------------------------------------------------------------
# The committed artifacts (MSM-06-001).
# ---------------------------------------------------------------------------


@pytest.mark.spec("MSM-06-001")
def test_committed_occasion_artifacts_are_in_sync():
    """The CI backstop for the ``msm-occasions-sync`` pre-commit hook."""
    found = gen.drift(_ROOT)
    assert found == gen.Drift(stale=(), unexpected=()), (
        f"run '{gen.WRITE_COMMAND}': {found}"
    )


def test_yaml_path_is_the_loader_default():
    assert (_ROOT / gen.YAML_PATH).resolve() == OCCASION_TABLE_PATH.resolve()


@pytest.mark.spec("MSM-06-001")
def test_committed_yaml_loads_and_equals_a_fresh_derivation(table):
    assert load_occasion_table() == table


def test_committed_yaml_carries_its_format_version():
    data = yaml.safe_load(OCCASION_TABLE_PATH.read_text(encoding="utf-8"))
    assert data["format_version"] == 1


@pytest.mark.spec("MSM-08-001")
def test_every_occasion_has_one_row_and_one_section(table):
    declared = [
        o.anchor
        for e in SEMANTIC_REGISTRY
        if e.page is not None
        for o in e.occasions
    ]
    assert sorted(_rows(table)) == sorted(declared)
    sections = {p.stem for p in (_FRAGMENTS / "sections").glob("*.md")}
    assert sections == set(declared)


def test_fragments_are_excluded_from_the_build():
    """Built alone, a table's links would be checked against the wrong page."""
    spec = excluded_docs_spec(mkdocs_config(_ROOT))
    fragments = sorted(_FRAGMENTS.rglob("*.md"))
    assert fragments
    for path in fragments:
        assert spec.match_file(path.relative_to(_DOCS).as_posix())


def test_every_fragment_opens_with_the_generated_marker():
    for path in _FRAGMENTS.rglob("*.md"):
        first = path.read_text(encoding="utf-8").splitlines()[0]
        assert first == gen.FRAGMENT_MARKER, path


# ---------------------------------------------------------------------------
# --check and --write.
# ---------------------------------------------------------------------------


def _scratch_root(tmp_path: Path) -> Path:
    """A root carrying the how-to pages the sections are titled from."""
    howto = "docs/howto/activitypub/activities"
    shutil.copytree(_ROOT / howto, tmp_path / howto)
    return tmp_path


def test_write_then_check_round_trips(tmp_path, monkeypatch, capsys):
    root = _scratch_root(tmp_path)
    monkeypatch.setattr(gen, "repo_root", lambda *_a: root)

    gen.main(["--write"])
    gen.main(["--check"])

    assert "in sync" in capsys.readouterr().out
    assert (root / gen.YAML_PATH).is_file()


def test_check_fails_on_a_hand_edited_fragment(tmp_path, monkeypatch, capsys):
    root = _scratch_root(tmp_path)
    monkeypatch.setattr(gen, "repo_root", lambda *_a: root)
    gen.write_artifacts(root)
    edited = root / gen.FRAGMENT_DIR / "lookup-cs.md"
    edited.write_text(
        edited.read_text(encoding="utf-8") + "hand edit\n", encoding="utf-8"
    )

    with pytest.raises(SystemExit) as exc:
        gen.main(["--check"])

    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert f"{gen.FRAGMENT_DIR}/lookup-cs.md is stale" in err
    assert gen.WRITE_COMMAND in err


def test_check_fails_on_an_orphaned_fragment_and_write_deletes_it(tmp_path):
    root = _scratch_root(tmp_path)
    gen.write_artifacts(root)
    orphan = root / gen.FRAGMENT_DIR / "sections" / "retired-occasion.md"
    orphan.write_text("stale\n", encoding="utf-8")
    rel = orphan.relative_to(root).as_posix()

    assert gen.drift(root).unexpected == (rel,)
    assert rel in gen.write_artifacts(root)
    assert not orphan.exists()
    assert gen.drift(root) == gen.Drift(stale=(), unexpected=())


def test_a_non_markdown_file_is_not_an_orphan(tmp_path):
    """``--write`` deletes orphaned fragments; it must not delete editor or
    OS droppings such as ``.DS_Store`` that are no fragment at all."""
    root = _scratch_root(tmp_path)
    gen.write_artifacts(root)
    stray = root / gen.FRAGMENT_DIR / ".DS_Store"
    stray.write_bytes(b"\x00")

    assert gen.drift(root) == gen.Drift(stale=(), unexpected=())
    gen.write_artifacts(root)
    assert stray.exists()


def test_check_reports_a_malformed_yaml_with_its_position(
    tmp_path, monkeypatch, capsys
):
    root = _scratch_root(tmp_path)
    monkeypatch.setattr(gen, "repo_root", lambda *_a: root)
    gen.write_artifacts(root)
    (root / gen.YAML_PATH).write_text(
        "format_version: 1\ngroups: [\n", encoding="utf-8"
    )

    with pytest.raises(SystemExit):
        gen.main(["--check"])

    assert re.search(
        rf"{re.escape(gen.YAML_PATH)}:\d+:\d+ — YAML parse error",
        capsys.readouterr().err,
    )


# ---------------------------------------------------------------------------
# The loader (MS-17).
# ---------------------------------------------------------------------------


@pytest.mark.spec("MS-17-001")
@pytest.mark.spec("MS-17-002")
def test_loader_names_path_line_and_column_of_a_parse_error(tmp_path):
    path = tmp_path / "occasions.yaml"
    path.write_text("format_version: 1\ngroups: [\n  - a: b: c\n")

    with pytest.raises(MetadataLoadError) as exc:
        load_occasion_table(path, root=tmp_path)

    assert exc.value.path == "occasions.yaml"
    assert exc.value.line is not None and exc.value.column is not None
    assert str(exc.value).startswith(
        f"occasions.yaml:{exc.value.line}:{exc.value.column} — "
    )


@pytest.mark.spec("MS-17-001")
def test_loader_names_line_and_column_of_a_fault_deep_in_the_table(
    tmp_path, table
):
    data = _table_data(table)
    data["groups"][2]["occasions"][3]["status"] = "sideways"
    path = tmp_path / "occasions.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    lines = path.read_text().splitlines()

    with pytest.raises(MetadataLoadError) as exc:
        load_occasion_table(path, root=tmp_path)

    assert exc.value.line is not None and exc.value.column is not None
    assert lines[exc.value.line - 1][exc.value.column - 1 :].startswith(
        "status: sideways"
    )
    assert str(exc.value).startswith(
        f"occasions.yaml:{exc.value.line}:{exc.value.column} — "
    )


@pytest.mark.spec("MS-17-001")
def test_loader_names_the_key_line_of_a_schema_error(tmp_path):
    path = tmp_path / "occasions.yaml"
    path.write_text("# header\nformat_version: 2\ngroups: []\n")

    with pytest.raises(MetadataLoadError) as exc:
        load_occasion_table(path, root=tmp_path)

    assert exc.value.line == 2
    assert "format_version" in exc.value.detail


def _table_data(table: OccasionTable) -> dict[str, Any]:
    return table.model_dump(mode="json", exclude_none=True)


@pytest.mark.spec("MSM-08-004")
def test_loader_refuses_a_duplicate_anchor(tmp_path, table):
    data = _table_data(table)
    rows = data["groups"][0]["occasions"]
    rows[1]["anchor"] = rows[0]["anchor"]
    path = tmp_path / "occasions.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False))

    with pytest.raises(MetadataLoadError, match="is used 2 times"):
        load_occasion_table(path, root=tmp_path)


def test_loader_refuses_a_lifecycle_group_after_the_mechanics(tmp_path, table):
    data = _table_data(table)
    data["groups"].append(data["groups"].pop(0))
    path = tmp_path / "occasions.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False))

    with pytest.raises(MetadataLoadError, match="lifecycle group follows"):
        load_occasion_table(path, root=tmp_path)


def test_loader_refuses_an_unknown_key(tmp_path, table):
    data = _table_data(table)
    data["groups"][0]["occasions"][0]["send_to"] = "the case manager"
    path = tmp_path / "occasions.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False))

    with pytest.raises(MetadataLoadError, match="send_to"):
        load_occasion_table(path, root=tmp_path)


# ---------------------------------------------------------------------------
# Groups (AC-1).
# ---------------------------------------------------------------------------


def test_table_groups_name_every_page_once():
    pages = [group.page for group in gen.TABLE_GROUPS]
    assert sorted(pages) == sorted(MessagePage)


def test_groups_follow_the_lifecycle_then_the_mechanics(table):
    assert [g.page for g in table.groups] == [
        MessagePage.RM,
        MessagePage.CASE_PROPOSAL,
        MessagePage.CASE_MANAGEMENT,
        MessagePage.EM,
        MessagePage.CS,
        MessagePage.GENERAL,
        MessagePage.FAULTS_AND_ACKNOWLEDGEMENTS,
        MessagePage.LEDGER_REPLICATION,
    ]
    assert [g.mechanics for g in table.groups] == [False] * 6 + [True] * 2


def test_rows_follow_registry_order_within_a_group(table):
    for group in table.groups:
        expected = [
            o.anchor
            for e in SEMANTIC_REGISTRY
            if e.page is group.page
            for o in e.occasions
        ]
        assert [row.anchor for row in group.occasions] == expected


def test_derive_refuses_a_page_in_no_group(monkeypatch):
    monkeypatch.setattr(gen, "TABLE_GROUPS", gen.TABLE_GROUPS[1:])
    with pytest.raises(ValueError, match="rm"):
        gen.derive_table(SEMANTIC_REGISTRY, _ROOT)


# ---------------------------------------------------------------------------
# Headings and link text (MSM-08-008, DF-09-010).
# ---------------------------------------------------------------------------


@pytest.mark.spec("MSM-08-008")
def test_own_shorthand_is_headed_by_formal_name_and_shorthand(table):
    _, row = _rows(table)["fix-readiness"]
    assert row.heading == "Fix Readiness (CF)"


@pytest.mark.spec("MSM-08-008")
@pytest.mark.spec("DF-09-010")
@pytest.mark.parametrize(
    "anchor",
    [
        "report-valid",
        "report-invalid",
        "report-closed",
        "accept-full-case-invite",
        "tentatively-reject-full-case-invite",
        "reject-full-case-invite",
        "add-note-to-case",
        "suggest-actor-to-case",
    ],
)
def test_expansion_is_headed_without_its_shorthand(table, anchor):
    """RV, RI, RC and GI expand, so a heading stands in (maintainer, #4430)."""
    _, row = _rows(table)[anchor]
    assert row.shorthand is not None
    assert row.status is MappingStatus.EXPANSION
    assert f"({row.shorthand.value})" not in row.heading
    assert row.shorthand.formal_name not in row.heading


@pytest.mark.spec("MSM-08-008")
def test_no_shorthand_is_headed_by_its_declared_heading(table):
    _, row = _rows(table)["create-case"]
    assert row.shorthand is None
    assert row.heading == "Create case"


@pytest.mark.spec("MSM-08-008")
def test_shared_shorthand_without_a_heading_fails():
    first = _occasion(heading=None, shorthand=ProtocolShorthand.GI)
    second = _occasion(anchor="other", shorthand=ProtocolShorthand.GI)
    registry = [
        _entry(first),
        _entry(second, semantics=MessageSemantics.ADD_NOTE_TO_CASE),
    ]
    with pytest.raises(ValueError, match="needs a plain-English heading"):
        section_heading(first, registry)


@pytest.mark.spec("MSM-08-008")
def test_own_shorthand_with_a_heading_fails():
    occasion = _occasion(shorthand=ProtocolShorthand.CF)
    with pytest.raises(ValueError, match="would render nowhere"):
        section_heading(occasion, [_entry(occasion)])


def test_distinguished_by_renders_a_field_value():
    occasion = _occasion(
        distinguisher=FieldValue(
            object_type=ParticipantStatus, field="vf_state", value=CS_vf.VF
        )
    )
    assert distinguished_by(occasion) == "`vf_state` = `VF`"


def test_distinguished_by_renders_a_state_context():
    occasion = _occasion(
        distinguisher=StateContext(machine=EM, states=(EM.NONE, EM.PROPOSED))
    )
    assert distinguished_by(occasion) == "EM state `NONE` or `PROPOSED`"


def test_distinguished_by_is_none_without_a_distinguisher():
    assert distinguished_by(_occasion()) is None


# ---------------------------------------------------------------------------
# Rendered fragments (AC-1, AC-4, AC-5).
# ---------------------------------------------------------------------------


def test_slice_has_the_lookup_columns(table):
    lines = gen.render_slice(table.groups[0]).splitlines()
    assert (
        lines[0] == "| When… | Send | Sent by | Distinguished by | Details |"
    )
    assert len(lines) == 2 + len(table.groups[0].occasions)


@pytest.mark.spec("MSM-08-005")
@pytest.mark.spec("MSM-08-008")
def test_fix_readiness_row_reads_as_specified(table):
    group = next(g for g in table.groups if g.page is MessagePage.CS)
    row = next(
        line
        for line in gen.render_slice(group).splitlines()
        if "fix-readiness" in line
    )
    assert row == (
        "| a Vendor has a fix ready"
        " | `Add(ParticipantStatus)[target=CaseParticipant]`"
        " | an active participant (usually: vendor)"
        " | `vf_state` = `VF`"
        " | [Fix Readiness (CF)](../cs.md#fix-readiness) |"
    )


def test_whole_table_is_every_slice_under_its_group_title(table):
    whole = gen.render_whole(table)
    for group in table.groups:
        assert f"## {group.title}\n\n{gen.render_slice(group)}" in whole


def test_a_pipe_in_the_send_cell_neither_splits_the_cell_nor_shows():
    cell = gen._code_cell("Create(Event)[context=A|B]")
    assert cell == "<code>Create(Event)&#91;context=A&#124;B&#93;</code>"
    assert gen._code_cell("Offer(X)") == "`Offer(X)`"


def test_section_is_anchored_by_the_occasion_id(table):
    _, row = _rows(table)["fix-readiness"]
    section = gen.render_section(row)
    assert section.startswith("## Fix Readiness (CF) { #fix-readiness }\n")
    assert "print(json2md(add_fix_readiness_to_participant()))" in section


def _resolve(fragment: Path, target: str) -> tuple[Path, str]:
    path, _, anchor = target.partition("#")
    joined = posixpath.normpath(
        posixpath.join(fragment.parent.as_posix(), path)
    )
    return Path(joined), anchor


@pytest.mark.spec("DF-09-007")
def test_every_fragment_link_is_a_relative_md_link_that_resolves():
    """Relative ``.md`` links, which include-markdown and MkDocs rewrite."""
    checked = 0
    for fragment in _FRAGMENTS.rglob("*.md"):
        for target in _LINK.findall(fragment.read_text(encoding="utf-8")):
            assert not target.startswith(("/", "http")), (fragment, target)
            path, _ = _resolve(fragment, target)
            assert path.suffix == ".md", (fragment, target)
            assert path.is_file(), (fragment, target)
            assert _DOCS in path.parents, (fragment, target)
            checked += 1
    assert checked > 0


def _slugs(page: Path) -> set[str]:
    return {
        re.sub(r"[^a-z0-9]+", "-", m.group(1).lower()).strip("-")
        for m in re.finditer(r"^#+ (.+)$", page.read_text("utf-8"), re.M)
    }


def test_formal_definition_links_name_an_existing_section():
    messages = _DOCS / "reference/formal_protocol/messages.md"
    anchors = _slugs(messages)
    for shorthand in ProtocolShorthand:
        link = gen.formal_link(shorthand, "")
        assert link.split("#", 1)[1].rstrip(")") in anchors


def test_table_links_target_the_group_page_and_a_generated_section(table):
    """Each Details link in a committed slice names its group's page and the
    anchor of one of that group's rows, whose section fragment exists.

    Whether the anchor resolves on the page itself waits for #4431, which
    includes the sections there.
    """
    for group in table.groups:
        slice_path = _FRAGMENTS / f"lookup-{group.page.value}.md"
        anchors = {row.anchor for row in group.occasions}
        page = _DOCS / f"reference/messages/{group.page.value}.md"
        seen = set()
        for target in _LINK.findall(slice_path.read_text(encoding="utf-8")):
            path, anchor = _resolve(slice_path, target)
            if path.parent != page.parent:
                continue  # not a Details link
            assert path == page and page.is_file(), (slice_path, target)
            assert anchor in anchors, (slice_path, target)
            assert (_FRAGMENTS / "sections" / f"{anchor}.md").is_file()
            seen.add(anchor)
        assert seen == anchors, slice_path


@pytest.mark.spec("MSM-06-001")
@pytest.mark.xfail(
    strict=True,
    reason="#4431 moves the message pages onto the generated fragments",
)
def test_no_message_page_renders_its_table_at_build_time():
    """The end state MSM-06-001 requires: no page under
    ``docs/reference/messages/`` prints a mapping table from an exec block.
    #4431 must remove this marker when it rebuilds the pages."""
    rendering = sorted(
        page.name
        for page in (_DOCS / "reference/messages").glob("*.md")
        if "render_page(" in page.read_text(encoding="utf-8")
    )
    assert rendering == []


def test_no_fragment_is_exempt_from_lint_docs():
    """``lint-docs`` skips ``*table*.md`` as generated; these carry prose."""
    for path in _FRAGMENTS.rglob("*.md"):
        assert "table" not in path.name, path


def test_tables_carry_no_exec_block():
    """A table is mostly links, which an exec block would hide from MkDocs."""
    for path in _FRAGMENTS.glob("lookup*.md"):
        assert "exec=" not in path.read_text(encoding="utf-8"), path
