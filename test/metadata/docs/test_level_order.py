"""Tests for the check that no ``docs/`` page depends above its own level.

Requirements: DF-11-002 (the rule), DF-11-003/DF-11-012 (working record is
unleveled), DF-11-010 (fragments take their hosts' levels), DF-09-009 (an empty
target set fails); findings are attributed per MS-17-001.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from vultron.metadata.base import repo_root
from vultron.metadata.docs import level_order
from vultron.metadata.docs.concept_scan import (
    first_use,
    scan_page,
    term_forms,
)
from vultron.metadata.docs.level_order import (
    check_level_order,
    main,
    prune_baseline,
    read_baseline,
    write_baseline,
)
from vultron.metadata.file_loading import (
    MetadataLoadError,
    MetadataLoadErrors,
)
from vultron.metadata.markdown_tables import fenced_lines

_GLOSSARY = """\
---
stakeholder_type: [project-contributor]
level: 300
---
# Glossary

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Case Ledger Entry** | A committed entry | Log item |
| **CASE_MANAGER** | The role that commits | — |
| **Coordinated Vulnerability Disclosure (CVD)** | The process | — |
| **V/v** | Vendor awareness | — |
"""


def _page(
    level: int | None = 300,
    body: str = "# Page\n",
    *,
    audience: str = "[cvd-practitioner]",
    introduces: str | None = None,
) -> str:
    lines = [f"stakeholder_type: {audience}"]
    if level is not None:
        lines.append(f"level: {level}")
    if introduces is not None:
        lines.append(f"introduces: {introduces}")
    return "---\n" + "\n".join(lines) + "\n---\n" + body


_LEDGER = _page(400, "# Ledger\n", introduces="[Case Ledger Entry]")


def _repo(tmp_path: Path, files: dict[str, str], nav=None) -> Path:
    """A checkout with a glossary, the 400-level ledger page, and *files*."""
    tree = {
        "reference/glossary.md": _GLOSSARY,
        "topics/ledger.md": _LEDGER,
        **files,
    }
    (tmp_path / "mkdocs.yml").write_text(
        yaml.safe_dump({"nav": nav if nav is not None else sorted(tree)})
    )
    for rel, text in tree.items():
        path = tmp_path / "docs" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


def _passes(root: Path) -> None:
    """The check raises nothing and tolerates nothing: *root* is compliant."""
    assert check_level_order(root, baseline={}).baselined == []


def _failures(root: Path, baseline=None) -> tuple[MetadataLoadError, ...]:
    with pytest.raises(MetadataLoadErrors) as info:
        check_level_order(root, baseline={} if baseline is None else baseline)
    return info.value.failures


# ---------------------------------------------------------------------------
# The rule (AC-1, AC-2, AC-3, AC-6a)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DF-11-002")
class TestRule:
    def test_compliant_page_passes(self, tmp_path):
        """A page using no higher-level concept depends on nothing above it."""
        root = _repo(tmp_path, {"howto/a.md": _page(300, "# A\n\nPlain.\n")})

        result = check_level_order(root, baseline={})

        assert result.leveled_pages == 3
        assert result.introductions == 1
        assert result.baselined == []

    def test_unlinked_upward_dependency_fails_at_its_first_use(self, tmp_path):
        body = "# A\n\nFirst line.\nEach case ledger entry is signed.\n"
        root = _repo(tmp_path, {"howto/a.md": _page(300, body)})

        (failure,) = _failures(root)

        # Frontmatter is four lines, so the body's fourth line is line 8.
        assert failure.location == "docs/howto/a.md:8:6"
        assert "docs/topics/ledger.md introduces at level 400" in str(failure)
        assert "this page is at 300" in str(failure)

    def test_link_at_first_use_satisfies_the_rule(self, tmp_path):
        """SG-11: the cross-page concept edge is a hyperlink (AC-2)."""
        body = (
            "# A\n\nEach [case ledger entry](../topics/ledger.md) is signed.\n"
        )
        root = _repo(tmp_path, {"howto/a.md": _page(300, body)})

        _passes(root)

    def test_earlier_link_satisfies_the_rule(self, tmp_path):
        body = (
            "# A\n\nRead [the ledger](../topics/ledger.md#entries) first.\n\n"
            "Each case ledger entry is signed.\n"
        )
        root = _repo(tmp_path, {"howto/a.md": _page(300, body)})

        _passes(root)

    def test_link_after_first_use_does_not(self, tmp_path):
        """A link below the first use leaves that use a forward reference."""
        body = (
            "# A\n\nEach case ledger entry is signed.\n\n"
            "See [the ledger](../topics/ledger.md).\n"
        )
        root = _repo(tmp_path, {"howto/a.md": _page(300, body)})

        (failure,) = _failures(root)
        assert failure.line == 7

    def test_link_to_another_page_does_not_satisfy(self, tmp_path):
        body = "# A\n\nEach [case ledger entry](b.md).\n"
        root = _repo(
            tmp_path, {"howto/a.md": _page(300, body), "howto/b.md": _page()}
        )

        assert len(_failures(root)) == 1

    def test_glossary_link_at_first_use_satisfies_the_rule(self, tmp_path):
        """SG-11 names the glossary entry as a canonical introduction too."""
        body = (
            "# A\n\nEach [case ledger entry](../reference/glossary.md#l) "
            "is signed.\n"
        )
        root = _repo(tmp_path, {"howto/a.md": _page(300, body)})

        _passes(root)

    def test_glossary_link_elsewhere_does_not(self, tmp_path):
        """Only the introducer's link reaches forward; a glossary link names
        the one term it wraps."""
        body = (
            "# A\n\nSee [the glossary](../reference/glossary.md).\n"
            "Each case ledger entry is signed.\n"
        )
        root = _repo(tmp_path, {"howto/a.md": _page(300, body)})

        assert len(_failures(root)) == 1

    @pytest.mark.parametrize(
        "body",
        [
            "Each [case ledger entry][cle] is signed.\n\n"
            "[cle]: ../topics/ledger.md\n",
            "Each [case ledger entry][] is signed.\n\n"
            "[Case Ledger Entry]: ../topics/ledger.md\n",
            "Each [case ledger\nentry](../topics/ledger.md) is signed.\n",
            'Each <a href="../topics/ledger.md">case ledger entry</a>.\n',
        ],
        ids=["reference", "collapsed-reference", "wrapped-text", "anchor"],
    )
    def test_every_link_form_satisfies_the_rule(self, tmp_path, body):
        root = _repo(tmp_path, {"howto/a.md": _page(300, "# A\n\n" + body)})

        _passes(root)

    def test_reference_definition_alone_is_not_a_link(self, tmp_path):
        """An unused definition links nothing, however early it appears."""
        body = (
            "# A\n\n[cle]: ../topics/ledger.md\n\n"
            "Each case ledger entry is signed.\n"
        )
        root = _repo(tmp_path, {"howto/a.md": _page(300, body)})

        assert len(_failures(root)) == 1

    def test_hyphenated_and_wrapped_uses_are_found(self, tmp_path):
        body = "# A\n\nEach case-ledger\nentry is signed.\n"
        root = _repo(tmp_path, {"howto/a.md": _page(300, body)})

        (failure,) = _failures(root)

        assert failure.location == "docs/howto/a.md:7:6"
        assert 'uses "case-ledger entry"' in failure.detail

    @pytest.mark.parametrize("level", [400, 500])
    def test_same_or_higher_level_page_is_compliant(self, tmp_path, level):
        body = "# A\n\nEach case ledger entry is signed.\n"
        root = _repo(tmp_path, {"howto/a.md": _page(level, body)})

        _passes(root)

    def test_comparison_is_site_wide_not_per_audience(self, tmp_path):
        """One ladder: a cross-audience dependency is still ordered (AC-6a)."""
        body = "# A\n\nEach case ledger entry is signed.\n"
        root = _repo(
            tmp_path,
            {"howto/a.md": _page(300, body, audience="[process-researcher]")},
        )

        assert len(_failures(root)) == 1

    def test_every_violation_is_reported(self, tmp_path):
        body = "# A\n\nEach case ledger entry is signed.\n"
        root = _repo(
            tmp_path,
            {"howto/a.md": _page(300, body), "howto/b.md": _page(200, body)},
        )

        assert {f.path for f in _failures(root)} == {
            "docs/howto/a.md",
            "docs/howto/b.md",
        }

    def test_glossary_defines_its_terms_and_is_not_scanned(self, tmp_path):
        """The registry at 300 lists a 400-level term without depending on it."""
        root = _repo(tmp_path, {})

        _passes(root)


# ---------------------------------------------------------------------------
# Skipped pages and fragments (AC-6, DF-11-010)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DF-11-002")
class TestTargetSet:
    def test_working_record_page_is_skipped_not_level_zero(self, tmp_path):
        """A level-0 reading would flag this page; it carries no level."""
        body = "# ADR\n\nEach case ledger entry is signed.\n"
        root = _repo(
            tmp_path,
            {
                "adr/0001-x.md": _page(
                    None, body, audience="[project-contributor]"
                )
            },
        )

        result = check_level_order(root, baseline={})

        assert result.unleveled_pages == 1
        assert result.leveled_pages == 2

    def test_undeclared_page_is_skipped(self, tmp_path):
        body = "---\ntitle: T\n---\nEach case ledger entry is signed.\n"
        root = _repo(tmp_path, {"howto/a.md": body})

        assert check_level_order(root, baseline={}).unleveled_pages == 1

    def test_fragment_is_checked_at_its_lowest_hosts_level(self, tmp_path):
        host = '# H\n\n{% include-markdown "./_frag.md" %}\n'
        root = _repo(
            tmp_path,
            {
                "howto/_frag.md": "Each case ledger entry is signed.\n",
                "howto/low.md": _page(200, host),
                "howto/high.md": _page(400, host),
            },
            nav=["howto/low.md", "howto/high.md", "topics/ledger.md"],
        )

        (failure,) = _failures(root)

        assert failure.location == "docs/howto/_frag.md:1:6"
        assert "lowest host (howto/low.md) is at 200" in str(failure)

    @pytest.mark.parametrize(
        "body",
        [
            "```text\ncase ledger entry\n```\n",
            "~~~~\ncase ledger entry\n~~~~\n",
            "Use `case ledger entry` here.\n",
            "<!-- case ledger entry -->\n",
            "[x](https://example.org/case-ledger-entry)\n",
            "[x]: ../case ledger entry.md\n",
            "<code>case ledger entry</code>\n",
            "!!! note\n\n    ```text\n    case ledger entry\n    ```\n",
        ],
        ids=[
            "backtick-fence",
            "tilde-fence",
            "inline",
            "comment",
            "url",
            "ref",
            "code-element",
            "admonition-fence",
        ],
    )
    def test_non_prose_is_not_a_use(self, tmp_path, body):
        root = _repo(tmp_path, {"howto/a.md": _page(300, "# A\n\n" + body)})

        _passes(root)

    def test_empty_target_set_fails(self, tmp_path):
        """DF-09-009: resolving no leveled page is a failure (AC-5)."""
        (tmp_path / "mkdocs.yml").write_text("nav: []\n")
        glossary = tmp_path / "docs" / "reference" / "glossary.md"
        glossary.parent.mkdir(parents=True)
        glossary.write_text(_GLOSSARY.replace("level: 300", ""))

        with pytest.raises(MetadataLoadError, match="no leveled page"):
            check_level_order(tmp_path, baseline={})

    def test_no_introduced_concept_fails(self, tmp_path):
        """A tree declaring no concept would pass vacuously (DF-09-009)."""
        root = _repo(tmp_path, {"topics/ledger.md": _page(400)})

        with pytest.raises(MetadataLoadError, match="no page declares"):
            check_level_order(root, baseline={})

    def test_missing_glossary_fails(self, tmp_path):
        root = _repo(tmp_path, {})
        (root / "docs" / "reference" / "glossary.md").unlink()

        with pytest.raises(MetadataLoadError, match="glossary.*is missing"):
            check_level_order(root, baseline={})


# ---------------------------------------------------------------------------
# ``introduces:`` declarations
# ---------------------------------------------------------------------------


@pytest.mark.spec("DF-11-002")
class TestIntroduces:
    @pytest.mark.parametrize(
        ("value", "message"),
        [
            ("Case Ledger Entry", "non-empty list"),
            ("[]", "non-empty list"),
            ("[Case Ledger Entry, Case Ledger Entry]", "more than once"),
            ("[Ledger Thing]", "Ledger Thing is not a term"),
            ("[V/v]", "no spelling the scan can match"),
        ],
    )
    def test_malformed_value_names_the_key_line(
        self, tmp_path, value, message
    ):
        root = _repo(
            tmp_path, {"topics/ledger.md": _page(400, introduces=value)}
        )

        (failure,) = _failures(root)

        assert failure.location == "docs/topics/ledger.md:4"
        assert message in failure.detail

    def test_every_fault_in_a_value_is_reported(self, tmp_path):
        value = "[Case Ledger Entry, Case Ledger Entry, Ledger Thing, V/v]"
        root = _repo(
            tmp_path, {"topics/ledger.md": _page(400, introduces=value)}
        )

        details = [f.detail for f in _failures(root)]

        assert len(details) == 3
        assert any("more than once" in d for d in details)
        assert any("Ledger Thing is not a term" in d for d in details)
        assert any("V/v has no spelling" in d for d in details)

    def test_a_term_has_one_introducer(self, tmp_path):
        root = _repo(
            tmp_path,
            {"topics/other.md": _page(500, introduces="[Case Ledger Entry]")},
        )

        (failure,) = _failures(root)

        assert "already introduced by docs/" in failure.detail

    def test_working_record_page_cannot_introduce(self, tmp_path):
        page = _page(
            None, audience="[project-contributor]", introduces="[CASE_MANAGER]"
        )
        root = _repo(tmp_path, {"adr/0001-x.md": page})

        (failure,) = _failures(root)

        assert "DF-11-012" in failure.detail

    def test_fragment_cannot_introduce(self, tmp_path):
        root = _repo(
            tmp_path,
            {
                "howto/_frag.md": "---\nintroduces: [CASE_MANAGER]\n---\nx\n",
                "howto/host.md": _page(
                    300, '{% include-markdown "./_frag.md" %}\n'
                ),
            },
            nav=["howto/host.md", "topics/ledger.md"],
        )

        (failure,) = _failures(root)

        assert "DF-11-010" in failure.detail


# ---------------------------------------------------------------------------
# Baseline (AC-4)
# ---------------------------------------------------------------------------

#: The committed baseline, pinned. It may only shrink: drop a key here when
#: ``--prune-baseline`` drops it from the file, and never add one. Pinning the
#: keys rather than their count also stops an entry being swapped for another
#: (AC-4 of #3529).
_BASELINED = frozenset(
    {
        ("howto/activitypub/activities/error.md", "CASE_MANAGER"),
        ("howto/activitypub/activities/initialize_case.md", "CASE_MANAGER"),
        ("howto/activitypub/activities/invite_actor.md", "CASE_MANAGER"),
        ("howto/activitypub/activities/invite_actor.md", "Embargo Consent"),
        ("howto/activitypub/activities/manage_case.md", "CASE_MANAGER"),
        (
            "howto/activitypub/activities/manage_participants.md",
            "CASE_MANAGER",
        ),
        (
            "howto/activitypub/activities/role_delegation.md",
            "Case Ownership Transfer",
        ),
        ("howto/activitypub/activities/status_updates.md", "CASE_MANAGER"),
        ("howto/activitypub/activities/suggest_actor.md", "CASE_MANAGER"),
        ("ns/index.md", "Embargo Consent"),
        ("reference/activitypub/objects.md", "CaseParticipant"),
        ("reference/fv-demo-protocol.md", "CASE_MANAGER"),
        ("reference/fv-demo-protocol.md", "Case Ledger Entry"),
        ("reference/fv-demo-protocol.md", "VulnerabilityCase"),
        ("reference/vultron-taxonomy.md", "CASE_MANAGER"),
        ("topics/case_lifecycle/index.md", "CASE_MANAGER"),
        (
            "topics/process_models/index.md",
            "Deterministic Finite Automaton (DFA)",
        ),
        ("topics/process_models/model_interactions/index.md", "CASE_MANAGER"),
        ("topics/process_models/model_interactions/index.md", "Global State"),
        ("topics/scenarios/fccv-handoff.md", "Case Ownership Transfer"),
        ("topics/scenarios/fcv.md", "Case Ledger Entry"),
        ("topics/scenarios/fvcv-handoff.md", "Case Ledger Entry"),
        ("topics/scenarios/fvcv-handoff.md", "Case Ownership Transfer"),
        ("topics/scenarios/index.md", "Case Ledger Entry"),
        ("tutorials/container_demos.md", "Case Ownership Transfer"),
        ("tutorials/other_demos.md", "Case Ownership Transfer"),
    }
)

_VIOLATING = _page(300, "# A\n\nEach case ledger entry is signed.\n")


@pytest.mark.spec("DF-11-002")
class TestBaseline:
    def test_baselined_violation_is_tolerated(self, tmp_path):
        root = _repo(tmp_path, {"howto/a.md": _VIOLATING})
        key = ("howto/a.md", "Case Ledger Entry")

        result = check_level_order(root, baseline={key: "awaiting #1"})

        assert result.baselined == [key]

    def test_stale_committed_entry_names_its_line(self, tmp_path, monkeypatch):
        root = _repo(tmp_path, {"howto/a.md": _page(300)})
        path = tmp_path / "baseline.txt"
        write_baseline({("howto/a.md", "Case Ledger Entry"): "old"}, path)
        monkeypatch.setattr(level_order, "BASELINE_PATH", path)

        with pytest.raises(MetadataLoadErrors) as info:
            check_level_order(root)

        (failure,) = info.value.failures
        entry_line = (
            path.read_text()
            .splitlines()
            .index("howto/a.md | Case Ledger Entry | old")
        )
        assert failure.location == f"baseline.txt:{entry_line + 1}"

    def test_stale_entry_fails(self, tmp_path):
        root = _repo(tmp_path, {"howto/a.md": _page(300)})

        (failure,) = _failures(
            root, baseline={("howto/a.md", "Case Ledger Entry"): "old"}
        )

        assert "no longer a violation" in failure.detail
        assert "--prune-baseline" in failure.detail
        assert "_BASELINED" in failure.detail

    @pytest.mark.parametrize(
        "line",
        [
            "howto/a.md | Case Ledger Entry",
            "howto/a.md | Case Ledger Entry | ",
        ],
        ids=["two-fields", "empty-reason"],
    )
    def test_entry_without_a_reason_is_malformed(self, tmp_path, line):
        path = tmp_path / "baseline.txt"
        path.write_text(f"# header\n\n{line}\n")

        with pytest.raises(MetadataLoadErrors) as info:
            read_baseline(path)

        (failure,) = info.value.failures
        assert failure.location == "baseline.txt:3"
        assert "names why it is unfixed" in failure.detail

    def test_repeated_entry_is_malformed(self, tmp_path):
        path = tmp_path / "baseline.txt"
        path.write_text("a.md | T | r\na.md | T | r2\n")

        with pytest.raises(MetadataLoadErrors, match="repeats"):
            read_baseline(path)

    def test_round_trip(self, tmp_path):
        path = tmp_path / "baseline.txt"
        entries = {("b.md", "T"): "why b", ("a.md", "T"): "why a"}

        write_baseline(entries, path)

        assert read_baseline(path) == entries
        body = [
            ln
            for ln in path.read_text().splitlines()
            if ln and not ln.startswith("#")
        ]
        assert body == ["a.md | T | why a", "b.md | T | why b"]

    def test_prune_only_removes(self, tmp_path):
        root = _repo(tmp_path, {"howto/a.md": _VIOLATING})
        path = tmp_path / "baseline.txt"
        write_baseline(
            {
                ("howto/a.md", "Case Ledger Entry"): "still open",
                ("howto/gone.md", "Case Ledger Entry"): "fixed",
            },
            path,
        )

        removed = prune_baseline(root, baseline_path=path)

        assert removed == 1
        assert read_baseline(path) == {
            ("howto/a.md", "Case Ledger Entry"): "still open"
        }

    def test_prune_keeps_an_entry_for_an_unreadable_page(self, tmp_path):
        """A page that fails to load has unknown violations, not none."""
        root = _repo(
            tmp_path,
            {
                "howto/a.md": _VIOLATING,
                "howto/b.md": "---\nlevel: [\n---\nx\n",
            },
        )
        path = tmp_path / "baseline.txt"
        entries = {
            ("howto/a.md", "Case Ledger Entry"): "open",
            ("howto/b.md", "Case Ledger Entry"): "unreadable",
        }
        write_baseline(entries, path)

        assert prune_baseline(root, baseline_path=path) == 0
        assert read_baseline(path) == entries

    def test_committed_baseline_never_grows(self):
        """When the baseline is pruned, drop the key here; never add one."""
        added = set(read_baseline()) - _BASELINED
        assert not added, (
            f"level_order_baseline.txt gained {sorted(added)}. Link each new "
            f"use to its introducing page (SG-11) instead of baselining it."
        )

    def test_pin_matches_the_committed_baseline(self):
        """A pruned entry leaves the pin too, so the pin cannot re-admit it."""
        assert _BASELINED == set(read_baseline())


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("term", "forms"),
    [
        (
            "Coordinated Vulnerability Disclosure (CVD)",
            ("Coordinated Vulnerability Disclosure", "CVD"),
        ),
        (
            "Semantic Type (or MessageSemantics)",
            ("Semantic Type", "MessageSemantics"),
        ),
        ("Embargo Revise (R)", ("Embargo Revise",)),
        ("V/v", ()),
        ("CASE_MANAGER", ("CASE_MANAGER",)),
    ],
)
def test_term_forms(term, forms):
    assert term_forms(term) == forms


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("Two case ledger entries.", None),  # "entries" is not "entry" + s
        ("The Case Ledger Entries.", None),
        ("The case ledger entry.", "case ledger entry"),
        ("The CASE_MANAGER role.", "CASE_MANAGER"),
        ("The case_manager role.", None),  # identifiers match exactly
        ("A CASE_MANAGER_ID field.", None),
        ("Multi-CASE_MANAGER setups.", None),
    ],
)
def test_first_use_matches_whole_words(text, found):
    page = scan_page(text, "a.md")
    forms = ("Case Ledger Entry", "CASE_MANAGER")

    use = first_use(page, forms)

    assert (use.text if use else None) == found


def test_scan_resolves_relative_links():
    page = scan_page(
        "[a](../b/c.md#x) [d](./) [e](https://x.org/f.md) [g](#h)\n",
        "topics/sub/page.md",
    )

    assert {link.target for link in page.links} == {
        "topics/b/c.md",
        "topics/sub/index.md",
    }


def test_nested_fences_are_tracked_only_when_asked():
    """A four-space fence is code inside an admonition, not plain Markdown."""
    text = "!!! note\n\n    ```\n    # x\n    ```\nafter\n"

    assert fenced_lines(text) == frozenset()
    assert fenced_lines(text, nested=True) == {3, 4, 5}


def test_a_shorter_run_does_not_close_a_longer_fence():
    assert fenced_lines("````\n```\nx\n````\ny\n") == {1, 2, 3, 4}


# ---------------------------------------------------------------------------
# Entry points and the real tree
# ---------------------------------------------------------------------------


def test_cli_reports_failures_without_a_traceback(
    tmp_path, monkeypatch, capsys
):
    root = _repo(tmp_path, {"howto/a.md": _VIOLATING})
    monkeypatch.setattr(level_order, "_find_repo_root", lambda: root)
    monkeypatch.setattr(level_order, "BASELINE_PATH", tmp_path / "none.txt")

    with pytest.raises(SystemExit) as info:
        main([])

    assert info.value.code == 1
    err = capsys.readouterr().err
    assert err.startswith("[ERROR] 1 docs level-order finding(s)")
    assert "docs/howto/a.md:7:6" in err


@pytest.mark.parametrize(
    "changed",
    [
        "docs/tutorials/deep/page.md",
        "mkdocs.yml",
        "vultron/metadata/docs/level_order.py",
        "vultron/metadata/docs/level_order_baseline.txt",
        "vultron/metadata/docs/level_baseline.py",
        "vultron/metadata/docs/concept_scan.py",
        "vultron/metadata/docs/concept_registry.py",
        "vultron/metadata/docs/baseline_file.py",
        "vultron/metadata/docs/page_frontmatter.py",
        "vultron/metadata/docs/page_schema.py",
        "vultron/metadata/markdown_tables.py",
        "vultron/metadata/file_loading.py",
    ],
)
def test_pre_commit_hook_runs_on_every_input(changed):
    config = yaml.safe_load(
        (repo_root() / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    )
    hooks = {
        hook["id"]: hook
        for repo in config["repos"]
        for hook in repo.get("hooks", [])
    }
    hook = hooks["docs-level-order"]

    assert hook["entry"] == "uv run docs-level-order"
    assert hook["pass_filenames"] is False
    assert re.search(hook["files"], changed)


@pytest.mark.spec("DF-11-002")
def test_the_committed_docs_tree_passes():
    """The gate CI enforces, independent of whether the hook ran locally."""
    result = check_level_order()

    assert result.leveled_pages > 0
    assert result.introductions > 0
