"""Tests for vultron.metadata.docs.legacy_urls (issue #3556).

Between the ``publish`` branch and ``main``, well over a hundred pages moved,
were renamed, or were withdrawn, and a publish would have turned every one of
their URLs into a 404. These tests pin the comparison that catches that: every page in the
committed baseline resolves in the built ``site/`` as a page, or as a redirect
chain ending at one, unless a withheld declaration withdraws it.

The empty-``site/`` and empty-baseline tests are the load-bearing ones: both
close a way for the check to pass while checking nothing (DF-09-009).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from vultron.metadata.docs.legacy_urls import (
    load_baseline,
    main,
    page_url,
    redirect_target,
    snapshot,
    unmapped_pages,
)
from vultron.metadata.docs.withheld import WithheldArtifact

NO_ARTIFACTS: tuple[WithheldArtifact, ...] = ()


def _stub(target: str) -> str:
    """Return a redirect page in the shape ``mkdocs-redirects`` writes."""
    return (
        "<!doctype html><html><head>"
        f'<link rel="canonical" href="{target}">'
        f'<meta http-equiv="refresh" content="0; url={target}">'
        "</head><body>Redirecting</body></html>"
    )


def _site(root: Path, files: dict[str, str]) -> None:
    """Write a synthetic built site: ``{path under site/: html}``."""
    for rel, html in files.items():
        path = root / "site" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")


def _artifact(prefix: str) -> WithheldArtifact:
    return WithheldArtifact(
        name="Withdrawn",
        site_prefixes=(prefix,),
        source_globs=("x",),
        reason="r",
        gate="g",
    )


# --- page_url ------------------------------------------------------------


@pytest.mark.parametrize(
    "source,url",
    [
        ("index.md", ""),
        ("README.md", ""),
        ("howto/index.md", "howto"),
        ("howto/README.md", "howto"),
        ("howto/objects.md", "howto/objects"),
        ("howto/activities/_accept.md", "howto/activities/_accept"),
    ],
)
def test_page_url_follows_directory_urls(source: str, url: str):
    assert page_url(source) == url


def test_redirect_target_reads_the_meta_refresh():
    assert redirect_target(_stub("../new/")) == "../new/"
    assert redirect_target("<html><body>a page</body></html>") is None


# --- unmapped_pages -------------------------------------------------------


def test_a_page_the_build_still_produces_is_mapped(tmp_path):
    _site(tmp_path, {"a/b/index.html": "<p>page</p>"})
    assert unmapped_pages(tmp_path, ["a/b.md"], NO_ARTIFACTS) == []


def test_the_site_root_is_checked_as_index_html(tmp_path):
    _site(tmp_path, {"index.html": "<p>home</p>"})
    assert unmapped_pages(tmp_path, ["index.md"], NO_ARTIFACTS) == []


def test_a_dropped_page_is_unmapped(tmp_path):
    _site(tmp_path, {"index.html": "<p>home</p>"})
    [page] = unmapped_pages(tmp_path, ["old/page.md"], NO_ARTIFACTS)
    assert page.source == "old/page.md"
    assert page.url == "old/page"
    assert "neither a page nor a redirect" in page.problem


def test_a_redirect_to_a_built_page_is_mapped(tmp_path):
    _site(
        tmp_path,
        {
            "old/page/index.html": _stub("../../new/page/"),
            "new/page/index.html": "<p>page</p>",
        },
    )
    assert unmapped_pages(tmp_path, ["old/page.md"], NO_ARTIFACTS) == []


def test_a_redirect_to_the_site_root_is_mapped(tmp_path):
    _site(
        tmp_path,
        {"old/index.html": _stub("../"), "index.html": "<p>home</p>"},
    )
    assert unmapped_pages(tmp_path, ["old/index.md"], NO_ARTIFACTS) == []


def test_a_redirect_anchor_is_ignored_when_resolving(tmp_path):
    _site(
        tmp_path,
        {
            "old/index.html": _stub("../new/#section"),
            "new/index.html": "<p>page</p>",
        },
    )
    assert unmapped_pages(tmp_path, ["old/index.md"], NO_ARTIFACTS) == []


def test_a_redirect_to_an_unbuilt_page_is_unmapped(tmp_path):
    """A stub alone is not continuity: its target must exist too."""
    _site(tmp_path, {"old/index.html": _stub("../gone/")})
    [page] = unmapped_pages(tmp_path, ["old/index.md"], NO_ARTIFACTS)
    assert "'gone/', which was not built" in page.problem


def test_a_redirect_chain_is_followed_to_its_end(tmp_path):
    _site(
        tmp_path,
        {
            "a/index.html": _stub("../b/"),
            "b/index.html": _stub("../c/"),
            "c/index.html": "<p>page</p>",
        },
    )
    assert unmapped_pages(tmp_path, ["a/index.md"], NO_ARTIFACTS) == []


def test_a_redirect_loop_is_unmapped(tmp_path):
    _site(
        tmp_path,
        {"a/index.html": _stub("../b/"), "b/index.html": _stub("../a/")},
    )
    [page] = unmapped_pages(tmp_path, ["a/index.md"], NO_ARTIFACTS)
    assert "loop: a -> b -> a" in page.problem


@pytest.mark.parametrize(
    "target,built",
    [
        ("../index.html", "index.html"),
        ("../new/index.html", "new/index.html"),
        ("../page.html", "page.html"),
    ],
)
def test_a_redirect_to_an_html_file_resolves_to_that_file(
    tmp_path, target, built
):
    """A file target names the file itself, not a directory beneath it."""
    _site(tmp_path, {"old/index.html": _stub(target), built: "<p>page</p>"})
    assert unmapped_pages(tmp_path, ["old/index.md"], NO_ARTIFACTS) == []


@pytest.mark.parametrize(
    "target", ["https://example.org/", "/abs/", "../../../outside/"]
)
def test_a_redirect_the_build_cannot_evidence_is_unmapped(tmp_path, target):
    _site(tmp_path, {"old/index.html": _stub(target)})
    [page] = unmapped_pages(tmp_path, ["old/index.md"], NO_ARTIFACTS)
    assert "outside the built site" in page.problem


def test_a_withheld_url_is_accounted_for(tmp_path):
    """A withdrawn page is absent on purpose; docs-withheld checks it stays so."""
    _site(tmp_path, {"index.html": "<p>home</p>"})
    pages = ["ontology/dfa.md", "ontology/dfa2.md"]
    unmapped = unmapped_pages(tmp_path, pages, (_artifact("ontology/dfa"),))
    # The prefix covers itself only, not a sibling that shares its spelling.
    assert [p.source for p in unmapped] == ["ontology/dfa2.md"]


def test_an_absent_site_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="absent or empty"):
        unmapped_pages(tmp_path, ["a.md"], NO_ARTIFACTS)


def test_an_empty_site_raises(tmp_path):
    (tmp_path / "site").mkdir()
    with pytest.raises(FileNotFoundError, match="absent or empty"):
        unmapped_pages(tmp_path, ["a.md"], NO_ARTIFACTS)


def test_an_empty_baseline_raises(tmp_path):
    _site(tmp_path, {"index.html": "<p>home</p>"})
    with pytest.raises(ValueError, match="baseline is empty"):
        unmapped_pages(tmp_path, [], NO_ARTIFACTS)


# --- the committed baseline ----------------------------------------------


def test_the_committed_baseline_is_seeded():
    """The publish-era evidence is gone once publish advances; keep it here."""
    pages = load_baseline()
    assert len(pages) > 300
    assert "topics/user_stories/story_2022_001.md" in pages
    assert all(page.endswith(".md") for page in pages)
    assert pages == sorted(pages)


# --- snapshot -------------------------------------------------------------


def _git_repo(
    root: Path, files: list[str], mkdocs_yml: str = "site_name: t\n"
) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "mkdocs.yml").write_text(mkdocs_yml, encoding="utf-8")
    for rel in files:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.org",
            "commit",
            "-qm",
            "seed",
        ],
        check=True,
    )


def test_snapshot_extends_the_baseline_and_never_drops(tmp_path):
    repo = tmp_path / "repo"
    _git_repo(repo, ["docs/new.md", "docs/sub/index.md", "docs/img.png"])
    baseline = tmp_path / "baseline.txt"
    baseline.write_text("# header\nold/gone.md\n", encoding="utf-8")

    added = snapshot("HEAD", repo, baseline)

    assert added == 2
    assert load_baseline(baseline) == ["new.md", "old/gone.md", "sub/index.md"]


def test_snapshot_skips_pages_the_ref_does_not_build(tmp_path):
    """A draft or excluded source was never served, so it is not a legacy URL.

    Recording ``developer/`` pages from a ref whose ``mkdocs.yml`` drafts them
    would fail the check on URLs no publish ever answered.
    """
    repo = tmp_path / "repo"
    _git_repo(
        repo,
        ["docs/page.md", "docs/developer/index.md", "docs/old/x.md"],
        mkdocs_yml=(
            "site_name: t\n"
            "draft_docs: |\n  developer/\n"
            "exclude_docs: |\n  old/\n"
            "markdown_extensions:\n"
            "  - pymdownx.emoji:\n"
            "      emoji_index: !!python/name:material.extensions.emoji.twemoji\n"
        ),
    )
    baseline = tmp_path / "baseline.txt"
    baseline.write_text("# header\n", encoding="utf-8")

    assert snapshot("HEAD", repo, baseline) == 1
    assert load_baseline(baseline) == ["page.md"]


# --- CLI ------------------------------------------------------------------


def test_cli_fails_on_an_unbuilt_site(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--root", str(tmp_path)])
    assert exc.value.code == 1
    assert "absent or empty" in capsys.readouterr().err


def _baseline(tmp_path: Path, pages: list[str]) -> Path:
    path = tmp_path / "baseline.txt"
    path.write_text("# header\n" + "".join(f"{p}\n" for p in pages))
    return path


def test_cli_names_each_unmapped_url(tmp_path, capsys):
    _site(tmp_path, {"index.html": "<p>home</p>"})
    baseline = _baseline(tmp_path, ["index.md", "old/page.md"])
    with pytest.raises(SystemExit) as exc:
        main(["--root", str(tmp_path), "--baseline", str(baseline)])
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "old/page/ (from old/page.md)" in err
    assert "1 of 2 published URL(s) would 404" in err


def test_cli_passes_when_every_url_resolves(tmp_path, capsys):
    _site(tmp_path, {"index.html": "<p>home</p>"})
    baseline = _baseline(tmp_path, ["index.md"])
    main(["--root", str(tmp_path), "--baseline", str(baseline)])
    assert "All 1 published URLs resolve in site/" in capsys.readouterr().out


def test_cli_fails_on_an_empty_baseline(tmp_path, capsys):
    _site(tmp_path, {"index.html": "<p>home</p>"})
    baseline = _baseline(tmp_path, [])
    with pytest.raises(SystemExit) as exc:
        main(["--root", str(tmp_path), "--baseline", str(baseline)])
    assert exc.value.code == 1
    assert "baseline is empty" in capsys.readouterr().err


def test_cli_snapshot_extends_the_named_baseline(tmp_path, capsys):
    repo = tmp_path / "repo"
    _git_repo(repo, ["docs/new.md"])
    baseline = _baseline(tmp_path, ["old/gone.md"])
    main(
        [
            "--root",
            str(repo),
            "--baseline",
            str(baseline),
            "--snapshot",
            "HEAD",
        ]
    )
    assert (
        "Added 1 page(s) from HEAD to baseline.txt" in capsys.readouterr().out
    )
    assert load_baseline(baseline) == ["new.md", "old/gone.md"]


def test_cli_snapshot_reports_an_unreadable_ref(tmp_path, capsys):
    repo = tmp_path / "repo"
    _git_repo(repo, ["docs/new.md"])
    baseline = _baseline(tmp_path, ["old/gone.md"])
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "--root",
                str(repo),
                "--baseline",
                str(baseline),
                "--snapshot",
                "nosuchref",
            ]
        )
    assert exc.value.code == 1
    assert "[ERROR] git cannot read 'nosuchref'" in capsys.readouterr().err
    assert load_baseline(baseline) == ["old/gone.md"]
