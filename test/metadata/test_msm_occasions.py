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

import dataclasses
import posixpath
import re
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml
from markdown.extensions import toc  # type: ignore[import-untyped]

from vultron.core.behaviors.sender_entitlement import (
    AddresseeSide,
    SenderEntitlementKind,
)
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.events.base import MessageSemantics, VultronEvent
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.cs import CS_pxa, CS_vf
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import EmbargoRegisterStatus
from vultron.metadata.base import excluded_docs_spec, mkdocs_config
from vultron.metadata.file_loading import MetadataLoadError
from vultron.metadata.msm import occasions as gen
from vultron.metadata.msm._mapping import (
    OCCASION_TABLE_PATH,
    MappingStatus,
    OccasionTable,
    PageLink,
    distinguished_by,
    load_occasion_table,
    section_heading,
)
from vultron.semantic_registry import SEMANTIC_REGISTRY, lookup_entry
from vultron.semantic_registry._entry import SemanticEntry
from vultron.semantic_registry._occasion import (
    FieldValue,
    HowToGuide,
    MessagePage,
    Occasion,
    ProtocolShorthand,
    SenderStanding,
    StateContext,
)

_ROOT = Path(__file__).parents[2]
_DOCS = _ROOT / "docs"
_FRAGMENTS = _ROOT / gen.FRAGMENT_DIR
_MESSAGES = _FRAGMENTS.parent
#: The fragment directory as the pages' include directives name it.
_FROM_PAGES = _FRAGMENTS.relative_to(_MESSAGES).as_posix()
_LINK = re.compile(r"\]\(([^)\s]+)\)")


def _occasion(**overrides: Any) -> Occasion:
    fields: dict[str, Any] = {
        "when": "a stub situation arises",
        "anchor": "stub-situation",
        "addressee": AddresseeSide.CASE_MANAGER,
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
    semantics: MessageSemantics = MessageSemantics.ADD_NOTE_TO_CASE,
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
    assert data["format_version"] == 3


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
    embeds = {p.stem for p in (_FRAGMENTS / "embeds").glob("*.md")}
    assert embeds == set(declared)


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
    shutil.copy(_ROOT / "mkdocs.yml", tmp_path / "mkdocs.yml")
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
    path.write_text("# header\nformat_version: 4\ngroups: []\n")

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
    data["groups"][0]["occasions"][0]["send_cc"] = "the case manager"
    path = tmp_path / "occasions.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False))

    with pytest.raises(MetadataLoadError, match="send_cc"):
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
        _entry(second, semantics=MessageSemantics.REMOVE_NOTE_FROM_CASE),
    ]
    with pytest.raises(ValueError, match="needs a plain-English heading"):
        section_heading(first, registry)


@pytest.mark.spec("MSM-08-008")
def test_own_shorthand_with_a_heading_fails():
    occasion = _occasion(shorthand=ProtocolShorthand.CF)
    with pytest.raises(ValueError, match="would render nowhere"):
        section_heading(occasion, [_entry(occasion)])


def _rendered(occasion: Occasion) -> str | None:
    """Render *occasion*'s distinguisher on a stub entry carrying it."""
    return distinguished_by(_entry(occasion), occasion)


def test_distinguished_by_renders_a_field_value():
    occasion = _occasion(
        distinguisher=FieldValue(
            object_type=ParticipantStatus, field="vf", value=CS_vf.VF
        )
    )
    assert _rendered(occasion) == "`vfState` = `VF`"


def test_distinguished_by_names_a_dimension_field_by_its_wire_spelling():
    """``CaseStatus.pxa`` renders as ``pxaState``, its AS2 key (#4376)."""
    occasion = _occasion(
        distinguisher=FieldValue(
            object_type=CaseStatus, field="pxa", value=CS_pxa.Pxa
        )
    )
    assert _rendered(occasion) == "`pxaState` = `Pxa`"


def test_distinguished_by_names_an_embedded_field_by_its_dotted_path():
    """A field read within an embedded model renders as its wire path."""
    occasion = _occasion(
        distinguisher=FieldValue(
            object_type=ParticipantStatus,
            within="case_status",
            field="pxa",
            value=CS_pxa.Pxa,
        )
    )
    assert _rendered(occasion) == "`caseStatus.pxaState` = `Pxa`"


