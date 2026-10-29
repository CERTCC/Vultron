"""Tests for the built-site reading-path box check (``uv run docs-path-boxes``).

Requirements: DF-11-045 (every member page and start page renders its box for
each thread it is on; the check names the page and the line to add and fails
on an empty target set), DF-11-044 (through an ``include-markdown`` line placed
by hand), DF-11-043 (a section member's box sits in its section), DF-09-009.
"""

from __future__ import annotations

from pathlib import Path

import markdown  # type: ignore[import-untyped]  # Python-Markdown ships no stubs
import pytest
import yaml

from test.metadata.docs._thread_tree import member, page, start_page, tree
from vultron.metadata.base import repo_root
from vultron.metadata.docs import path_boxes
from vultron.metadata.docs.path_boxes import check_boxes, scan_page
from vultron.metadata.docs.site_urls import url_path
from vultron.metadata.docs.threads import (
    box_fragment_path,
    include_line,
    load_threads,
    page_titles,
    render_boxes,
)
from vultron.metadata.file_loading import MetadataLoadError

_EXTENSIONS = ["admonition", "attr_list", "md_in_html", "tables"]

#: ``(thread, target)`` of every box the fixture's pages must render.
_PRACTICE = ("practice", "start/practice.md")
_STUDY = ("study", "start/study.md")


def _stage(title: str, kind: str, *members: dict) -> dict[str, object]:
    return {"title": title, "kind": kind, "members": list(members)}


def _docs(tmp_path: Path) -> Path:
    """``shared.md`` is on two threads; ``g.md#later`` is a section member."""
    return tree(
        tmp_path,
        {
            "start/practice.md": start_page(
                "You coordinate cases",
                [
                    _stage(
                        "Learn", "chain", member("a.md"), member("shared.md")
                    )
                ],
            ),
            "start/study.md": start_page(
                "You study disclosure",
                [
                    _stage(
                        "Browse",
                        "set",
                        member("shared.md"),
                        member("g.md#later"),
                    )
                ],
            ),
            "a.md": page("A"),
            "shared.md": page("Shared"),
            "g.md": page("G"),
            "off.md": page("Off"),
        },
    )


def _fragments(root: Path) -> dict[tuple[str, str], tuple[str, str]]:
    """``{(thread, target): (fragment path, box HTML)}`` for the fixture."""
    threads = load_threads(root)
    rendered = render_boxes(threads, page_titles(root, threads))
    out = {}
    for thread in threads:
        name = thread.path.removeprefix("start/").removesuffix(".md")
        for target in [thread.path, *(m.page for m in thread.members())]:
            fragment = box_fragment_path(thread, target)
            out[(name, target)] = (
                fragment,
                markdown.markdown(rendered[fragment], extensions=_EXTENSIONS),
            )
    return out


#: Each page's boxes, by ``(thread, target)``, in the layout that passes.
_LAYOUT: dict[str, list[tuple[str, str]]] = {
    "start/practice.md": [_PRACTICE],
    "start/study.md": [_STUDY],
    "a.md": [("practice", "a.md")],
    "shared.md": [("practice", "shared.md"), ("study", "shared.md")],
    "g.md": [("study", "g.md#later")],
    "off.md": [],
}


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build(
    root: Path,
    layout: dict[str, list[tuple[str, str]]] | None = None,
    *,
    sourced: bool = True,
    misplace: bool = False,
) -> None:
    """Write each page's source include lines and its built HTML.

    *layout* maps a page to the boxes it renders; *sourced* ``False`` renders
    them without the include lines; *misplace* puts ``g.md``'s section box
    after the next section's heading.
    """
    fragments = _fragments(root)
    for rel, keys in {**_LAYOUT, **(layout or {})}.items():
        includes = [include_line(rel, fragments[key][0]) for key in keys]
        boxes = "\n".join(fragments[key][1] for key in keys)
        if rel == "g.md":
            source = "# G\n\n## Later\n\nText.\n\n" + "\n\n".join(includes)
            source += "\n\n## After\n"
            section = '<h1 id="g">G</h1><h2 id="later">Later</h2><p>Text.</p>'
            after = '<h2 id="after">After</h2>'
            body = (
                f"{section}{after}{boxes}"
                if misplace
                else section + boxes + after
            )
        else:
            source = f"# {rel}\n\n" + "\n\n".join(includes) + "\n"
            body = f"<h1>{rel}</h1>{boxes}"
        if not sourced:
            source = source.replace("include-markdown", "removed")
        docs = root / "docs" / rel
        front = (
            docs.read_text().split("\n# ")[0]
            if rel.startswith("start/")
            else ""
        )
        _write(root, f"docs/{rel}", (front + "\n" if front else "") + source)
        _write(
            root,
            f"site/{url_path(rel)}/index.html",
            '<html><body><nav><h2 id="later">Nav</h2></nav>'
            f'<article class="md-content__inner">{body}</article></body></html>',
        )


