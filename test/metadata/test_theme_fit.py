"""Tests for the ``theme-fit`` structural theme check.

Pure: no network. Fixture Issues are built directly, and the ``gh`` call goes
through a fake runner that answers with a canned GraphQL page list.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from vultron.metadata.planning import gh as gh_module
from vultron.metadata.planning.gh import GhError
from vultron.metadata.planning.theme_fit import (
    AUTO_CALVED_MARKER,
    GITHUB_BODY_LIMIT,
    UNSCHEDULED,
    Ancestor,
    FindingKind,
    OpenIssue,
    ThemeFitReport,
    analyze,
    fetch_open_issues,
    main,
    nearest_epic,
    parse_pages,
    render_coherence,
    render_markdown,
)
from vultron.metadata.planning.themes import (
    BEGIN_MARKER,
    END_MARKER,
    ThemeCatalog,
    parse_theme_catalog,
)

_CATALOG_YAML = """\
themes:
  - label: theme:alpha
    outcome: Alpha works
    in_bounds: [alpha things]
    out_of_bounds: [beta things]
    color: 1D76DB
  - label: theme:beta
    outcome: Beta works
    in_bounds: [beta things]
    out_of_bounds: [alpha things]
    color: 1D76DB
  - label: theme:old
    outcome: Old outcome
    in_bounds: [nothing new]
    out_of_bounds: [every new Issue]
    color: 1D76DB
    status: retiring
    replaced_by: [theme:alpha]