def test_distinguished_by_renders_a_state_context():
    occasion = _occasion(
        distinguisher=StateContext(machine=EM, states=(EM.NONE, EM.PROPOSED))
    )
    assert _rendered(occasion) == "EM state `NONE` or `PROPOSED`"


@pytest.mark.spec("MSM-08-002")
def test_distinguished_by_renders_a_register_status_as_the_named_embargos():
    """A register status belongs to the embargo the activity names, not to
    the case, so it is not rendered as a bare machine state (MSM-08-003)."""
    occasion = _occasion(
        distinguisher=StateContext(
            machine=EmbargoRegisterStatus,
            states=(EmbargoRegisterStatus.TERMINATED,),
        )
    )
    rendered = _rendered(occasion)
    assert rendered == "register status of the named embargo `TERMINATED`"
    assert "EmbargoRegisterStatus" not in rendered


@pytest.mark.spec("MSM-08-002", "MSM-08-010")
@pytest.mark.parametrize(
    ("holds", "expected"),
    [
        (True, "sender is the case owner"),
        (False, "sender is not the case owner"),
    ],
    ids=["holds", "lacks"],
)
def test_distinguished_by_renders_a_sender_standing_from_its_kind(
    holds: bool, expected: str
):
    occasion = _occasion(
        distinguisher=SenderStanding(
            kind=SenderEntitlementKind.CASE_OWNER, holds=holds
        )
    )
    assert _rendered(occasion) == expected
    assert SenderEntitlementKind.CASE_OWNER.sent_by in expected


@pytest.mark.spec("MSM-08-010")
def test_distinguished_by_fills_a_sender_standing_placeholder_from_the_entry():
    """A kind held over an object names it from the entry's pattern."""
    entry = lookup_entry(MessageSemantics.ADD_NOTE_TO_CASE)
    occasion = _occasion(
        distinguisher=SenderStanding(
            kind=SenderEntitlementKind.AUTHOR, holds=False
        )
    )
    rendered = distinguished_by(entry, occasion)
    assert rendered is not None
    assert rendered.startswith("sender is not the ")
    assert "{object}" not in rendered


def test_distinguished_by_is_none_without_a_distinguisher():
    assert _rendered(_occasion()) is None


# ---------------------------------------------------------------------------
# Rendered fragments (AC-1, AC-4, AC-5).
# ---------------------------------------------------------------------------


def test_slice_has_the_lookup_columns(table):
    lines = gen.render_slice(table.groups[0]).splitlines()
    assert lines[0] == (
        "| When… | Send | Send to | Sent by | Distinguished by | Details |"
    )
    assert len(lines) == 2 + len(table.groups[0].occasions)


@pytest.mark.spec("MSM-08-009")
def test_every_row_renders_its_occasions_addressee_as_send_to(table):
    """Each lookup row's "Send to" cell names the occasion's addressee."""
    addressees = {
        o.anchor: o.addressee for e in SEMANTIC_REGISTRY for o in e.occasions
    }
    for group in table.groups:
        lines = gen.render_slice(group).splitlines()[2:]
        for row, line in zip(group.occasions, lines, strict=True):
            assert row.send_to == addressees[row.anchor].send_to
            assert line.split(" | ")[2] == row.send_to, line


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
        " | the case manager"
        " | the case manager or the case owner or the participant status's"
        " author (usually: vendor)"
        " | `vfState` = `VF`"
        " | [Fix Readiness (CF)](../cs.md#fix-readiness) |"
    )


@pytest.mark.spec("MSM-06-001")
@pytest.mark.spec("MSM-08-005")
@pytest.mark.spec("SE-05-002")
def test_an_unhandled_entry_renders_not_handled_on_its_page():
    """The generator renders an entry no received use case handles.

    The fix-readiness entry stands in for a recognized type with no use
    case: its rows still render, through the YAML, with "Sent by" stating
    that it is not handled rather than failing on a missing sender rule.
    """
    semantics = MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT
    registry = [
        dataclasses.replace(e, use_case_class=None)
        if e.semantics is semantics
        else e
        for e in SEMANTIC_REGISTRY
    ]

    contents = gen.desired_contents(_ROOT, registry)

    row = next(
        line
        for line in contents[f"{gen.FRAGMENT_DIR}/lookup-cs.md"].splitlines()
        if "fix-readiness" in line
    )
    assert " | not handled (usually: vendor) | " in row
    section = contents[f"{gen.FRAGMENT_DIR}/sections/fix-readiness.md"]
    assert "- **Sent by:** not handled (usually: vendor)" in section


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


