"""Tests for the cross-tab lookup page (``docs/lookup.md``).

Requirements: DF-11-021 (one lookup page listing every ``page_type:
reference`` page by top-level nav section; a subgroup listed once through the
index of its outermost group that has one; an omitted page placed by its own
directory's index or reported; generated and check gated; linked from the
home page and every start page), DF-09-009 (an empty target set fails).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from vultron.metadata.base import mkdocs_config, repo_root, walk_nav
from vultron.metadata.docs import site_sync
from vultron.metadata.docs.landing_pages import (
    BEGIN_MARKER as LANDING_BEGIN,
    CONTENTS_KEY,
    END_MARKER as LANDING_END,
)
from vultron.metadata.docs.lookup_page import (
    BEGIN_MARKER,
    END_MARKER,
    HOME_PATH,
    LOOKUP_PATH,
    lookup_link_faults,
    lookup_sections,
    render_lookup,
)
from vultron.metadata.docs.page_schema import is_start_page
from vultron.metadata.file_loading import MetadataLoadError, MetadataLoadErrors

from ._lookup_tree import LOOKUP_LINK
from ._thread_tree import stage, start_page

pytestmark = pytest.mark.spec("DF-11-021")


def _page(
    title: str,
    page_type: str = "reference",
    description: str | None = "What it holds.",
    body: str = "",
) -> str:
    keys = [
        "stakeholder_type: ALL",
        "level: 200",
        f"page_type: {page_type}",
    ]
    if description is not None:
        keys.append(f"description: {description}")
    return "---\n" + "\n".join(keys) + f"\n---\n\n# {title}\n\n{body}"


def _repo(
    tmp_path: Path,
    files: dict[str, str],
    nav: list[object],
    **config: object,
) -> Path:
    (tmp_path / "mkdocs.yml").write_text(
        yaml.safe_dump({"nav": nav, **config})
    )
    for rel, text in files.items():
        path = tmp_path / "docs" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


def _listed(root: Path) -> list[tuple[str, list[str | None]]]:
    return [
        (section.label, [entry.target for entry in section.entries])
        for section in lookup_sections(root)
    ]


class TestListing:
    def test_groups_by_top_level_section_in_nav_order(self, tmp_path):
        root = _repo(
            tmp_path,
            {
                "b.md": _page("B"),
                "a.md": _page("A"),
                "c.md": _page("C"),
            },
            [{"Second": ["b.md"]}, {"First": ["a.md", "c.md"]}],
        )
        assert _listed(root) == [
            ("Second", ["b.md"]),
            ("First", ["a.md", "c.md"]),
        ]

    def test_entry_links_the_page_and_shows_its_description(self, tmp_path):
        root = _repo(
            tmp_path,
            {"ref/a.md": _page("A", description="Every message type.")},
            [{"Tab": [{"Alpha": "ref/a.md"}]}],
        )
        rendered = render_lookup(lookup_sections(root))
        assert rendered == (
            "## Tab\n\n- [Alpha](ref/a.md) — Every message type."
        )

    def test_only_reference_pages_are_listed(self, tmp_path):
        root = _repo(
            tmp_path,
            {
                "a.md": _page("A"),
                "e.md": _page("E", page_type="explanation"),
                "h.md": _page("H", page_type="how-to"),
            },
            [{"Tab": ["a.md", "e.md", "h.md"]}, {"Other": ["e.md"]}],
        )
        assert _listed(root) == [("Tab", ["a.md"])]

    def test_page_directly_under_the_top_level_is_listed_on_its_own(
        self, tmp_path
    ):
        root = _repo(
            tmp_path,
            {"a.md": _page("A")},
            [{"Tab": [{"Alpha": "a.md"}]}],
        )
        assert _listed(root) == [("Tab", ["a.md"])]

    def test_top_level_page_is_its_own_section(self, tmp_path):
        root = _repo(tmp_path, {"a.md": _page("A")}, [{"Alpha": "a.md"}])
        assert _listed(root) == [("Alpha", ["a.md"])]

    def test_unlabelled_top_level_page_takes_its_title(self, tmp_path):
        root = _repo(tmp_path, {"a.md": _page("Alpha")}, ["a.md"])
        (section,) = lookup_sections(root)
        assert (section.label, section.entries[0].target) == ("Alpha", "a.md")

    @pytest.mark.parametrize(
        "nav",
        [
            [{"Tab": ["a.md", 7]}],
            [7, {"Tab": ["a.md"]}],
            [["a.md"]],
            [{"Tab": [["a.md"]]}],
        ],
    )
    def test_unreadable_nav_item_fails_rather_than_drops(self, tmp_path, nav):
        root = _repo(tmp_path, {"a.md": _page("A")}, nav)
        with pytest.raises(MetadataLoadError, match="cannot read"):
            lookup_sections(root)

    def test_external_links_are_not_sections(self, tmp_path):
        root = _repo(
            tmp_path,
            {"a.md": _page("A")},
            [{"Tab": ["a.md"]}, {"Elsewhere": "https://example.org/"}],
        )
        assert _listed(root) == [("Tab", ["a.md"])]

    def test_working_record_and_unbuilt_pages_are_not_listed(self, tmp_path):
        root = _repo(
            tmp_path,
            {
                "a.md": _page("A"),
                "draft-b.md": _page("B"),
                "adr/0001-x.md": "---\n---\n\n# X\n",
            },
            [{"Tab": ["a.md"]}],
            draft_docs="draft-*.md\n",
        )
        assert _listed(root) == [("Tab", ["a.md"])]


@pytest.mark.spec("DF-11-040")
class TestSubgroups:
    def test_nested_group_is_one_entry_through_the_outermost_index(
        self, tmp_path
    ):
        """A reference page two groups down is listed once, through the
        index of the outer group, not the inner one or the page itself."""
        root = _repo(
            tmp_path,
            {
                "spec/index.md": _page("Spec", page_type="routing"),
                "spec/part.md": _page("Part"),
                "spec/annex/index.md": _page("Annexes", page_type="routing"),
                "spec/annex/a.md": _page("Annex A"),
            },
            [
                {
                    "Tab": [
                        {
                            "Specification": [
                                "spec/index.md",
                                "spec/part.md",
                                {
                                    "Annexes": [
                                        "spec/annex/index.md",
                                        "spec/annex/a.md",
                                    ]
                                },
                            ]
                        }
                    ]
                }
            ],
        )
        (section,) = lookup_sections(root)
        (entry,) = section.entries
        assert (entry.label, entry.target) == (
            "Specification",
            "spec/index.md",
        )

    def test_group_without_an_index_lists_its_pages_on_their_own(
        self, tmp_path
    ):
        root = _repo(
            tmp_path,
            {"x.md": _page("X"), "y.md": _page("Y")},
            [{"Tab": [{"Loose": ["x.md", "y.md"]}]}],
        )
        assert _listed(root) == [("Tab", ["x.md", "y.md"])]

    def test_indexed_group_inside_an_unindexed_one_is_one_entry(
        self, tmp_path
    ):
        root = _repo(
            tmp_path,
            {
                "x.md": _page("X"),
                "m/index.md": _page("Messages", page_type="routing"),
                "m/rm.md": _page("RM"),
                "m/em.md": _page("EM"),
            },
            [
                {
                    "Tab": [
                        {
                            "Loose": [
                                "x.md",
                                {
                                    "Messages": [
                                        "m/index.md",
                                        "m/rm.md",
                                        "m/em.md",
                                    ]
                                },
                            ]
                        }
                    ]
                }
            ],
        )
        assert _listed(root) == [("Tab", ["x.md", "m/index.md"])]

    def test_group_holding_no_reference_page_is_not_listed(self, tmp_path):
        root = _repo(
            tmp_path,
            {
                "a.md": _page("A"),
                "g/index.md": _page("G", page_type="routing"),
                "g/e.md": _page("E", page_type="explanation"),
            },
            [{"Tab": ["a.md", {"G": ["g/index.md", "g/e.md"]}]}],
        )
        assert _listed(root) == [("Tab", ["a.md"])]

    def test_group_entry_shows_the_index_description(self, tmp_path):
        root = _repo(
            tmp_path,
            {
                "g/index.md": _page(
                    "G", page_type="routing", description="The whole set."
                ),
                "g/a.md": _page("A", description="One part."),
            },
            [{"Tab": [{"Group": ["g/index.md", "g/a.md"]}]}],
        )
        assert render_lookup(lookup_sections(root)) == (
            "## Tab\n\n- [Group](g/index.md) — The whole set."
        )


@pytest.mark.spec("DF-11-041")
class TestOmittedPages:
    def test_page_is_placed_in_the_group_its_index_opens(self, tmp_path):
        root = _repo(
            tmp_path,
            {
                "a.md": _page("A", page_type="explanation"),
                "g/index.md": _page("G", page_type="routing"),
                "g/e.md": _page("E", page_type="explanation"),
                "g/full.md": _page("Full"),
            },
            [{"Tab": ["a.md", {"G": ["g/index.md", "g/e.md"]}]}],
            not_in_nav="g/full.md\n",
        )
        assert _listed(root) == [("Tab", ["g/index.md"])]

    def test_page_beside_a_leaf_index_is_listed_on_its_own(self, tmp_path):
        """A leaf index directly under the top level opens no group, so the
        page it places is directly under the top level too."""
        root = _repo(
            tmp_path,
            {
                "s/index.md": _page("Stories", page_type="routing"),
                "s/one.md": _page("One"),
                "z.md": _page("Z"),
            },
            [{"Tab": [{"Stories": "s/index.md"}, "z.md"]}],
        )
        assert _listed(root) == [("Tab", ["s/one.md", "z.md"])]

    def test_page_placed_by_a_top_level_index_stays_in_its_section(
        self, tmp_path
    ):
        root = _repo(
            tmp_path,
            {
                "s/index.md": _page("Stories", page_type="routing"),
                "s/one.md": _page("One"),
                "z.md": _page("Z"),
            },
            [{"Stories": "s/index.md"}, {"Tab": ["z.md"]}],
        )
        assert _listed(root) == [("Stories", ["s/one.md"]), ("Tab", ["z.md"])]

    def test_page_whose_directory_index_is_not_in_the_nav_fails(
        self, tmp_path
    ):
        root = _repo(
            tmp_path,
            {
                "a.md": _page("A"),
                "old/index.md": _page("Old", page_type="routing"),
                "old/notation.md": _page("Notation"),
            },
            [{"Tab": ["a.md"]}],
        )
        with pytest.raises(MetadataLoadErrors) as exc:
            lookup_sections(root)
        (fault,) = exc.value.failures
        assert fault.path == "docs/old/notation.md"
        assert "old/index.md" in str(fault)

    def test_omitted_index_is_not_its_own_placement(self, tmp_path):
        root = _repo(
            tmp_path,
            {"a.md": _page("A"), "ns/index.md": _page("Namespace")},
            [{"Tab": ["a.md"]}],
        )
        with pytest.raises(MetadataLoadErrors) as exc:
            lookup_sections(root)
        assert [f.path for f in exc.value.failures] == ["docs/ns/index.md"]

    def test_every_unplaceable_page_is_reported(self, tmp_path):
        root = _repo(
            tmp_path,
            {
                "a.md": _page("A"),
                "x/one.md": _page("One"),
                "y/two.md": _page("Two"),
            },
            [{"Tab": ["a.md"]}],
        )
        with pytest.raises(MetadataLoadErrors) as exc:
            lookup_sections(root)
        assert sorted(str(f.path) for f in exc.value.failures) == [
            "docs/x/one.md",
            "docs/y/two.md",
        ]


class TestFaults:
    def test_entry_without_a_description_fails(self, tmp_path):
        root = _repo(
            tmp_path,
            {"a.md": _page("A", description=None)},
            [{"Tab": ["a.md"]}],
        )
        with pytest.raises(MetadataLoadErrors) as exc:
            lookup_sections(root)
        (fault,) = exc.value.failures
        assert fault.path == "docs/a.md"
        assert "description" in str(fault)

    def test_group_entry_checks_the_index_description(self, tmp_path):
        root = _repo(
            tmp_path,
            {
                "g/index.md": _page(
                    "G", page_type="routing", description=None
                ),
                "g/a.md": _page("A"),
            },
            [{"Tab": [{"G": ["g/index.md", "g/a.md"]}]}],
        )
        with pytest.raises(MetadataLoadErrors) as exc:
            lookup_sections(root)
        assert [f.path for f in exc.value.failures] == ["docs/g/index.md"]

    def test_no_reference_page_fails(self, tmp_path):
        root = _repo(
            tmp_path,
            {"a.md": _page("A", page_type="explanation")},
            [{"Tab": ["a.md"]}],
        )
        with pytest.raises(MetadataLoadError, match="DF-09-009"):
            lookup_sections(root)


@pytest.mark.spec("DF-11-042")
class TestLinks:
    def _hosts(self, tmp_path: Path, home: str, start: str) -> Path:
        return _repo(
            tmp_path,
            {
                HOME_PATH: home,
                "start/go.md": start,
                "_cards.md": f"[Look]({LOOKUP_PATH})\n",
            },
            [HOME_PATH],
        )

    def test_linking_pages_have_no_fault(self, tmp_path):
        root = self._hosts(
            tmp_path, "[Look](lookup.md)\n", "[Look](../lookup.md)\n"
        )
        assert lookup_link_faults(root, [HOME_PATH, "start/go.md"]) == []

    def test_each_page_missing_the_link_is_reported(self, tmp_path):
        root = self._hosts(tmp_path, "# Home\n", "# Go\n")
        faults = lookup_link_faults(root, [HOME_PATH, "start/go.md"])
        assert [f.path for f in faults] == [
            "docs/index.md",
            "docs/start/go.md",
        ]

    def test_link_in_a_whole_included_fragment_counts(self, tmp_path):
        root = self._hosts(
            tmp_path,
            '{% include-markdown "./_cards.md" %}\n',
            "[Look](../lookup.md)\n",
        )
        assert lookup_link_faults(root, [HOME_PATH]) == []


# ---------------------------------------------------------------------------
# The docs-site artifact: --check and --write
# ---------------------------------------------------------------------------

_LOOKUP = (
    "---\nstakeholder_type: ALL\nlevel: 200\npage_type: routing\n---\n\n"
    "# Look Something Up\n\nHand-written framing.\n\n"
    f"{BEGIN_MARKER}\n\n{END_MARKER}\n"
)

_HOME = (
    f"---\n{CONTENTS_KEY}: routing\nstakeholder_type: ALL\nlevel: 100\n"
    "page_type: routing\n---\n\n# Home\n\n[Look](lookup.md)\n"
)

_LANDING = (
    f"---\n{CONTENTS_KEY}: generated\nstakeholder_type: ALL\nlevel: 200\n"
    "page_type: routing\n---\n\n# Guides\n\n"
    f"{LANDING_BEGIN}\n\n{LANDING_END}\n"
)


@pytest.fixture
def site(tmp_path: Path) -> Path:
    """A tree every docs-site artifact resolves in, written once: the home
    page, the lookup page, one start page and one generated landing page."""
    start = start_page("Go", [stage("Read", "set", "guides/a.md")])
    root = _repo(
        tmp_path,
        {
            HOME_PATH: _HOME,
            LOOKUP_PATH: _LOOKUP,
            "start/go.md": start,
            "guides/index.md": _LANDING,
            "guides/a.md": _page("A", page_type="how-to"),
            "guides/ref.md": _page("Ref", description="First wording."),
        },
        [
            {"Home": [HOME_PATH, {"Look Something Up": LOOKUP_PATH}]},
            {"Go": ["start/go.md"]},
            {"Guides": ["guides/index.md", "guides/a.md", "guides/ref.md"]},
        ],
    )
    site_sync.write_artifacts(root)
    assert site_sync.stale_artifacts(root) == []
    return root


@pytest.mark.spec("DF-11-042")
class TestLookupArtifact:
    def test_write_fills_the_listing_and_keeps_the_framing(self, site):
        text = (site / "docs" / LOOKUP_PATH).read_text()
        assert "Hand-written framing." in text
        assert "- [Ref](guides/ref.md) — First wording." in text

    def test_hand_edit_is_stale_and_write_repairs_it(self, site):
        lookup = site / "docs" / LOOKUP_PATH
        lookup.write_text(lookup.read_text().replace("First", "Hand"))
        assert site_sync.stale_artifacts(site) == [f"docs/{LOOKUP_PATH}"]
        assert site_sync.write_artifacts(site) == [f"docs/{LOOKUP_PATH}"]
        assert site_sync.stale_artifacts(site) == []

    def test_changed_description_is_stale(self, site):
        ref = site / "docs/guides/ref.md"
        ref.write_text(ref.read_text().replace("First", "Second"))
        assert f"docs/{LOOKUP_PATH}" in site_sync.stale_artifacts(site)
        site_sync.write_artifacts(site)
        assert "— Second wording." in (site / "docs" / LOOKUP_PATH).read_text()

    def test_new_reference_page_is_stale(self, site):
        (site / "docs/guides/new.md").write_text(_page("New"))
        nav = yaml.safe_load((site / "mkdocs.yml").read_text())
        nav["nav"][2]["Guides"].append("guides/new.md")
        (site / "mkdocs.yml").write_text(yaml.safe_dump(nav))
        assert f"docs/{LOOKUP_PATH}" in site_sync.stale_artifacts(site)
        site_sync.write_artifacts(site)
        assert (
            "- [New](guides/new.md)"
            in (site / "docs" / LOOKUP_PATH).read_text()
        )

    def test_check_exits_nonzero_when_stale(self, site, monkeypatch, capsys):
        lookup = site / "docs" / LOOKUP_PATH
        lookup.write_text(lookup.read_text().replace("First", "Hand"))
        monkeypatch.setattr(site_sync, "repo_root", lambda: site)
        with pytest.raises(SystemExit) as exc:
            site_sync.main(["--check"])
        assert exc.value.code == 1
        assert f"docs/{LOOKUP_PATH} is stale" in capsys.readouterr().err

    @pytest.mark.parametrize(
        "host, text",
        [
            ("docs/index.md", "[Look](lookup.md)\n"),
            ("docs/start/go.md", LOOKUP_LINK),
        ],
    )
    def test_check_fails_when_a_host_drops_the_link(
        self, site, monkeypatch, capsys, host, text
    ):
        page = site / host
        page.write_text(page.read_text().replace(text, ""))
        monkeypatch.setattr(site_sync, "repo_root", lambda: site)
        with pytest.raises(SystemExit) as exc:
            site_sync.main(["--check"])
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert host in err and "lookup.md" in err
        with pytest.raises(MetadataLoadErrors):
            site_sync.write_artifacts(site)


def _nav_group(root: Path, index: str) -> list[object]:
    """The committed nav group that *index* opens."""

    def find(items: object) -> list[object] | None:
        if isinstance(items, dict):
            return next(
                (g for v in items.values() if (g := find(v)) is not None),
                None,
            )
        if isinstance(items, list):
            if items and items[0] == index:
                return items
            return next((g for i in items if (g := find(i)) is not None), None)
        return None

    group = find(mkdocs_config(root).get("nav"))
    assert group is not None, index
    return group


class TestOneRunReportsEveryFault:
    def test_placement_and_link_faults_are_reported_together(self, site):
        """An author fixing by hand sees every finding in one run
        (EH-07-001), not one batch per check."""
        (site / "docs/orphan").mkdir()
        (site / "docs/orphan/old.md").write_text(_page("Old"))
        start = site / "docs/start/go.md"
        start.write_text(start.read_text().replace(LOOKUP_LINK, ""))
        with pytest.raises(MetadataLoadErrors) as exc:
            site_sync.stale_artifacts(site)
        assert {str(f.path) for f in exc.value.failures} == {
            "docs/orphan/old.md",
            "docs/start/go.md",
        }

    def test_empty_target_set_and_link_faults_are_reported_together(
        self, site
    ):
        """A single lookup fault (DF-09-009) does not hide the link faults
        already collected (EH-07-001)."""
        ref = site / "docs/guides/ref.md"
        ref.write_text(_page("Ref", page_type="how-to", description="Gone."))
        start = site / "docs/start/go.md"
        start.write_text(start.read_text().replace(LOOKUP_LINK, ""))
        with pytest.raises(MetadataLoadErrors) as exc:
            site_sync.stale_artifacts(site)
        assert {str(f.path) for f in exc.value.failures} == {
            "docs/",
            "docs/start/go.md",
        }

    def test_home_page_routing_to_the_lookup_page_is_reported_once(self, site):
        home = site / "docs/index.md"
        home.write_text(home.read_text().replace("[Look](lookup.md)\n", ""))
        with pytest.raises(MetadataLoadErrors) as exc:
            site_sync.stale_artifacts(site)
        assert [str(f.path) for f in exc.value.failures] == ["docs/index.md"]


class TestCommittedLookupPage:
    @pytest.mark.spec("DF-11-040")
    def test_subgroups_are_one_entry_each(self):
        """The specification parts, the message pages, Formal Protocol, the
        scenario narratives and the crosswalks are one entry each (AC-3):
        each group's index is listed once and none of its members is."""
        root = repo_root()
        targets = [
            entry.target
            for section in lookup_sections(root)
            for entry in section.entries
        ]
        for index in (
            "reference/vultron-spec/index.md",
            "reference/messages/index.md",
            "reference/formal_protocol/index.md",
            "topics/scenarios/index.md",
            "reference/iso_crosswalks/index.md",
        ):
            members = set(walk_nav(_nav_group(root, index))) - {index}
            assert members, index
            assert targets.count(index) == 1
            assert not members & set(targets), index

    def test_home_and_every_start_page_link_the_lookup_page(self):
        root = repo_root()
        starts = sorted(
            rel
            for rel in (
                p.relative_to(root / "docs").as_posix()
                for p in (root / "docs/start").glob("*.md")
            )
            if is_start_page(rel)
        )
        hosts = [HOME_PATH, *starts]
        assert len(hosts) >= 5
        assert lookup_link_faults(root, hosts) == []
