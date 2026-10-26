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
)

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

    def test_empty_target_set_fails(self, tmp_path):
        root = make_repo(tmp_path, {"adr/0001-decision.md": page(SHARED)})
        with pytest.raises(ValueError, match="no target pages resolved"):
            duplicate_report(root)


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

    def test_line_is_the_paragraph_start_in_the_file(self):
        text = page(SHARED)
        (found,) = paragraphs(text, "a.md")
        assert text.splitlines()[found.line - 1] == SHARED


_real_sentences = duplicates.sentences


@pytest.fixture
def scored(monkeypatch) -> list[tuple[frozenset[str], frozenset[str]]]:
    """Every pair of sentence sets the clusterer intersects, in call order."""
    calls: list[tuple[frozenset[str], frozenset[str]]] = []

    class Spy(frozenset):
        def __and__(self, other):
            calls.append((self, other))
            return frozenset(self).__and__(other)

    monkeypatch.setattr(
        duplicates, "sentences", lambda t: Spy(_real_sentences(t))
    )
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
    assert (
        "docs-duplicates: no target pages resolved" in capsys.readouterr().err
    )


@pytest.mark.parametrize("value", ["0", "1.5", "-0.2"])
def test_threshold_outside_unit_interval_is_refused(value):
    with pytest.raises(SystemExit):
        duplicates.main(["--threshold", value])