_HEADING = re.compile(r"^#+ (.+?)\s*$", re.M)
_EXPLICIT_ID = re.compile(r"\{\s*#([\w-]+)[^}]*\}$")


def _slugs(page: Path) -> set[str]:
    """The anchors *page*'s own headings take, as MkDocs' ``toc`` makes them:
    an explicit ``{ #id }`` attribute, or else the ``toc`` slug of the text."""
    slugs: set[str] = set()
    for match in _HEADING.finditer(page.read_text("utf-8")):
        title = match.group(1)
        explicit = _EXPLICIT_ID.search(title)
        slugs.add(explicit.group(1) if explicit else toc.slugify(title, "-"))
    return slugs


def test_formal_definition_links_name_an_existing_section():
    messages = _DOCS / "reference/formal_protocol/messages.md"
    anchors = _slugs(messages)
    for shorthand in ProtocolShorthand:
        link = gen.formal_link(shorthand, "")
        assert link.split("#", 1)[1].rstrip(")") in anchors


def test_table_links_target_the_group_page_and_a_generated_section(table):
    """Each Details link in a committed slice names its group's page and the
    anchor of one of that group's rows, whose section fragment exists.

    That the page includes that section is
    ``test_each_message_page_includes_its_slice_and_each_section_once``.
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


#: An opening code fence of any language that ``markdown_exec`` runs.
_EXEC_FENCE = re.compile(r"^\s*(`{3,}|~{3,})[^\n]*\bexec=", re.M)


@pytest.mark.spec("MSM-06-001")
def test_no_message_page_renders_its_table_at_build_time():
    """No page under ``docs/reference/messages/`` prints a mapping table
    from an exec block (MSM-06-001).  Its examples render inside the
    included sections, so a page carries no exec block of its own."""
    rendering = sorted(
        page.name
        for page in _MESSAGES.glob("*.md")
        if _EXEC_FENCE.search(page.read_text(encoding="utf-8"))
    )
    assert rendering == []


# ---------------------------------------------------------------------------
# The pages that include the fragments (MSM-08-004, #4431).
# ---------------------------------------------------------------------------

_INCLUDE = re.compile(r'\{%\s*include-markdown\s+"([^"]+)"')
_COMMENT = re.compile(r"<!--.*?-->", re.S)


def _raw_includes(page: Path) -> list[str]:
    """The include paths *page* names outside HTML comments, as written."""
    text = _COMMENT.sub("", page.read_text(encoding="utf-8"))
    return _INCLUDE.findall(text)


def _includes(page: Path) -> list[str]:
    """The fragments *page* includes, as paths relative to the pages."""
    return [posixpath.normpath(path) for path in _raw_includes(page)]


def test_every_include_path_on_a_message_page_is_page_relative():
    """``include-markdown`` resolves a path with no ``./`` or ``../`` prefix
    against ``docs/``, not against the page, so every include names one."""
    paths = [
        (page.name, path)
        for page in sorted(_MESSAGES.glob("*.md"))
        for path in _raw_includes(page)
    ]
    assert paths
    assert [p for p in paths if not p[1].startswith(("./", "../"))] == []


def _section(anchor: str) -> str:
    return f"{_FROM_PAGES}/sections/{anchor}.md"


def _slice(page: str) -> str:
    return f"{_FROM_PAGES}/lookup-{page}.md"


@pytest.mark.spec("MSM-06-001")
def test_the_message_types_page_opens_with_the_whole_table():
    """AC-1 of #4431: the whole table comes before the page's first ``##``."""
    text = (_MESSAGES / "index.md").read_text(encoding="utf-8")
    directive = text.index(f'"./{_FROM_PAGES}/lookup.md"')
    assert directive < text.index("\n## ")
    assert _includes(_MESSAGES / "index.md") == [f"{_FROM_PAGES}/lookup.md"]


_QUICK_REFERENCE = _DOCS / "reference/quick_reference.md"