@pytest.fixture
def site(tmp_path: Path) -> Path:
    root = _docs(tmp_path)
    _build(root)
    return root


def _faults(root: Path) -> list[str]:
    return check_boxes(root).faults


@pytest.mark.spec("DF-11-045")
class TestBuiltSiteCheck:
    def test_every_box_in_place_passes(self, site):
        report = check_boxes(site)
        assert report.faults == []
        assert report.boxes == 6
        assert report.pages == 6

    def test_a_member_page_with_no_box_names_the_line_to_add(self, site):
        _build(site, {"a.md": []})
        (fault,) = _faults(site)
        assert fault == (
            "docs/a.md: does not render its box for the practice reading "
            'path; add {% include-markdown "./start/_paths/practice/a.md" %}'
        )

    def test_a_start_page_with_no_box_fails(self, site):
        _build(site, {"start/study.md": []})
        (fault,) = _faults(site)
        assert fault.startswith("docs/start/study.md: does not render its box")
        assert (
            '{% include-markdown "./_paths/study/start__study.md" %}' in fault
        )

    def test_a_page_on_two_threads_with_one_box_fails(self, site):
        _build(site, {"shared.md": [("practice", "shared.md")]})
        (fault,) = _faults(site)
        assert fault.startswith("docs/shared.md: does not render its box for")
        assert "the study reading path" in fault
        assert "./start/_paths/study/shared.md" in fault

    def test_a_page_including_another_pages_box_fails(self, site):
        _build(site, {"off.md": [("practice", "a.md")]})
        (fault,) = _faults(site)
        assert fault == (
            "docs/off.md: renders the box made for a.md on the practice "
            "reading path; remove "
            '{% include-markdown "./start/_paths/practice/a.md" %}'
        )

    @pytest.mark.spec("DF-11-043")
    def test_a_section_box_outside_its_section_fails(self, site):
        _build(site, misplace=True)
        (fault,) = _faults(site)
        assert fault.startswith(
            "docs/g.md: renders the study box for #later outside that section"
        )
        assert (
            '{% include-markdown "./start/_paths/study/g--later.md" %}'
            in fault
        )

    @pytest.mark.spec("DF-11-043")
    def test_a_section_box_before_its_heading_fails(self, site):
        html = site / "site/g/index.html"
        text = html.read_text()
        box_start = text.index("<div class")
        box_end = text.index('<h2 id="after">')
        moved = text[box_start:box_end]
        text = text.replace(moved, "").replace(
            '<h1 id="g">G</h1>', f'<h1 id="g">G</h1>{moved}'
        )
        html.write_text(text)
        (fault,) = _faults(site)
        assert "outside that section" in fault

    @pytest.mark.spec("DF-11-043")
    def test_a_section_box_whose_anchor_is_gone_fails(self, site):
        html = site / "site/g/index.html"
        html.write_text(html.read_text().replace('id="later"', 'id="renamed"'))
        (fault,) = _faults(site)
        assert "no element carries that id" in fault

    def test_a_box_made_for_no_target_is_foreign(self, site):
        html = site / "site/off/index.html"
        html.write_text(
            html.read_text().replace(
                "</article>",
                '<div class="reading-path" data-thread="gone" '
                'data-member="x.md"></div></article>',
            )
        )
        (fault,) = _faults(site)
        assert fault == (
            "docs/off.md: renders the box made for x.md on the gone reading "
            "path; remove the include-markdown line that renders it"
        )

    def test_a_non_heading_anchor_bounds_the_section_at_any_heading(
        self, site
    ):
        html = site / "site/g/index.html"
        text = html.read_text().replace(
            '<h2 id="later">Later</h2><p>Text.</p>',
            '<p id="later">Text.</p><h4 id="minor">Minor</h4>',
        )
        html.write_text(text)
        (fault,) = _faults(site)
        assert "outside that section" in fault

    @pytest.mark.spec("DF-11-044")
    def test_a_box_with_no_include_directive_fails(self, site):
        _build(site, sourced=False)
        faults = _faults(site)
        assert len(faults) == 6
        assert (
            "docs/a.md: renders the practice box for a.md with no matching "
            "include-markdown directive in its source"
        ) in faults[0]
        assert (
            '{% include-markdown "./start/_paths/practice/a.md" %}'
            in (faults[0])
        )

    def test_a_box_rendered_twice_fails(self, site):
        _build(site, {"a.md": [("practice", "a.md"), ("practice", "a.md")]})
        (fault,) = _faults(site)
        assert fault.startswith("docs/a.md: renders its practice box 2 times")

    def test_an_unbuilt_member_page_fails(self, site):
        (site / "site/a/index.html").unlink()
        (fault,) = _faults(site)
        assert fault.startswith("docs/a.md: is on a reading path but was not")

    def test_no_threads_fails(self, tmp_path):
        root = tree(tmp_path, {"a.md": page("A")})
        _write(root, "site/index.html", "<html></html>")
        with pytest.raises(MetadataLoadError, match="no reading-path boxes"):
            check_boxes(root)

    def test_an_unbuilt_site_fails(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="reading-path boxes"):
            check_boxes(_docs(tmp_path))

    def test_cli_exits_nonzero_and_names_each_fault(
        self, site, monkeypatch, capsys
    ):
        _build(site, {"a.md": []})
        monkeypatch.setattr(path_boxes, "repo_root", lambda: site)
        with pytest.raises(SystemExit) as exc:
            path_boxes.main([])
        assert exc.value.code == 1
        assert "[ERROR] docs/a.md: does not render" in capsys.readouterr().err

    def test_cli_reports_what_it_checked(self, site, monkeypatch, capsys):
        monkeypatch.setattr(path_boxes, "repo_root", lambda: site)
        path_boxes.main([])
        assert "Checked 6 reading-path box(es) over 6 built page(s)." in (
            capsys.readouterr().out
        )


@pytest.mark.spec("DF-11-045")
class TestScan:
    def test_only_the_article_is_read(self):
        scan = scan_page(
            '<nav><h2 id="x">X</h2><div class="reading-path"></div></nav>'
            '<article><h2 id="y">Y</h2></article>'
            '<footer><div class="reading-path"></div></footer>'
        )
        assert scan.boxes == []
        assert list(scan.ids) == ["y"]

    def test_a_class_merely_containing_the_name_is_not_a_box(self):
        scan = scan_page('<article><table class="reading-path-table">')
        assert scan.boxes == []


@pytest.mark.spec("DF-11-045")
def test_the_check_runs_in_ci_beside_the_built_site_checks():
    action = yaml.safe_load(
        (
            repo_root() / ".github/actions/check-site-publication/action.yml"
        ).read_text(encoding="utf-8")
    )
    runs = [step.get("run", "") for step in action["runs"]["steps"]]
    assert any("uv run docs-path-boxes" in run for run in runs)
    hooks = yaml.safe_load(
        (repo_root() / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    )
    entries = [
        hook.get("entry", "")
        for repo in hooks["repos"]
        for hook in repo.get("hooks", [])
    ]
    assert not [entry for entry in entries if "docs-path-boxes" in entry]
