"""Tests for the advisory docs duplicate finder (SG-43, DF-10-002, DF-09-009)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from vultron.metadata.docs import duplicates
from vultron.metadata.docs.duplicates import (
    GENERATED_FILE_MARKER,
    Paragraph,
    duplicate_report,
    find_clusters,
    format_cluster,
    paragraphs,
    sentences,
)
from vultron.metadata.file_loading import MetadataLoadError

FRONTMATTER = (
    "---\nstakeholder_type: [cvd-practitioner]\nlevel: 200\n"
    "page_type: explanation\n---\n"
)

SHARED = (
    "Every participant keeps its own copy of the case and applies each "
    "ledger entry the case manager sends. The copies stay in agreement "
    "because each one replays the same entries in the same order."
)
# Two of three sentences shared, the third reworded: Jaccard 2/4 = 0.5.
DRIFTED_A = (
    "The case manager commits every change to the case as a ledger entry. "
    "Each participant replays those entries in the order they were committed. "
    "A replica that misses an entry asks the case manager to send it again."
)
DRIFTED_B = (
    "The case manager commits every change to the case as a ledger entry. "
    "Each participant replays those entries in the order they were committed. "
    "A replica that falls behind requests the missing entries from the manager."
)
# One sentence of three shared with DRIFTED_A: Jaccard 1/5, below threshold.
UNRELATED = (
    "The case manager commits every change to the case as a ledger entry. "
    "Embargo proposals are relayed to every invited participant at once. "
    "A participant may answer the proposal with an accept or a reject."
)
_S = [
    "The first sentence names the case manager and its single role.",
    "The second sentence says every change becomes a ledger entry.",
    "The third sentence says each replica replays the entries in order.",
    "The fourth sentence says a lagging replica asks for what it missed.",
    "The fifth sentence says the manager answers that request at once.",
]
# A~B and B~C at 2/4 each; A and C share one sentence of five (1/5).
CHAIN_A = " ".join(_S[0:3])
CHAIN_B = " ".join(_S[1:4])
CHAIN_C = " ".join(_S[2:5])
FRAGMENT_TEXT = (
    "This block is sourced once from an include fragment, so every page "
    "that renders it shows the same words and an edit lands everywhere."
)


def page(*blocks: str, title: str = "Page") -> str:
    return FRONTMATTER + f"# {title}\n\n" + "\n\n".join(blocks) + "\n"


def make_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    nav = sorted(
        rel for rel in files if not rel.rsplit("/", 1)[-1].startswith("_")
    )
    (tmp_path / "mkdocs.yml").write_text(yaml.safe_dump({"nav": nav}))
    for rel, text in files.items():
        path = tmp_path / "docs" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


def clusters_by_kind(root: Path) -> dict[str, list[tuple[str, ...]]]:
    found: dict[str, list[tuple[str, ...]]] = {"exact": [], "drifted": []}
    for cluster in duplicate_report(root).clusters:
        found[cluster.kind].append(cluster.files)
    return found


class TestDuplicateReport:
    def test_exact_pair_is_one_exact_cluster(self, tmp_path):
        root = make_repo(
            tmp_path,
            {"topics/a.md": page(SHARED), "howto/b.md": page(SHARED)},
        )
        assert clusters_by_kind(root) == {
            "exact": [("howto/b.md", "topics/a.md")],
            "drifted": [],
        }

    def test_exact_copy_survives_rewrapping(self, tmp_path):
        rewrapped = SHARED.replace(" the case ", "\nthe case\n")
        root = make_repo(
            tmp_path,
            {"topics/a.md": page(SHARED), "howto/b.md": page(rewrapped)},
        )
        assert clusters_by_kind(root)["exact"] == [
            ("howto/b.md", "topics/a.md")
        ]

    def test_drifted_pair_at_threshold_is_one_drifted_cluster(self, tmp_path):
        root = make_repo(
            tmp_path,
            {"topics/a.md": page(DRIFTED_A), "topics/b.md": page(DRIFTED_B)},
        )
        report = duplicate_report(root)
        assert [(c.kind, c.files) for c in report.clusters] == [
            ("drifted", ("topics/a.md", "topics/b.md"))
        ]
        assert [v.text for v in report.clusters[0].variants] == sorted(
            [DRIFTED_A, DRIFTED_B]
        )

    def test_pair_below_threshold_is_not_reported(self, tmp_path):
        root = make_repo(
            tmp_path,
            {"topics/a.md": page(DRIFTED_A), "topics/b.md": page(UNRELATED)},
        )
        assert duplicate_report(root).clusters == ()

    def test_higher_threshold_drops_the_drifted_pair(self, tmp_path):
        root = make_repo(
            tmp_path,
            {"topics/a.md": page(DRIFTED_A), "topics/b.md": page(DRIFTED_B)},
        )
        assert duplicate_report(root, threshold=0.75).clusters == ()

    def test_fragment_hosted_block_is_not_reported(self, tmp_path):
        include = '{% include-markdown "./_shared.md" %}'
        root = make_repo(
            tmp_path,
            {
                "topics/_shared.md": FRAGMENT_TEXT + "\n",
                "topics/a.md": page(include),
                "topics/b.md": page(include),
            },
        )
        report = duplicate_report(root)
        assert report.clusters == ()
        assert report.pages == 2

    def test_exact_variant_of_a_drifted_cluster_is_reported_once(
        self, tmp_path
    ):
        root = make_repo(
            tmp_path,
            {
                "topics/a.md": page(DRIFTED_A),
                "topics/b.md": page(DRIFTED_A),
                "topics/c.md": page(DRIFTED_B),
            },
        )
        report = duplicate_report(root)
        assert [c.kind for c in report.clusters] == ["drifted"]
        hosts = {
            v.text: [h.path for h in v.hosts]
            for v in report.clusters[0].variants
        }
        assert hosts == {
            DRIFTED_A: ["topics/a.md", "topics/b.md"],
            DRIFTED_B: ["topics/c.md"],
        }

    def test_repeat_within_one_page_is_not_a_cross_page_copy(self, tmp_path):
        root = make_repo(tmp_path, {"topics/a.md": page(SHARED, SHARED)})
        assert duplicate_report(root).clusters == ()

    @pytest.mark.parametrize(
        "skipped",
        [
            "adr/0001-decision.md",
            "reference/code/module.md",
            "reference/case_states/state.md",
            "topics/states_table.md",
            "topics/flow_diagram.md",
            "_acronyms/index.md",
            "ns/vocab.md",
            "reference/behaviors/tree.md",
            "reference/codebase/STRUCTURE.md",
            "reference/user_stories/story_2022_001.md",
        ],
    )
    def test_skipped_content_class_is_not_read(self, tmp_path, skipped):
        root = make_repo(
            tmp_path, {"topics/a.md": page(SHARED), skipped: page(SHARED)}
        )
        report = duplicate_report(root)
        assert report.clusters == ()
        assert report.pages == 1

    def test_generated_page_is_not_read(self, tmp_path):
        generated = page(GENERATED_FILE_MARKER, SHARED)
        root = make_repo(
            tmp_path,
            {"topics/a.md": page(SHARED), "reference/gen.md": generated},
        )
        assert duplicate_report(root).clusters == ()

    def test_generated_section_is_not_read(self, tmp_path):
        section = (
            "<!-- BEGIN GENERATED SECTION CONTENTS — do not edit -->\n"
            f"{SHARED}\n"
            "<!-- END GENERATED SECTION CONTENTS -->"
        )
        root = make_repo(
            tmp_path,
            {"topics/a.md": page(SHARED), "topics/index.md": page(section)},
        )
        assert duplicate_report(root).clusters == ()

    def test_underscore_page_is_not_read(self, tmp_path):
        # Included with ``start=``, so classify_docs_tree keeps it a page.
        include = '{% include-markdown "./_partial.md" start="<!-- s -->" %}'
        root = make_repo(
            tmp_path,
            {
                "topics/_partial.md": "<!-- s -->\n\n" + SHARED + "\n",
                "topics/a.md": page(SHARED),
                "topics/b.md": page(include),
            },
        )
        assert duplicate_report(root).clusters == ()

    def test_chained_drift_is_one_cluster(self, tmp_path):
        root = make_repo(
            tmp_path,
            {
                "topics/a.md": page(CHAIN_A),
                "topics/b.md": page(CHAIN_B),
                "topics/c.md": page(CHAIN_C),
            },
        )
        report = duplicate_report(root)
        assert [(c.kind, c.files) for c in report.clusters] == [
            ("drifted", ("topics/a.md", "topics/b.md", "topics/c.md"))
        ]

    def test_frontmatter_is_not_read(self, tmp_path):
        def described() -> str:
            return f"---\ndescription: >\n  {SHARED}\n---\n# Page\n"

        root = make_repo(
            tmp_path, {"topics/a.md": described(), "topics/b.md": described()}
        )
        assert duplicate_report(root).clusters == ()

    def test_frontmatter_of_a_bodiless_page_is_not_read(self, tmp_path):
        described = f"---\ndescription: >\n  {SHARED}\n---\n"
        root = make_repo(
            tmp_path, {"topics/a.md": described, "topics/b.md": described}
        )
        assert duplicate_report(root).clusters == ()

    def test_html_comment_is_not_read(self, tmp_path):
        comment = f"<!--\n{SHARED}\n-->"
        root = make_repo(
            tmp_path,
            {"topics/a.md": page(comment), "topics/b.md": page(comment)},
        )
        assert duplicate_report(root).clusters == ()

    def test_short_paragraph_threshold_is_configurable(self, tmp_path):
        short = "A copied pointer to the index page, shared by two pages."
        root = make_repo(
            tmp_path, {"topics/a.md": page(short), "topics/b.md": page(short)}
        )
        assert duplicate_report(root).clusters == ()
        (cluster,) = duplicate_report(root, min_chars=20).clusters
        assert cluster.kind == "exact"

    def test_missing_docs_directory_fails(self, tmp_path):
        with pytest.raises(MetadataLoadError, match="DF-09-009") as info:
            duplicate_report(tmp_path)
        assert info.value.path == "docs"

    def test_empty_target_set_fails(self, tmp_path):
        root = make_repo(tmp_path, {"adr/0001-decision.md": page(SHARED)})
        with pytest.raises(MetadataLoadError, match="no target page") as info:
            duplicate_report(root)
        assert info.value.path == "docs"


class TestParagraphs:
    def test_fenced_code_is_not_a_paragraph(self):
        text = page(f"```text\n{SHARED}\n```")
        assert list(paragraphs(text, "a.md")) == []

    def test_short_paragraph_is_skipped(self):
        assert (
            list(paragraphs(page("See the index for details."), "a.md")) == []
        )

    def test_heading_is_not_part_of_a_paragraph(self):
        text = page(f"## Section\n{SHARED}")
        (found,) = paragraphs(text, "a.md")
        assert found.text == SHARED

    def test_heading_ends_the_paragraph_before_it(self):
        text = page(f"{SHARED}\n## Section\n{DRIFTED_A}")
        assert [p.text for p in paragraphs(text, "a.md")] == [
            SHARED,
            DRIFTED_A,
        ]

    @pytest.mark.parametrize("underline", ["=====", "-----"])
    def test_setext_heading_ends_the_paragraph_before_it(self, underline):
        text = page(f"{SHARED}\n\nSection title\n{underline}\n{DRIFTED_A}")
        assert [p.text for p in paragraphs(text, "a.md")] == [
            SHARED,
            DRIFTED_A,
        ]

    def test_thematic_break_ends_the_paragraph_before_it(self):
        text = page(f"{SHARED}\n\n---\n{DRIFTED_A}")
        assert [p.text for p in paragraphs(text, "a.md")] == [
            SHARED,
            DRIFTED_A,
        ]

    def test_comment_marker_inside_a_fence_is_code(self):
        text = page(SHARED, "```html\n<!-- unclosed\n```", DRIFTED_A, "-->")
        assert [p.text for p in paragraphs(text, "a.md")] == [
            SHARED,
            DRIFTED_A,
        ]

    def test_directive_marker_inside_a_fence_is_code(self):
        text = page(SHARED, "```jinja\n{% if x\n```", DRIFTED_A, "%}")
        assert [p.text for p in paragraphs(text, "a.md")] == [
            SHARED,
            DRIFTED_A,
        ]

    def test_line_is_the_paragraph_start_in_the_file(self):
        text = page(SHARED)
        (found,) = paragraphs(text, "a.md")
        assert text.splitlines()[found.line - 1] == SHARED


class TestSentences:
    def test_case_and_punctuation_are_dropped(self):
        assert sentences("The Case Manager, alone, commits each entry!") == {
            "the case manager alone commits each entry"
        }

    def test_short_sentence_cannot_link_paragraphs(self):
        assert sentences(
            "See below. The case manager commits each entry in order."
        ) == {"the case manager commits each entry in order"}


@pytest.fixture
def scored(monkeypatch) -> list[tuple[frozenset[str], frozenset[str]]]:
    """Every pair of sentence sets the clusterer scores, in call order."""
    calls: list[tuple[frozenset[str], frozenset[str]]] = []
    real = duplicates._overlap

    def spy(left: frozenset[str], right: frozenset[str]) -> float:
        calls.append((left, right))
        return real(left, right)

    monkeypatch.setattr(duplicates, "_overlap", spy)
    return calls


class TestFindClusters:
    """Drifted candidates come from the sentence index, never all pairs (AC-2)."""

    def test_paragraphs_sharing_no_sentence_are_never_scored(self, scored):
        found = [
            Paragraph(
                f"p{n}.md",
                1,
                f"Paragraph number {n} talks about topic {n} only.",
            )
            for n in range(50)
        ]
        assert find_clusters(found) == ()
        assert scored == []

    def test_only_paragraphs_sharing_a_sentence_are_scored(self, scored):
        found = [
            Paragraph("a.md", 1, DRIFTED_A),
            Paragraph("b.md", 1, DRIFTED_B),
            *(
                Paragraph(
                    f"p{n}.md",
                    1,
                    f"Paragraph number {n} talks about topic {n}.",
                )
                for n in range(20)
            ),
        ]
        assert [c.kind for c in find_clusters(found)] == ["drifted"]
        assert len(scored) == 1


def test_format_cluster_names_every_host_and_wording():
    hosts = (Paragraph("a.md", 3, SHARED), Paragraph("b.md", 9, SHARED))
    (cluster,) = find_clusters(hosts)
    assert format_cluster(cluster).splitlines() == [
        "exact copy across 2 pages:",
        "  docs/a.md:3",
        "  docs/b.md:9",
        f"    > {SHARED}",
    ]


def test_main_exits_zero_when_it_reports_clusters(
    tmp_path, monkeypatch, capsys
):
    root = make_repo(
        tmp_path, {"topics/a.md": page(SHARED), "howto/b.md": page(SHARED)}
    )
    monkeypatch.setattr(duplicates, "_find_repo_root", lambda: root)
    duplicates.main([])
    out = capsys.readouterr().out
    assert "exact copy across 2 pages:" in out
    assert out.rstrip().endswith(
        "1 cluster(s) of repeated paragraphs (1 exact, 0 drifted) across "
        "2 page(s); advisory, see SG-43."
    )


def test_main_fails_distinctly_on_an_empty_target_set(
    tmp_path, monkeypatch, capsys
):
    root = make_repo(tmp_path, {"adr/0001-decision.md": page(SHARED)})
    monkeypatch.setattr(duplicates, "_find_repo_root", lambda: root)
    with pytest.raises(SystemExit) as info:
        duplicates.main([])
    assert info.value.code == 1
    assert "docs-duplicates resolved no target page" in capsys.readouterr().err


@pytest.mark.parametrize("value", ["0", "1.5", "-0.2", "half"])
def test_threshold_outside_unit_interval_is_refused(value):
    with pytest.raises(SystemExit) as info:
        duplicates.main(["--threshold", value])
    assert info.value.code == 2


@pytest.mark.parametrize("value", ["0", "-5", "1.5", "many"])
def test_min_chars_below_one_or_not_an_integer_is_refused(value):
    with pytest.raises(SystemExit) as info:
        duplicates.main(["--min-chars", value])
    assert info.value.code == 2