def _glance_section() -> str:
    """The quick reference's "Message Types at a Glance" section, as written."""
    text = _QUICK_REFERENCE.read_text(encoding="utf-8")
    start = text.index("\n## Message Types at a Glance\n")
    end = text.index("\n## ", start + 1)
    return text[start:end]


@pytest.mark.spec("MSM-06-004")
def test_quick_reference_includes_the_generated_message_tables():
    """The section embeds both generated tables and writes no table row of
    its own, whatever its columns are called (#5066)."""
    fragments = Path(gen.FRAGMENT_DIR).relative_to("docs/reference").as_posix()
    section = _glance_section()
    assert [posixpath.normpath(p) for p in _INCLUDE.findall(section)] == [
        f"{fragments}/lookup.md",
        f"{fragments}/shorthands.md",
    ]
    rows = [
        line for line in section.splitlines() if line.lstrip().startswith("|")
    ]
    assert rows == []


@pytest.mark.spec("MSM-06-004")
def test_shorthand_table_lists_every_shorthand_with_its_carriers(table):
    """Each row links the first occasion of each wire activity that carries
    its shorthand, in table order, or "none" on its family page."""
    rows = gen.render_shorthands(table).splitlines()[2:]
    by_type = dict(zip(ProtocolShorthand, rows, strict=True))
    for shorthand, line in by_type.items():
        assert line.startswith(
            f"| `{shorthand.value}` | {shorthand.formal_name} |"
        )
        expected: dict[str, str] = {}
        for group in table.groups:
            for row in group.occasions:
                if row.shorthand is shorthand:
                    expected.setdefault(
                        row.send, f"../{group.page.value}.md#{row.anchor}"
                    )
        if expected:
            assert _LINK.findall(line) == list(expected.values()), line
            assert "[none]" not in line, line
        else:
            page, _ = gen.SHORTHAND_FAMILIES[shorthand.value[0]]
            assert line.endswith(
                f" | [none](../{page.value}.md#{gen.NO_WIRE_ANCHOR}) |"
            ), line
    assert by_type[ProtocolShorthand.RS] == (
        "| `RS` | Report Submission | RM"
        " | [`Offer(VulnerabilityReport)`](../rm.md#report-submission) |"
    )


@pytest.mark.spec("MSM-06-004")
def test_shorthand_table_links_each_wire_activity_once(table):
    """Two occasions of one shorthand on one wire activity link the first."""
    group, row = _rows(table)["fix-readiness"]
    twin = row.model_copy(update={"anchor": "fix-readiness-twin"})
    doubled = table.model_copy(
        update={
            "groups": (group.model_copy(update={"occasions": (row, twin)}),)
        }
    )
    line = next(
        line
        for line in gen.render_shorthands(doubled).splitlines()
        if line.startswith("| `CF`")
    )
    assert _LINK.findall(line) == ["../cs.md#fix-readiness"], line


@pytest.mark.spec("MSM-06-004")
def test_every_formal_model_page_has_the_no_wire_activity_section():
    for page, _ in gen.SHORTHAND_FAMILIES.values():
        assert gen.NO_WIRE_ANCHOR in _slugs(_MESSAGES / f"{page.value}.md")


@pytest.mark.spec("MSM-08-004")
def test_each_message_page_includes_its_slice_and_each_section_once(table):
    """Each occasion anchor resolves to exactly one section on its page: the
    page includes the section once, no other message page includes it, and
    no hand-written heading on the page takes the same anchor."""
    owners: dict[str, list[str]] = {}
    for page in sorted(_MESSAGES.glob("*.md")):
        for path in _includes(page):
            owners.setdefault(path, []).append(page.stem)
    for group in table.groups:
        page = _MESSAGES / f"{group.page.value}.md"
        included = _includes(page)
        assert included.count(_slice(group.page.value)) == 1, page
        hand_written = _slugs(page)
        for row in group.occasions:
            assert owners.get(_section(row.anchor)) == [page.stem], row.anchor
            assert row.anchor not in hand_written, (page, row.anchor)