"""

_NOTE = (
    f"# Note\n\n{BEGIN_MARKER}\n```yaml\n{_CATALOG_YAML}```\n{END_MARKER}\n"
)


@pytest.fixture
def catalog() -> ThemeCatalog:
    return parse_theme_catalog(_NOTE, "note.md")


def _issue(
    number: int,
    *themes: str,
    kind: str | None = "Task",
    parents: Sequence[tuple[int, str | None]] = (),
    body: str | None = None,
    schedule: str | None = None,
    extra_labels: Sequence[str] = (),
) -> OpenIssue:
    """An open Issue; *body* defaults to a reason line naming each theme."""
    if body is None:
        body = "".join(f"Theme: {t} — does a thing.\n" for t in themes)
    return OpenIssue(
        number=number,
        title=f"Issue {number}",
        issue_type=kind,
        labels=frozenset((*themes, *extra_labels)),
        body=body,
        ancestors=tuple(Ancestor(n, t) for n, t in parents),
        schedule=schedule,
    )


def _epic_issue(
    number: int,
    *themes: str,
    parents: Sequence[tuple[int, str | None]] = (),
    body: str | None = None,
    schedule: str | None = None,
) -> OpenIssue:
    return _issue(
        number,
        *themes,
        kind="Epic",
        parents=parents,
        body=body,
        schedule=schedule,
    )


def _kinds(report: ThemeFitReport) -> list[tuple[FindingKind, int]]:
    return [(f.kind, f.number) for f in report.findings]


_EPIC = (1, "Epic")


class TestClean:
    def test_coherent_tree_has_no_findings(
        self, catalog: ThemeCatalog
    ) -> None:
        report = analyze(
            [
                _epic_issue(1, "theme:alpha", schedule="Now"),
                _issue(2, "theme:alpha", parents=[_EPIC]),
                _issue(3, "theme:alpha", parents=[_EPIC]),
            ],
            catalog,
        )
        assert report.clean
        assert report.findings == ()


@pytest.mark.spec("PAD-02-014")
class TestLeafThemeCount:
    @pytest.mark.parametrize(
        "themes", [(), ("theme:alpha", "theme:beta")], ids=["zero", "two"]
    )
    def test_leaf_without_exactly_one(
        self, catalog: ThemeCatalog, themes: tuple[str, ...]
    ) -> None:
        report = analyze(
            [
                _epic_issue(1, "theme:alpha"),
                _issue(2, *themes, parents=[_EPIC]),
            ],
            catalog,
        )
        assert (FindingKind.LEAF_THEME_COUNT, 2) in _kinds(report)

    def test_non_leaf_task_is_not_held_to_the_leaf_rule(
        self, catalog: ThemeCatalog
    ) -> None:
        report = analyze(
            [
                _epic_issue(1, "theme:alpha"),
                _issue(2, parents=[_EPIC]),
                _issue(3, "theme:alpha", parents=[(2, "Task"), _EPIC]),
            ],
            catalog,
        )
        assert FindingKind.LEAF_THEME_COUNT not in {
            f.kind for f in report.findings
        }

    def test_non_theme_labels_do_not_count(
        self, catalog: ThemeCatalog
    ) -> None:
        report = analyze(
            [
                _epic_issue(1, "theme:alpha"),
                _issue(
                    2, "theme:alpha", parents=[_EPIC], extra_labels=["size:S"]
                ),
            ],
            catalog,
        )
        assert report.clean

    def test_label_case_is_ignored(self, catalog: ThemeCatalog) -> None:
        report = analyze(
            [
                _epic_issue(1, "theme:alpha"),
                _issue(
                    2,
                    "Theme:Alpha",
                    parents=[_EPIC],
                    body="Theme: theme:alpha — x\n",
                ),
            ],
            catalog,
        )
        assert report.clean


@pytest.mark.spec("PAD-02-015")
class TestEpicThemeCount:
    def test_no_theme(self, catalog: ThemeCatalog) -> None:
        report = analyze([_epic_issue(1)], catalog)
        assert _kinds(report) == [(FindingKind.EPIC_THEME_COUNT, 1)]

    def test_three_themes(self, catalog: ThemeCatalog) -> None:
        epic = _epic_issue(
            1,
            "theme:alpha",
            "theme:beta",
            "theme:old",
            body="Theme: theme:alpha theme:beta theme:old — all\n",
        )
        assert (FindingKind.EPIC_THEME_COUNT, 1) in _kinds(
            analyze([epic], catalog)
        )

    def test_two_themes_without_a_split_line(
        self, catalog: ThemeCatalog
    ) -> None:
        report = analyze(
            [_epic_issue(1, "theme:alpha", "theme:beta")], catalog
        )
        assert _kinds(report) == [(FindingKind.EPIC_THEME_COUNT, 1)]

    def test_two_themes_with_a_split_line(self, catalog: ThemeCatalog) -> None:
        body = (
            "Theme: theme:alpha — a.\nTheme: theme:beta — b.\n"
            "Theme split: theme:alpha holds the parser; theme:beta the CLI.\n"
        )
        report = analyze(
            [_epic_issue(1, "theme:alpha", "theme:beta", body=body)], catalog
        )
        assert report.clean


@pytest.mark.spec("PAD-02-018")
class TestReasonLine:
    @pytest.mark.parametrize(
        "body",
        [
            "",
            "Theme: — no label named\n",
            "Theme: theme:beta — names the wrong label\n",
            "The theme:alpha label, outside a Theme: line\n",
            "Theme: theme:alphabet — a longer label is not this one\n",
            "Theme: theme:alpha\n",
            "Theme: theme:alpha — \n",
            "Theme: theme:alpha—no space around the dash\n",
        ],
    )
    def test_missing(self, catalog: ThemeCatalog, body: str) -> None:
        report = analyze(
            [
                _epic_issue(1, "theme:alpha"),
                _issue(2, "theme:alpha", parents=[_EPIC], body=body),
            ],
            catalog,
        )
        assert _kinds(report) == [(FindingKind.MISSING_REASON_LINE, 2)]

    @pytest.mark.parametrize("dash", ["\u2014", "\u2013", "-"])
    def test_any_spaced_dash_splits_the_outcome(
        self, catalog: ThemeCatalog, dash: str
    ) -> None:
        report = analyze(
            [
                _epic_issue(1, "theme:alpha"),
                _issue(
                    2,
                    "theme:alpha",
                    parents=[_EPIC],
                    body=f"Theme: theme:alpha {dash} does x - and y\n",
                ),
            ],
            catalog,
        )
        assert report.clean

    def test_indented_backticked_line_counts(
        self, catalog: ThemeCatalog
    ) -> None:
        report = analyze(
            [
                _epic_issue(1, "theme:alpha"),
                _issue(
                    2,
                    "theme:alpha",
                    parents=[_EPIC],
                    body="Intro.\n  Theme: `theme:alpha` — x\n",
                ),
            ],
            catalog,
        )
        assert report.clean

    def test_unlabeled_issue_needs_no_line(
        self, catalog: ThemeCatalog
    ) -> None:
        report = analyze(
            [_epic_issue(1, "theme:alpha"), _issue(2, parents=[_EPIC])],
            catalog,
        )
        assert _kinds(report) == [(FindingKind.LEAF_THEME_COUNT, 2)]


@pytest.mark.spec("PAD-02-017")
class TestMismatch:
    def test_child_theme_differs(self, catalog: ThemeCatalog) -> None:
        report = analyze(
            [
                _epic_issue(1, "theme:alpha"),
                _issue(2, "theme:beta", parents=[_EPIC]),
            ],
            catalog,
        )
        assert _kinds(report) == [(FindingKind.THEME_MISMATCH, 2)]
        assert "Epic #1" in report.findings[0].detail

    def test_grandchild_compares_with_nearest_epic(
        self, catalog: ThemeCatalog
    ) -> None:
        report = analyze(
            [
                _epic_issue(1, "theme:alpha"),
                _issue(2, "theme:alpha", parents=[_EPIC]),
                _issue(3, "theme:beta", parents=[(2, "Task"), _EPIC]),
            ],
            catalog,
        )
        assert _kinds(report) == [(FindingKind.THEME_MISMATCH, 3)]

    def test_either_epic_theme_matches(self, catalog: ThemeCatalog) -> None:
        body = "Theme: theme:alpha and theme:beta — split by layer\n"
        report = analyze(
            [
                _epic_issue(1, "theme:alpha", "theme:beta", body=body),
                _issue(2, "theme:beta", parents=[_EPIC]),
            ],
            catalog,
        )
        assert report.clean

    def test_unthemed_non_leaf_child_is_a_mismatch(
        self, catalog: ThemeCatalog
    ) -> None:
        report = analyze(
            [
                _epic_issue(1, "theme:alpha"),
                _issue(2, parents=[_EPIC]),
                _issue(3, "theme:alpha", parents=[(2, "Task"), _EPIC]),
            ],
            catalog,
        )
        assert _kinds(report) == [(FindingKind.THEME_MISMATCH, 2)]
        assert report.findings[0].detail.startswith("no theme label;")

    def test_unthemed_leaf_is_only_a_count_finding(
        self, catalog: ThemeCatalog
    ) -> None:
        report = analyze(
            [_epic_issue(1, "theme:alpha"), _issue(2, parents=[_EPIC])],
            catalog,
        )
        assert _kinds(report) == [(FindingKind.LEAF_THEME_COUNT, 2)]

    def test_unthemed_side_is_not_a_mismatch(
        self, catalog: ThemeCatalog
    ) -> None:
        report = analyze(
            [_epic_issue(1), _issue(2, "theme:beta", parents=[_EPIC])],
            catalog,
        )
        assert FindingKind.THEME_MISMATCH not in {
            f.kind for f in report.findings
        }


@pytest.mark.spec("PAD-01-007")
class TestHierarchy:
    def test_unparented_non_epic(self, catalog: ThemeCatalog) -> None:
        report = analyze([_issue(2, "theme:alpha", kind="Bug")], catalog)
        assert _kinds(report) == [(FindingKind.UNPARENTED, 2)]
        assert report.findings[0].detail == "no parent"

    def test_untyped_issue_needs_an_epic(self, catalog: ThemeCatalog) -> None:
        report = analyze([_issue(2, "theme:alpha", kind=None)], catalog)
        assert _kinds(report) == [(FindingKind.UNPARENTED, 2)]

    def test_parent_without_epic_ancestor(self, catalog: ThemeCatalog) -> None:
        report = analyze(
            [
                _issue(2, "theme:alpha"),
                _issue(3, "theme:alpha", parents=[(2, "Task")]),
            ],
            catalog,
        )
        assert (FindingKind.UNPARENTED, 3) in _kinds(report)
        assert "parent #2" in report.of_kind(FindingKind.UNPARENTED)[1].detail

    def test_child_of_a_closed_epic(self, catalog: ThemeCatalog) -> None:
        report = analyze(
            [_issue(2, "theme:alpha", parents=[(9, "Epic")])], catalog
        )
        assert _kinds(report) == [(FindingKind.UNPARENTED, 2)]
        assert report.findings[0].detail == "its nearest Epic, #9, is closed"
        assert report.coherence == ()

    def test_unparented_epic_is_fine(self, catalog: ThemeCatalog) -> None:
        assert analyze([_epic_issue(1, "theme:alpha")], catalog).clean

    def test_nested_epic(self, catalog: ThemeCatalog) -> None:
        report = analyze(
            [
                _epic_issue(1, "theme:alpha"),
                _epic_issue(5, "theme:alpha", parents=[_EPIC]),
            ],
            catalog,
        )
        assert _kinds(report) == [(FindingKind.NESTED_EPIC, 5)]
        assert FindingKind.NESTED_EPIC.rule == "PAD-01-002"


class TestNearestEpic:
    def test_walk_continues_past_the_fetched_depth(self) -> None:
        deep = _issue(9, parents=[(8, "Task"), (7, "Task"), (6, "Task")])
        six = _issue(6, parents=[(5, "Task"), _EPIC])
        by_number = {i.number: i for i in (deep, six)}
        assert nearest_epic(deep, by_number) == 1

    def test_closed_ancestor_ends_the_walk(self) -> None:
        deep = _issue(9, parents=[(8, "Task"), (7, "Task"), (6, "Task")])
        assert nearest_epic(deep, {9: deep}) is None

    def test_cycle_ends_the_walk(self) -> None:
        a = _issue(2, parents=[(3, "Task")])
        b = _issue(3, parents=[(2, "Task")])
        assert nearest_epic(a, {2: a, 3: b}) is None


@pytest.mark.spec("PAD-02-008")
class TestAutoCalved:
    @pytest.mark.parametrize("children", [0, 1])
    def test_single_child(self, catalog: ThemeCatalog, children: int) -> None:
        body = f"Theme: theme:alpha — x\n{AUTO_CALVED_MARKER}\n"
        issues = [_epic_issue(1, "theme:alpha", body=body)]
        issues += [
            _issue(10 + n, "theme:alpha", parents=[_EPIC])
            for n in range(children)
        ]
        report = analyze(issues, catalog)
        assert _kinds(report) == [(FindingKind.SINGLE_CHILD_CALVED_EPIC, 1)]

    def test_two_children_is_fine(self, catalog: ThemeCatalog) -> None:
        body = f"Theme: theme:alpha — x\n  {AUTO_CALVED_MARKER}  \n"
        report = analyze(
            [
                _epic_issue(1, "theme:alpha", body=body),
                _issue(2, "theme:alpha", parents=[_EPIC]),
                _issue(3, "theme:alpha", parents=[_EPIC]),
            ],
            catalog,
        )
        assert report.clean

    def test_unmarked_single_child_epic_is_fine(
        self, catalog: ThemeCatalog
    ) -> None:
        report = analyze(
            [
                _epic_issue(1, "theme:alpha"),
                _issue(2, "theme:alpha", parents=[_EPIC]),
            ],
            catalog,
        )
        assert report.clean

    def test_marker_inside_a_line_does_not_count(
        self, catalog: ThemeCatalog
    ) -> None:
        body = f"Theme: theme:alpha — x\nsee {AUTO_CALVED_MARKER}\n"
        assert analyze(
            [_epic_issue(1, "theme:alpha", body=body)], catalog
        ).clean


@pytest.mark.spec("PAD-02-014")
class TestCatalogMembership:
    def test_unknown_theme(self, catalog: ThemeCatalog) -> None:
        report = analyze(
            [
                _epic_issue(1, "theme:alpha"),
                _issue(2, "theme:zeta", parents=[_EPIC]),
            ],
            catalog,
        )
        assert (FindingKind.UNKNOWN_THEME, 2) in _kinds(report)

    def test_retiring_theme_names_replacement(
        self, catalog: ThemeCatalog
    ) -> None:
        report = analyze(
            [
                _epic_issue(1, "theme:old"),
                _issue(2, "theme:old", parents=[_EPIC]),
            ],
            catalog,
        )
        retiring = report.of_kind(FindingKind.RETIRING_THEME)
        assert [f.number for f in retiring] == [1, 2]
        assert "`theme:alpha`" in retiring[0].detail


class TestCoherence:
    def test_per_tier_shares(self, catalog: ThemeCatalog) -> None:
        now, later = (1, "Epic"), (5, "Epic")
        report = analyze(
            [
                _epic_issue(1, "theme:alpha", schedule="Now"),
                _issue(2, "theme:alpha", parents=[now]),
                _issue(3, "theme:beta", parents=[now]),
                _issue(4, parents=[now]),
                _epic_issue(5, "theme:beta", schedule="Later"),
                _issue(6, "theme:beta", parents=[later]),
                _epic_issue(7, "theme:beta"),
                _issue(8, "theme:alpha"),  # no Epic: outside every tier
            ],
            catalog,
        )
        rows = {r.tier: r for r in report.coherence}
        assert [r.tier for r in report.coherence] == [
            "Now",
            "Later",
            UNSCHEDULED,
        ]
        assert (rows["Now"].epics, rows["Now"].children) == (1, 3)
        assert rows["Now"].matching == 1
        assert rows["Later"].share == 1.0
        assert rows[UNSCHEDULED].children == 0
        assert rows[UNSCHEDULED].share is None

    def test_two_theme_child_does_not_match(
        self, catalog: ThemeCatalog
    ) -> None:
        report = analyze(
            [
                _epic_issue(1, "theme:alpha", schedule="Next"),
                _issue(2, "theme:alpha", "theme:beta", parents=[_EPIC]),
            ],
            catalog,
        )
        assert report.coherence[0].matching == 0

    def test_tier_order_follows_schedule_order(
        self, catalog: ThemeCatalog
    ) -> None:
        tiers = ["Someday", "Custom", "Focus", "Next"]
        report = analyze(
            [
                _epic_issue(n, "theme:alpha", schedule=t)
                for n, t in enumerate(tiers, 1)
            ],
            catalog,
        )
        assert [r.tier for r in report.coherence] == [
            "Focus",
            "Next",
            "Someday",
            "Custom",
        ]


class TestRender:
    def test_markdown_lists_every_kind_and_the_tiers(
        self, catalog: ThemeCatalog
    ) -> None:
        report = analyze(
            [
                _epic_issue(1, "theme:alpha", schedule="Now"),
                _issue(2, "theme:beta", parents=[_EPIC]),
                _issue(3, "theme:alpha", parents=[_EPIC]),
            ],
            catalog,
        )
        text = render_markdown(report)
        assert text.startswith("# Theme fit report\n")
        assert "3 open Issues checked; 1 finding(s)." in text
        assert "| Now | 1 | 2 | 1 | 50% |" in text
        assert "| All tiers | 1 | 2 | 1 | 50% |" in text
        for kind in FindingKind:
            assert f"| {kind.heading} | {kind.rule} |" in text
        assert "### Child theme differs from its Epic's (1)" in text
        assert "- #2 Issue 2 — carries `theme:beta`" in text
        assert "### Leaf without" not in text

    def test_titles_cannot_mention_anyone(self, catalog: ThemeCatalog) -> None:
        issue = OpenIssue(
            number=2,
            title="Carry @context and @octocat",
            issue_type="Bug",
            labels=frozenset(),
            body="",
        )
        text = render_markdown(analyze([issue], catalog))
        assert "@" not in text.split("## Findings")[1]
        assert "Carry &#64;context and &#64;octocat" in text

    def test_empty_tier_reads_n_a(self, catalog: ThemeCatalog) -> None:
        report = analyze([_epic_issue(1, "theme:alpha")], catalog)
        assert f"| {UNSCHEDULED} | 1 | 0 | 0 | n/a |" in render_coherence(
            report
        )

    def test_limit_cuts_each_list_and_keeps_the_tables(
        self, catalog: ThemeCatalog
    ) -> None:
        issues = [_issue(n, "theme:alpha", kind="Bug") for n in range(1, 41)]
        report = analyze(issues, catalog)
        full = render_markdown(report)
        limit = len(full) - 300
        cut = render_markdown(report, limit)
        assert len(cut) <= limit
        assert cut.startswith(full[: full.index("### ")])
        listed = cut.count("— no parent")
        assert 0 < listed < 40
        assert f"- … and {40 - listed} more; run `uv run theme-fit`" in cut

    def test_limit_the_full_report_fits_changes_nothing(
        self, catalog: ThemeCatalog
    ) -> None:
        report = analyze([_issue(2, "theme:alpha")], catalog)
        full = render_markdown(report)
        assert render_markdown(report, len(full)) == full
        assert render_markdown(report, GITHUB_BODY_LIMIT) == full

    def test_limit_below_the_summary_raises(
        self, catalog: ThemeCatalog
    ) -> None:
        report = analyze([_issue(2, "theme:alpha")], catalog)
        with pytest.raises(ValueError, match="summary alone"):
            render_markdown(report, 10)

    def test_json_counts_every_kind(self, catalog: ThemeCatalog) -> None:
        report = analyze([_issue(2, "theme:alpha")], catalog)
        data = report.to_json()
        assert data["clean"] is False
        assert data["counts"] == {
            k.value: int(k is FindingKind.UNPARENTED) for k in FindingKind
        }
        assert data["findings"] == [
            {
                "kind": "unparented",
                "rule": "PAD-01-007",
                "number": 2,
                "title": "Issue 2",
                "detail": "no parent",
            }
        ]


def _node(
    number: int,
    *,
    kind: str | None = "Task",
    labels: Sequence[str] = (),
    body: str | None = "",
    parent: dict[str, object] | None = None,
    schedule: str | None = None,
) -> dict[str, object]:
    items = (
        [
            {"project": {"number": 8}, "fieldValueByName": None},
            {
                "project": {"number": 24},
                "fieldValueByName": {"name": schedule},
            },
        ]
        if schedule
        else []
    )
    return {
        "number": number,
        "title": f"Issue {number}",
        "body": body,
        "issueType": {"name": kind} if kind else None,
        "labels": {"nodes": [{"name": n} for n in labels]},
        "parent": parent,
        "projectItems": {"nodes": items},
    }


def _page(*nodes: dict[str, object]) -> dict[str, object]:
    return {"data": {"repository": {"issues": {"nodes": list(nodes)}}}}


class TestParse:
    def test_fields(self) -> None:
        parent = {
            "number": 4,
            "issueType": {"name": "Task"},
            "parent": {
                "number": 1,
                "issueType": {"name": "Epic"},
                "parent": None,
            },
        }
        pages = [
            _page(_node(1, kind="Epic", schedule="Now")),
            _page(
                _node(
                    2, labels=["theme:alpha", "bug"], body=None, parent=parent
                )
            ),
        ]
        epic, child = parse_pages(pages)
        assert epic.schedule == "Now"
        assert epic.is_epic
        assert child.labels == frozenset({"theme:alpha", "bug"})
        assert child.body == ""
        assert child.ancestors == (Ancestor(4, "Task"), Ancestor(1, "Epic"))
        assert child.schedule is None

    def test_untyped_issue(self) -> None:
        (issue,) = parse_pages([_page(_node(3, kind=None))])
        assert issue.issue_type is None

    @pytest.mark.parametrize(
        "pages",
        [{}, [{}], [{"data": None}], [_page({"title": "no number"})], [1]],
    )
    def test_unreadable_raises(self, pages: object) -> None:
        with pytest.raises(GhError, match="could not read"):
            parse_pages(pages)

    def test_graphql_errors_raise(self) -> None:
        pages = [{"data": None, "errors": [{"message": "rate limited"}]}]
        with pytest.raises(GhError, match="rate limited"):
            parse_pages(pages)


class _FakeGh:
    """Records ``gh`` calls; answers with *pages* as JSON."""

    def __init__(self, pages: object, fail: bool = False) -> None:
        self.pages = pages
        self.fail = fail
        self.calls: list[list[str]] = []

    def __call__(self, args: Sequence[str]) -> str:
        self.calls.append(list(args))
        if self.fail:
            raise subprocess.CalledProcessError(1, ["gh"], stderr="boom")
        return (
            self.pages
            if isinstance(self.pages, str)
            else json.dumps(self.pages)
        )


class TestFetch:
    def test_query_is_read_only_and_paginated(self) -> None:
        fake = _FakeGh([_page(_node(1, kind="Epic"))])
        (issue,) = fetch_open_issues("o/r", run=fake)
        assert issue.number == 1
        (call,) = fake.calls
        assert call[:4] == ["api", "graphql", "--paginate", "--slurp"]
        assert call[call.index("owner=o") - 1] == "-f"
        assert call[call.index("name=r") - 1] == "-f"
        query = next(a for a in call if a.startswith("query="))
        assert "mutation" not in query
        assert "states: OPEN" in query

    @pytest.mark.parametrize("repo", ["noslash", "/r", "o/", "o/r/x"])
    def test_malformed_repo_raises(self, repo: str) -> None:
        with pytest.raises(GhError, match="OWNER/NAME"):
            fetch_open_issues(repo, run=_FakeGh([]))

    def test_non_json_raises(self) -> None:
        with pytest.raises(GhError, match="could not read"):
            fetch_open_issues("o/r", run=_FakeGh("not json"))

    def test_gh_not_installed_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def missing(*_: object, **__: object) -> None:
            raise FileNotFoundError("gh")

        monkeypatch.setattr(gh_module.subprocess, "run", missing)
        with pytest.raises(GhError, match="not installed"):
            fetch_open_issues("o/r")


@pytest.fixture
def note(tmp_path: Path) -> Path:
    path = tmp_path / "epic-themes.md"
    path.write_text(_NOTE, encoding="utf-8")
    return path


_CLEAN_PAGES = [
    _page(
        _node(
            1,
            kind="Epic",
            labels=["theme:alpha"],
            body="Theme: theme:alpha — x",
            schedule="Now",
        ),
        _node(
            2,
            labels=["theme:alpha"],
            body="Theme: theme:alpha — y",
            parent={
                "number": 1,
                "issueType": {"name": "Epic"},
                "parent": None,
            },
        ),
    )
]


class TestMain:
    def test_clean_exits_zero(
        self, note: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        fake = _FakeGh(_CLEAN_PAGES)
        assert main(["--catalog", str(note), "--repo", "o/r"], run=fake) == 0
        out = capsys.readouterr().out
        assert out.startswith("# Theme fit report\n")
        assert "| Now | 1 | 1 | 1 | 100% |" in out

    def test_findings_exit_one(self, note: Path) -> None:
        fake = _FakeGh([_page(_node(2))])
        assert main(["--catalog", str(note)], run=fake) == 1

    def test_json(
        self, note: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main(["--catalog", str(note), "--json"], run=_FakeGh(_CLEAN_PAGES))
        data = json.loads(capsys.readouterr().out)
        assert data["clean"] is True
        assert data["coherence"][0]["tier"] == "Now"

    def test_coherence_only(
        self, note: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main(
            ["--catalog", str(note), "--coherence"], run=_FakeGh(_CLEAN_PAGES)
        )
        out = capsys.readouterr().out
        assert out.startswith("| Tier |")
        assert "## Findings" not in out

    def test_max_chars_cuts_the_report(
        self, note: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        pages = [_page(*(_node(n) for n in range(1, 30)))]
        main(["--catalog", str(note)], run=_FakeGh(pages))
        full = capsys.readouterr().out
        limit = len(full) - 200
        args = ["--catalog", str(note), "--max-chars", str(limit)]
        assert main(args, run=_FakeGh(pages)) == 1
        out = capsys.readouterr().out
        assert len(out) <= limit
        assert "more; run" in out

    def test_max_chars_too_small_exits_two(
        self, note: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        args = ["--catalog", str(note), "--max-chars", "10"]
        assert main(args, run=_FakeGh(_CLEAN_PAGES)) == 2
        assert "summary alone" in capsys.readouterr().err

    def test_max_chars_must_be_positive(self, note: Path) -> None:
        with pytest.raises(SystemExit) as exc:
            main(["--catalog", str(note), "--max-chars", "0"], run=_FakeGh([]))
        assert exc.value.code == 2

    def test_gh_failure_exits_two(
        self, note: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["--catalog", str(note)], run=_FakeGh([], fail=True)) == 2
        assert "gh failed: boom" in capsys.readouterr().err

    def test_query_error_exits_two(
        self, note: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        fake = _FakeGh([{"errors": [{"message": "no read:project scope"}]}])
        assert main(["--catalog", str(note)], run=fake) == 2
        assert "read:project" in capsys.readouterr().err

    def test_missing_catalog_exits_two(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        fake = _FakeGh(_CLEAN_PAGES)
        code = main(["--catalog", str(tmp_path / "nope.md")], run=fake)
        assert code == 2
        assert fake.calls == []

    def test_bad_catalog_exits_two(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.md"
        bad.write_text("# no markers\n", encoding="utf-8")
        assert main(["--catalog", str(bad)], run=_FakeGh(_CLEAN_PAGES)) == 2


class TestRepositoryCatalog:
    def test_repository_catalog_loads_for_the_check(self) -> None:
        from vultron.metadata.planning.themes import load_theme_catalog

        report = analyze(
            [_issue(1, "theme:dev-workflow", kind="Epic")],
            load_theme_catalog(),
        )
        assert report.clean