@pytest.mark.spec("MSM-08-004")
def test_every_included_section_is_referenced_by_a_row_of_its_page(table):
    """Every occasion section a page includes is the target of a Details
    link in the slice that page includes, and the page includes nothing
    else from the fragment directory."""
    by_page = {group.page.value: group for group in table.groups}
    for page in sorted(_MESSAGES.glob("*.md")):
        if page.stem == "index":
            continue
        included = [
            p for p in _includes(page) if p.startswith(f"{_FROM_PAGES}/")
        ]
        group = by_page[page.stem]
        slice_path = _MESSAGES / _slice(page.stem)
        targets = _LINK.findall(slice_path.read_text(encoding="utf-8"))
        resolved = [_resolve(slice_path, target) for target in targets]
        linked = {anchor for path, anchor in resolved if path == page}
        sections = {
            Path(path).stem
            for path in included
            if path.startswith(f"{_FROM_PAGES}/sections/")
        }
        assert sections == linked == {row.anchor for row in group.occasions}
        assert len(included) == len(sections) + 1, page


@pytest.mark.spec("MSM-06-003")
def test_every_section_links_its_mapping_status_to_its_definition(table):
    """A section states its entry's status, linked to the definitions on the
    Message Types page, which carry every status value."""
    index = _MESSAGES / gen.STATUS_PAGE
    assert gen.STATUS_ANCHOR in _slugs(index)
    text = index.read_text(encoding="utf-8")
    for status in MappingStatus:
        assert f"| `{status.value}` |" in text, status
    for _, row in _rows(table).values():
        section = gen.render_section(row)
        assert (
            f"- **Mapping status:** [{row.status.value}]"
            f"(../../{gen.STATUS_PAGE}#{gen.STATUS_ANCHOR})"
        ) in section, row.anchor


def test_no_fragment_is_exempt_from_lint_docs():
    """``lint-docs`` skips ``*table*.md`` as generated; these carry prose."""
    for path in _FRAGMENTS.rglob("*.md"):
        assert "table" not in path.name, path


def test_tables_carry_no_exec_block():
    """A table is mostly links, which an exec block would hide from MkDocs."""
    tables = [*_FRAGMENTS.glob("lookup*.md"), _FRAGMENTS / "shorthands.md"]
    for path in tables:
        assert "exec=" not in path.read_text(encoding="utf-8"), path


# ---------------------------------------------------------------------------
# Embeds and "Seen in" (#4432).
# ---------------------------------------------------------------------------

_HOWTO = _DOCS / "howto/activitypub/activities"
#: The embed directory as a how-to page's include directives name it.
_EMBEDS_FROM_HOWTO = posixpath.relpath(
    (_ROOT / gen.EMBED_DIR).as_posix(), _HOWTO.as_posix()
)


def _embed_directive(anchor: str, prefix: str = "../../../") -> str:
    embeds = Path(gen.EMBED_DIR).relative_to("docs").as_posix()
    path = f"{prefix}{embeds}/{anchor}.md"
    return f'{{% include-markdown "{path}" %}}'


#: The ``mkdocs.yml`` keys :func:`gen.embedding_pages` reads, as a scratch
#: root carries them.
_SCRATCH_MKDOCS = (
    "draft_docs: |\n  developer/\n"
    "exclude_docs: |\n  reference/messages/_occasions/\n"
)


def _docs_page(root: Path, docs_path: str, body: str) -> None:
    config = root / "mkdocs.yml"
    if not config.exists():
        config.write_text(_SCRATCH_MKDOCS, encoding="utf-8")
    page = root / "docs" / docs_path
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(body, encoding="utf-8")


_OWNERS = {
    "fix-readiness": MessagePage.CS,
    "add-note-to-case": MessagePage.GENERAL,
}


def test_embedding_pages_reads_include_directives_under_docs(tmp_path):
    """A page anywhere under ``docs/`` counts, once however often it
    includes the embed, whether or not the embed file exists yet."""
    _docs_page(
        tmp_path,
        "howto/guide.md",
        "# Guide\n\n"
        + _embed_directive("fix-readiness", "../")
        + "\n\n"
        + _embed_directive("fix-readiness", "../")
        + "\n",
    )
    _docs_page(
        tmp_path,
        "topics/deep/page.md",
        "# Topic\n\n" + _embed_directive("fix-readiness", "../../") + "\n",
    )

    found = gen.embedding_pages(_OWNERS, tmp_path)

    assert found == {
        "fix-readiness": ("howto/guide.md", "topics/deep/page.md")
    }


def test_embedding_pages_ignores_sections_and_the_fragment_directory(
    tmp_path,
):
    """A message page includes the section, which is not an embed, and a
    file in the fragment directory is generated, so never read."""
    _docs_page(
        tmp_path,
        "reference/messages/cs.md",
        '# CS\n\n{% include-markdown "./_occasions/sections/fix-readiness.md" %}\n',
    )
    _docs_page(
        tmp_path,
        "reference/messages/_occasions/embeds/stray.md",
        '{% include-markdown "./fix-readiness.md" %}\n',
    )

    assert gen.embedding_pages(_OWNERS, tmp_path) == {}


def test_embedding_pages_refuses_an_undeclared_anchor(tmp_path):
    _docs_page(
        tmp_path,
        "howto/guide.md",
        "# Guide\n\n" + _embed_directive("no-such-occasion", "../") + "\n",
    )

    with pytest.raises(ValueError, match=r"no-such-occasion\.md, which no"):
        gen.embedding_pages(_OWNERS, tmp_path)


def test_embedding_pages_refuses_an_embed_on_the_occasions_own_page(tmp_path):
    """The reference page carries the section, so "Seen in" never names it."""
    _docs_page(
        tmp_path,
        "reference/messages/cs.md",
        '# CS\n\n{% include-markdown "./_occasions/embeds/fix-readiness.md" %}\n',
    )

    with pytest.raises(ValueError, match="message page includes sections"):
        gen.embedding_pages(_OWNERS, tmp_path)


def test_embedding_pages_refuses_an_embed_on_another_message_page(tmp_path):
    """No message page lists in "Seen in", not only the occasion's own."""
    _docs_page(
        tmp_path,
        "reference/messages/general.md",
        '# General\n\n{% include-markdown "./_occasions/embeds/fix-readiness.md" %}\n',
    )

    with pytest.raises(
        ValueError, match=r"general\.md includes .*message page includes"
    ):
        gen.embedding_pages(_OWNERS, tmp_path)


def test_embedding_pages_refuses_an_embed_in_a_whole_included_fragment(
    tmp_path,
):
    """The reader sees the hosting page, so a fragment would be the wrong
    "Seen in" link; the embed belongs on the page."""
    _docs_page(
        tmp_path,
        "topics/x/_frag.md",
        _embed_directive("fix-readiness", "../../") + "\n",
    )
    _docs_page(
        tmp_path,
        "topics/x/page.md",
        '# Page\n\n{% include-markdown "./_frag.md" %}\n',
    )

    with pytest.raises(
        ValueError, match=r"_frag\.md includes .*included whole by another"
    ):
        gen.embedding_pages(_OWNERS, tmp_path)


def test_embedding_pages_counts_a_page_another_quotes_from_a_marker(tmp_path):
    """A page included only from a ``start=`` marker is still a page."""
    _docs_page(
        tmp_path,
        "topics/x/quoted.md",
        "# Quoted\n\n<!-- start -->\n\n"
        + _embed_directive("fix-readiness", "../../")
        + "\n",
    )
    _docs_page(
        tmp_path,
        "topics/x/page.md",
        '# Page\n\n{% include-markdown "./quoted.md" start="<!-- start -->" %}\n',
    )

    assert gen.embedding_pages(_OWNERS, tmp_path) == {
        "fix-readiness": ("topics/x/quoted.md",)
    }


def test_embedding_pages_skips_a_page_the_production_build_withholds(
    tmp_path,
):
    """A ``draft_docs`` page is served locally but not published, so a
    "Seen in" link to it would break the production build."""
    _docs_page(
        tmp_path,
        "developer/draft.md",
        "# Draft\n\n" + _embed_directive("fix-readiness", "../") + "\n",
    )
    _docs_page(
        tmp_path,
        "howto/guide.md",
        "# Guide\n\n" + _embed_directive("fix-readiness", "../") + "\n",
    )

    assert gen.embedding_pages(_OWNERS, tmp_path) == {
        "fix-readiness": ("howto/guide.md",)
    }


def test_derive_refuses_a_declared_guide_that_does_not_embed_its_occasion(
    tmp_path,
):
    guide = HowToGuide.STATUS_UPDATES
    _docs_page(tmp_path, guide.value, "# How to Post\n\nNo embed here.\n")
    entry = _entry(_occasion(howto=guide))

    with pytest.raises(ValueError, match="do not embed the occasion"):
        gen.derive_table([entry], tmp_path)


def test_derive_lists_each_embedding_page_by_its_title(tmp_path):
    guide = HowToGuide.STATUS_UPDATES
    _docs_page(
        tmp_path,
        guide.value,
        "# How to Post\n\n" + _embed_directive("stub-situation") + "\n",
    )
    (note,) = [
        e
        for e in SEMANTIC_REGISTRY
        if e.semantics is MessageSemantics.ADD_NOTE_TO_CASE
    ]
    entry = dataclasses.replace(note, occasions=(_occasion(howto=guide),))

    (row,) = gen.derive_table([entry], tmp_path).groups[0].occasions

    assert row.seen_in == (PageLink(path=guide.value, title="How to Post"),)


def test_section_lists_seen_in_pages_and_omits_the_line_without_any(table):
    _, row = _rows(table)["fix-readiness"]
    section = gen.render_section(row)
    assert row.seen_in
    links = ", ".join(
        f"[{page.title}](../../../../{page.path})" for page in row.seen_in
    )
    assert f"- **Seen in:** {links}\n" in section
    assert "How-to:" not in section

    bare = row.model_copy(update={"seen_in": ()})
    assert "Seen in" not in gen.render_section(bare)


def test_embed_links_its_canonical_section_and_collapses_the_example(table):
    """AC-1: separated from the host's prose, linked to its canonical
    section, the example JSON collapsed (DF-01-003)."""
    group, row = _rows(table)["fix-readiness"]
    embed = gen.render_embed(group, row)
    lines = embed.splitlines()

    assert lines[0] == '!!! info "Fix Readiness (CF)"'
    assert all(not line or line.startswith("    ") for line in lines[1:])
    assert (
        "    - **Reference:** [Fix Readiness (CF)](../../cs.md#fix-readiness)"
        in lines
    )
    collapse = lines.index('    ??? example "Example activity"')
    fence = lines.index('        ```python exec="true" idprefix=""')
    assert collapse < fence
    assert (
        "        print(json2md(add_fix_readiness_to_participant()))" in lines
    )


def test_no_embed_carries_a_heading_or_reference_only_facts():
    """No heading, so a host gains no anchor that could collide with its
    own, and no fact the canonical section alone carries."""
    embeds = sorted((_FRAGMENTS / "embeds").glob("*.md"))
    assert embeds
    for path in embeds:
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"^\s*#", text, re.M), path
        for fact in ("Seen in", "Formal definition", "Mapping status"):
            assert fact not in text, (path, fact)


def test_seen_in_never_names_a_reference_page(table):
    pages = [
        page.path for _, row in _rows(table).values() for page in row.seen_in
    ]
    assert pages
    assert [p for p in pages if p.startswith("reference/messages/")] == []


def test_every_declared_guide_embeds_its_occasions_in_the_committed_table(
    table,
):
    """AC-4: each guide shows the occasions its steps send."""
    rows = _rows(table)
    for entry in SEMANTIC_REGISTRY:
        for occasion in entry.occasions:
            if occasion.howto is None:
                continue
            _, row = rows[occasion.anchor]
            assert occasion.howto.value in {p.path for p in row.seen_in}


def test_every_embed_include_on_a_howto_page_is_page_relative():
    """``include-markdown`` resolves an unprefixed path against ``docs/``."""
    directives = [
        (page.name, path)
        for page in sorted(_HOWTO.glob("[!_]*.md"))
        for path in _raw_includes(page)
        if "/embeds/" in path
    ]
    assert directives
    for name, path in directives:
        assert path.startswith(f"{_EMBEDS_FROM_HOWTO}/"), (name, path)


def test_the_sync_hook_watches_every_docs_page_and_the_include_reader():
    """AC-2: a new include anywhere under ``docs/`` re-runs ``--check``."""
    config = yaml.safe_load(
        (_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    )
    (hook,) = [
        h
        for repo in config["repos"]
        for h in repo["hooks"]
        if h["id"] == "msm-occasions-sync"
    ]
    files = re.compile(hook["files"])
    for path in (
        "docs/howto/activitypub/activities/status_updates.md",
        "docs/topics/anything/page.md",
        "vultron/metadata/docs/page_frontmatter.py",
        "vultron/metadata/base.py",
        "mkdocs.yml",
    ):
        assert files.search(path), path
