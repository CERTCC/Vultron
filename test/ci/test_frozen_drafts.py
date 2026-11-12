"""CI verification test — a promote that releases a draft attaches its frozen pages.

Implements the promote side of DOCBW-08 (ADR-0188, #6286): DOCBW-08-009 to
DOCBW-08-026 and DOCBW-08-037, and the DOCBW-07-016 refusal they refine.

The archive is built by ``.github/scripts/frozen_draft.py`` from a fixture
site, and checked by unpacking it into an empty folder. The promote runs
``.github/scripts/release.py`` against real commits, drafts registers and
tags in a scratch repository with a bare ``origin``, with ``gh`` replaced by
a fake that keeps the repository's releases and their assets. The workflow
that runs both, ``promote_release.yml``, is read for its job split and
permissions.
"""

from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import tarfile
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest

from test.ci._scratch_git import (
    git,
    isolate_git_config,
    scratch_clone,
    tag_as_bot,
)
from test.ci._scripts import load_script
from test.ci._workflows import BUILD_SITE_ACTION, WORKFLOWS_DIR, load_workflow
from vultron.metadata.docs import drafts_register as dr

_rel = load_script("release")
_fd = load_script("frozen_draft")
_tags = load_script("release_tags")

TODAY = date(2026, 11, 2)
BUILT = date(2026, 11, 2)
RELEASE = "v2026.11.0"
PUBLISH = "publish-2026-11-02.1"
SITE_URL = "https://example.org/Vultron/"
RUN_URL = "https://github.com/O/R/actions/runs/7"
MAIN = "refs/heads/main"
PROMOTE = WORKFLOWS_DIR / "promote_release.yml"
SHA = "0123456789abcdef0123456789abcdef01234567"
ARCHIVE = "vultron-spec-draft-1.tar.gz"
MANIFEST = "vultron-spec-draft-1.sha256"


# --- a fixture site -------------------------------------------------------------


def _footer(publish: str = PUBLISH, release: str = RELEASE) -> str:
    return (
        '<p class="build-footer">Published 2026-11-02 · '
        f'<a href="https://github.com/O/R/tree/{publish}">{publish}</a> · '
        f'release <a href="https://github.com/O/R/tree/{release}">{release}'
        "</a></p>"
    )


def _page(body: str, head: str = "", footer: str | None = None) -> str:
    return (
        "<!doctype html>\n<html><head><meta charset=utf-8>"
        f"{head}</head>\n<body dir=ltr>\n{body}\n"
        f"<footer>{_footer() if footer is None else footer}</footer>\n"
        "<script>if (a<b && c>d) { x = '<a href=\"../nope\">'; }</script>\n"
        "</body></html>\n"
    )


_SPEC_PAGES = {
    "index.html": _page(
        '<a href="layers/">Layers</a> <a href="./">Here</a>'
        ' <a href="../../start/">Start</a>'
        ' <a href="../../guide/page.html#x">Guide</a>'
        ' <a href="../..">Home</a> <a href="#top">Top</a>'
        ' <a href="https://elsewhere.example/">Out</a>'
        ' <a href="mailto:x@example.org">Mail</a>'
        ' <a href="../../files/data.yaml">Data</a>'
        ' <img src="../../img/logo.png"'
        ' srcset="../../img/logo.png 1x, ../../img/logo@2x.png 2x">'
        ' <img src="figure.svg">',
        head=(
            f'<link rel="canonical" href="{SITE_URL}reference/vultron-spec/">'
            '<link rel="stylesheet" href="../../assets/main.css">'
            '<script src="../../assets/app.js"></script>'
            '<script id="__config" type="application/json">'
            '{"base": "../..", "search": "../../assets/worker.js"}</script>'
        ),
    ),
    "layers/index.html": _page(
        '<a href="../">Spec</a> <a href="../../../start/?q=1#s">Start</a>'
        " <a href='../index.html'>Index</a>"
        ' <a class="tight"href="../../../start/">Tight</a>'
        ' <a href="../../vultron-spec/">Round</a>'
        ' <img srcset="data:image/png;base64,AA,BB 1x,'
        ' ../../../img/logo.png 2x">',
        head='<link rel="stylesheet" href="../../../assets/main.css">',
    ),
    "_old/index.html": (
        "<!doctype html><html><head>"
        '<link rel="canonical" href="../layers/">'
        '<meta http-equiv="refresh" content="0; url=../layers/">'
        '</head><body>Moved to <a href="../layers/">layers</a>.</body></html>'
    ),
    "figure.svg": "<svg/>",
}

_OTHER_FILES = {
    "index.html": _page("Home"),
    "start/index.html": _page("Start"),
    "guide/page.html": _page("Guide"),
    "other/index.html": _page("Never linked"),
    "assets/main.css": (
        '@import "theme.css";'
        "body{background:url(../img/bg.png)}"
        '@font-face{src:url("../fonts/f.woff2")}'
        ".x{background:url(data:image/png;base64,AA)}"
    ),
    "assets/app.js": "console.log(1)",
    "assets/worker.js": "onmessage = null",
    "assets/theme.css": "a{background:url('../img/t.png')}",
    "img/t.png": "t",
    "img/logo.png": "png",
    "img/logo@2x.png": "png2",
    "img/bg.png": "bg",
    "fonts/f.woff2": "font",
    "files/data.yaml": "a: 1",
}


def _write(root: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _site(tmp_path: Path, **spec_overrides: str) -> Path:
    site = tmp_path / "site"
    _write(site, _OTHER_FILES)
    _write(site / _fd.SPEC_DIR, {**_SPEC_PAGES, **spec_overrides})
    return site


def _draft(commit: str = SHA) -> Any:
    return _fd.FrozenDraft("draft-1", RELEASE, commit, PUBLISH, BUILT)


def _build(
    tmp_path: Path, commit: str = SHA, **overrides: str
) -> tuple[Path, Path]:
    archive, manifest = _fd.build_archive(
        _site(tmp_path, **overrides), tmp_path / "frozen", _draft(commit)
    )
    return Path(archive), Path(manifest)


def _unpacked(tmp_path: Path) -> Path:
    archive, manifest = _build(tmp_path)
    into = tmp_path / "unpacked"
    _fd.verify_archive(archive, manifest, into)
    return into


class _References(HTMLParser):
    """Every href, src and srcset URL of a page, read independently of the script."""

    def __init__(self) -> None:
        super().__init__()
        self.found: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        for name, value in attrs:
            if value is None:
                continue
            if name == "srcset":
                # Candidates end at a comma followed by white space.
                self.found += [c.split()[0] for c in re.split(r",\s+", value)]
            elif name in ("href", "src"):
                self.found.append(value)


def _refs(path: Path) -> list[str]:
    parser = _References()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.found


def _pages(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*.html"))


# --- building the archive -----------------------------------------------------------


@pytest.mark.spec("DOCBW-08-013")
def test_the_archive_root_is_the_specification_root(tmp_path: Path) -> None:
    root = _unpacked(tmp_path)
    assert _pages(root) == [
        "_old/index.html",
        "index.html",
        "layers/index.html",
    ]
    assert (root / "figure.svg").is_file()
    # The files the pages load come along, below their site paths; no page
    # from outside the specification does.
    bundled = sorted(
        p.relative_to(root).as_posix()
        for p in (root / _fd.BUNDLE_DIR).rglob("*")
        if p.is_file()
    )
    assert bundled == [
        "_site/assets/app.js",
        "_site/assets/main.css",
        "_site/assets/theme.css",
        "_site/assets/worker.js",
        "_site/files/data.yaml",
        "_site/fonts/f.woff2",
        "_site/img/bg.png",
        "_site/img/logo.png",
        "_site/img/logo@2x.png",
        "_site/img/t.png",
    ]


@pytest.mark.spec("DOCBW-08-014")
def test_every_page_footer_names_the_publish_and_the_release(
    tmp_path: Path,
) -> None:
    root = _unpacked(tmp_path)
    for name in ("index.html", "layers/index.html"):
        text = (root / name).read_text(encoding="utf-8")
        assert f">{PUBLISH}</a>" in text and f">{RELEASE}</a>" in text


@pytest.mark.spec("DOCBW-08-014")
def test_a_page_whose_footer_lacks_the_release_is_refused(
    tmp_path: Path,
) -> None:
    bad = _page("x", footer=_footer(release="v2026.10.9"))
    with pytest.raises(_fd.FrozenDraftError) as caught:
        _build(tmp_path, **{"layers/index.html": bad})
    assert caught.value.faults == [
        f"{_fd.SPEC_DIR}/layers/index.html: the page footer does not name "
        f"{RELEASE}"
    ]


@pytest.mark.spec("DOCBW-08-015")
def test_every_relative_reference_resolves_inside_the_archive(
    tmp_path: Path,
) -> None:
    root = _unpacked(tmp_path)
    checked = 0
    for name in _pages(root):
        for ref in _refs(root / name):
            path = ref.split("#")[0].split("?")[0]
            if not path or ":" in path or path.startswith("/"):
                continue
            target = (root / name).parent / path
            if target.is_dir():
                target = target / "index.html"
            assert target.resolve().is_relative_to(root.resolve()), (name, ref)
            assert target.is_file(), (name, ref)
            checked += 1
    assert checked >= 12, "the fixture's references were not read"
    # The stylesheet's own references resolve too.
    css = root / "_site/assets/main.css"
    assert "url(../img/bg.png)" in css.read_text()
    assert (css.parent / "../img/bg.png").is_file()


@pytest.mark.spec("DOCBW-08-015")
def test_references_are_rewritten_to_the_archive_layout(
    tmp_path: Path,
) -> None:
    root = _unpacked(tmp_path)
    index = _refs(root / "index.html")
    assert "layers/" in index and "./" in index and "figure.svg" in index
    assert "_site/assets/main.css" in index
    assert "_site/img/logo@2x.png" in index
    assert "_site/files/data.yaml" in index
    layers = _refs(root / "layers/index.html")
    assert "../_site/assets/main.css" in layers
    assert "../" in layers and "../index.html" in layers
    # A specification link written through the long way round still works.
    assert "../../vultron-spec/" not in layers and layers.count("../") == 2
    # A data: candidate keeps its commas; the other candidate is bundled.
    text = (root / "layers/index.html").read_text(encoding="utf-8")
    assert (
        'srcset="data:image/png;base64,AA,BB 1x, ../_site/img/logo.png 2x"'
        in text
    )
    # An attribute right after a quote is rewritten too.
    assert f'class="tight"href="{SITE_URL}start/"' in text


def test_stylesheet_imports_and_the_search_worker_come_along(
    tmp_path: Path,
) -> None:
    root = _unpacked(tmp_path)
    css = (root / "_site/assets/main.css").read_text(encoding="utf-8")
    assert '@import "theme.css";' in css
    assert (root / "_site/assets/theme.css").is_file()
    config = (root / "index.html").read_text(encoding="utf-8")
    assert '"search": "_site/assets/worker.js"' in config
    assert '"base": "../.."' in config  # search still queries the live site


@pytest.mark.spec("DOCBW-08-016")
def test_links_that_leave_the_specification_name_the_live_site(
    tmp_path: Path,
) -> None:
    root = _unpacked(tmp_path)
    index = _refs(root / "index.html")
    assert f"{SITE_URL}start/" in index
    assert f"{SITE_URL}guide/page.html#x" in index
    assert SITE_URL in index  # the site's home page
    assert "https://elsewhere.example/" in index
    assert "mailto:x@example.org" in index
    assert f"{SITE_URL}start/?q=1#s" in _refs(root / "layers/index.html")


@pytest.mark.spec("DOCBW-08-017")
def test_every_page_carries_the_banner(tmp_path: Path) -> None:
    root = _unpacked(tmp_path)
    for name in _pages(root):
        text = (root / name).read_text(encoding="utf-8")
        start = text.index(f'class="{_fd.BANNER_CLASS}"')
        banner = text[start : text.index("</div>", start)]
        assert text.index("<body") < start, name
        for fact in ("draft-1", RELEASE, SHA, "2026-11-02"):
            assert fact in banner, (name, fact)
        assert "go to the live site, which changes" in banner, name


@pytest.mark.spec("DOCBW-08-017")
def test_the_banner_needs_a_full_commit_sha(tmp_path: Path) -> None:
    with pytest.raises(_fd.FrozenDraftError, match="full commit SHA"):
        _build(tmp_path, commit="0123abc")


@pytest.mark.spec("DOCBW-08-018")
def test_the_manifest_passes_sha256sum_check(tmp_path: Path) -> None:
    root = _unpacked(tmp_path)
    manifest = tmp_path / "frozen" / MANIFEST
    listed = {
        line.split("  ", 1)[1] for line in manifest.read_text().splitlines()
    }
    on_disk = {
        p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
    }
    assert listed == on_disk
    if shutil.which("sha256sum") is None:
        pytest.skip("sha256sum is not installed")
    subprocess.run(
        ["sha256sum", "--check", "--strict", "--quiet", str(manifest)],
        cwd=root,
        check=True,
    )


def test_every_build_fault_is_named(tmp_path: Path) -> None:
    """A dead reference, one past the site root, a redirect out of the
    specification and a page with no body are all reported (EH-07-001)."""
    overrides = {
        "dead.html": _page('<a href="missing/">x</a>'),
        "deep/past.html": _page('<a href="../../../../../up">x</a>'),
        "_away/index.html": (
            '<html><head><meta http-equiv="refresh" '
            'content="0; url=../../../start/"></head><body></body></html>'
        ),
        "nobody.html": "<html><head></head></html>",
    }
    with pytest.raises(_fd.FrozenDraftError) as caught:
        _build(tmp_path, **overrides)
    text = str(caught.value)
    assert "'missing/' names no file of the site" in text
    assert "leaves the site" in text
    assert "redirects to '../../../start/'" in text
    assert "nobody.html: the page has no <body>" in text


def test_a_specification_folder_named_like_the_bundle_is_refused(
    tmp_path: Path,
) -> None:
    with pytest.raises(_fd.FrozenDraftError, match="_site/ folder"):
        _build(tmp_path, **{"_site/x.css": "a{}"})


# --- checking the archive (DOCBW-08-021) --------------------------------------------


def _tar(members: list[tarfile.TarInfo], data: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for info in members:
            payload = data.get(info.name)
            tar.addfile(
                info, io.BytesIO(payload) if payload is not None else None
            )
    return buffer.getvalue()


def _file(name: str, payload: bytes) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    return info


def _pair(tmp_path: Path, files: dict[str, bytes]) -> tuple[Path, Path]:
    archive = tmp_path / ARCHIVE
    manifest = tmp_path / MANIFEST
    archive.write_bytes(_fd.archive_bytes(files, _fd.datetime(2026, 11, 2)))
    manifest.write_text(_fd.manifest_text(files))
    return archive, manifest


@pytest.mark.spec("DOCBW-08-021")
def test_a_reference_that_leaves_the_archive_fails_the_check(
    tmp_path: Path,
) -> None:
    archive, manifest = _pair(
        tmp_path, {"index.html": b'<a href="../outside.html">x</a>'}
    )
    with pytest.raises(_fd.FrozenDraftError, match="leaves the archive"):
        _fd.verify_archive(archive, manifest, tmp_path / "into")


@pytest.mark.spec("DOCBW-08-021")
@pytest.mark.parametrize("fault", ["changed", "missing", "extra"])
def test_a_tree_that_is_not_its_manifest_fails_the_check(
    tmp_path: Path, fault: str
) -> None:
    files = {"index.html": b"<p>x</p>", "a.css": b"a{}"}
    archive, manifest = _pair(tmp_path, files)
    lines = manifest.read_text().splitlines()
    if fault == "changed":
        lines[0] = "0" * 64 + lines[0][64:]
    elif fault == "missing":
        lines.append(f"{'1' * 64}  gone.html")
    else:
        lines = lines[1:]
    manifest.write_text("\n".join(lines) + "\n")
    with pytest.raises(_fd.FrozenDraftError) as caught:
        _fd.verify_archive(archive, manifest, tmp_path / "into")
    assert {
        "changed": "its SHA-256 is not the listed one",
        "missing": "listed, but not in the archive",
        "extra": "in the archive, but not listed",
    }[fault] in str(caught.value)


@pytest.mark.spec("DOCBW-08-021")
@pytest.mark.parametrize("bad", ["page", "manifest"])
def test_text_that_is_not_utf8_fails_the_check(
    tmp_path: Path, bad: str
) -> None:
    page = b"<p>\xff</p>" if bad == "page" else b"<p>x</p>"
    archive, manifest = _pair(tmp_path, {"index.html": page})
    if bad == "manifest":
        manifest.write_bytes(b"\xff\n")
    with pytest.raises(_fd.FrozenDraftError, match="not UTF-8 text"):
        _fd.verify_archive(archive, manifest, tmp_path / "into")


def test_a_stylesheet_that_is_not_utf8_is_refused(tmp_path: Path) -> None:
    site = _site(tmp_path)
    (site / "assets/main.css").write_bytes(b"a{}\xff")
    with pytest.raises(_fd.FrozenDraftError, match=r"main\.css: not UTF-8"):
        _fd.build_archive(site, tmp_path / "frozen", _draft())


@pytest.mark.parametrize("kind", ["absolute", "dotdot", "symlink"])
def test_an_unsafe_member_is_refused_before_anything_is_written(
    tmp_path: Path, kind: str
) -> None:
    payload = b"x"
    if kind == "symlink":
        bad = tarfile.TarInfo("link")
        bad.type = tarfile.SYMTYPE
        bad.linkname = "/etc/passwd"
    else:
        bad = _file(
            "/abs/evil" if kind == "absolute" else "a/../../evil", payload
        )
    good = _file("index.html", payload)
    archive = tmp_path / ARCHIVE
    archive.write_bytes(
        _tar([good, bad], {good.name: payload, bad.name: payload})
    )
    into = tmp_path / "into"
    with pytest.raises(_fd.FrozenDraftError):
        _fd.unpack(archive, into)
    assert list(into.iterdir()) == []


def test_the_archive_is_unpacked_only_into_an_empty_folder(
    tmp_path: Path,
) -> None:
    archive, _ = _pair(tmp_path, {"index.html": b"x"})
    into = tmp_path / "into"
    into.mkdir()
    (into / "stale").write_text("x")
    with pytest.raises(_fd.FrozenDraftError, match="not an empty folder"):
        _fd.unpack(archive, into)


def test_the_cli_builds_and_verifies(tmp_path: Path) -> None:
    site = _site(tmp_path)
    out = tmp_path / "out"
    assert _fd.main([
        "build", "--site", str(site), "--out", str(out), "--draft", "draft-1",
        "--release", RELEASE, "--commit", SHA, "--publish-tag", PUBLISH,
        "--built", "2026-11-02",
    ]) == 0  # fmt: skip
    assert _fd.main([
        "verify", "--archive", str(out / ARCHIVE), "--manifest",
        str(out / MANIFEST), "--into", str(tmp_path / "into"),
    ]) == 0  # fmt: skip
    assert _fd.main([
        "verify", "--archive", str(out / ARCHIVE), "--manifest",
        str(out / MANIFEST), "--into", str(tmp_path / "into"),
    ]) == 1  # fmt: skip


# --- the promote, on a fixture repository -------------------------------------------


class _Releases:
    """A fake ``gh`` that keeps releases and their assets, as GitHub does.

    ``fail_upload`` makes ``release create`` fail after the release exists
    and before its second asset lands; ``tamper`` makes a download return
    bytes other than the stored ones; ``fail_delete`` makes ``release
    delete`` fail.
    """

    def __init__(self) -> None:
        self.releases: dict[str, dict[str, Any]] = {}
        self.calls: list[tuple[str, ...]] = []
        self.fail_upload = False
        self.tamper = False
        self.fail_delete = False

    def add(self, tag: str, *, draft: bool, assets: dict[str, bytes]) -> None:
        self.releases[tag] = {"draft": draft, "assets": dict(assets)}

    def __call__(self, *args: str, retry: bool = True) -> str:
        self.calls.append(args)
        assert args[0] == "release", args
        handler = getattr(self, f"_{args[1]}", None)
        if handler is None:
            raise AssertionError(f"unexpected gh call {args}")
        return str(handler(args[2], args, retry))

    def _view(self, tag: str, args: tuple[str, ...], retry: bool) -> str:
        if tag not in self.releases:
            raise subprocess.CalledProcessError(
                1, ["gh", *args], stderr="release not found\n"
            )
        found = self.releases[tag]
        return json.dumps(
            {
                "isDraft": found["draft"],
                "assets": [{"name": n} for n in found["assets"]],
            }
        )

    def _create(self, tag: str, args: tuple[str, ...], retry: bool) -> str:
        assert retry is False and "--draft" in args
        files = []
        for arg in args[3:]:
            if arg.startswith("--"):
                break
            files.append(Path(arg))
        self.add(tag, draft=True, assets={})
        for number, path in enumerate(files):
            if self.fail_upload and number == 1:
                raise subprocess.CalledProcessError(1, ["gh", *args])
            self.releases[tag]["assets"][path.name] = path.read_bytes()
        return f"https://github.com/O/R/releases/tag/{tag}\n"

    def _download(self, tag: str, args: tuple[str, ...], retry: bool) -> str:
        into = Path(args[args.index("--dir") + 1])
        into.mkdir(parents=True, exist_ok=True)
        wanted = [args[i + 1] for i, a in enumerate(args) if a == "--pattern"]
        for name in wanted:
            data = self.releases[tag]["assets"][name]
            if self.tamper and name.endswith(".tar.gz"):
                data = data + b"\0"
            (into / name).write_bytes(data)
        return ""

    def _delete(self, tag: str, args: tuple[str, ...], retry: bool) -> str:
        assert "--cleanup-tag" not in args
        if self.fail_delete:
            raise subprocess.CalledProcessError(1, ["gh", *args])
        del self.releases[tag]
        return ""

    def verbs(self) -> list[str]:
        return [c[1] for c in self.calls]


def _register_text(*entries: tuple[str, str, str | None]) -> str:
    text = "drafts:\n"
    for version, status, release in entries:
        text += f"  - version: {version}\n    status: {status}\n    date: 2026-11-06\n"
        if release:
            text += f"    release: {release}\n"
    return text


def _commit_register(repo: Path, *entries: tuple[str, str, str | None]) -> str:
    path = repo / dr.REGISTER_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_register_text(*entries), encoding="utf-8")
    git(repo, "add", "-A")
    git(
        repo,
        "commit",
        "-q",
        "-m",
        "register",
        when="2026-10-30T12:00:00+00:00",
    )
    return git(repo, "rev-parse", "HEAD")


def _remote_tags(repo: Path) -> set[str]:
    out = git(repo, "ls-remote", "--tags", "origin")
    return {
        ref.removeprefix("refs/tags/")
        for _, ref in (line.split("\t") for line in out.splitlines())
        if not ref.endswith("^{}")
    }


RELEASED = ("draft-1", "released", RELEASE)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A clone of a bare ``origin``, as the current directory."""
    isolate_git_config(monkeypatch)
    work = scratch_clone(tmp_path)
    git(work, "commit", "--allow-empty", "-q", "-m", "first")
    git(work, "push", "-q", "origin", "HEAD")
    monkeypatch.chdir(work)
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    def register_at(ref: str) -> Any:
        found = dr.load_register_at(ref, work)
        if found is None:
            return None
        return _rel.Register.from_json(json.loads(json.dumps(found.as_json())))

    monkeypatch.setattr(_rel, "register_at", register_at)
    monkeypatch.setattr(_rel, "_today", lambda: TODAY)
    return work


@pytest.fixture
def releases(monkeypatch: pytest.MonkeyPatch) -> _Releases:
    fake = _Releases()
    monkeypatch.setattr(_rel, "gh", fake)
    return fake


def _publish(repo: Path, *entries: tuple[str, str, str | None]) -> str:
    """Commit *entries* as the register and publish that commit."""
    commit = _commit_register(repo, *entries)
    tag_as_bot(repo, PUBLISH)
    return commit


def _frozen(tmp_path: Path, commit: str) -> Path:
    """The archive and manifest the frozen-draft job would upload."""
    out = tmp_path / "frozen-build"
    if out.exists():
        shutil.rmtree(out)
    _fd.build_archive(_site(out), out / "frozen", _draft(commit))
    return out / "frozen"


def _promote(
    frozen: Path | None, draft: str = "draft-1", release: str = RELEASE
) -> int:
    argv = [
        "promote", "--repo", "O/R", "--ref", MAIN, "--actor", "octocat",
        "--run-url", RUN_URL, "--publish-tag", "",
        "--planned-release", release, "--planned-draft", draft,
        "--frozen-dir", str(frozen or ""),
    ]  # fmt: skip
    return int(_rel.main(argv))


def _creates(fake: _Releases) -> list[tuple[str, ...]]:
    return [c for c in fake.calls if c[1] == "create"]


@pytest.mark.spec("DOCBW-08-009")
def test_a_release_that_carries_a_draft_is_created_with_both_files(
    repo: Path,
    releases: _Releases,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commit = _publish(repo, RELEASED)
    frozen = _frozen(tmp_path, commit)
    checked_before_the_tag: list[bool] = []
    original = _rel.verify_archive

    def spy(*args: Any) -> None:
        checked_before_the_tag.append(RELEASE not in _remote_tags(repo))
        original(*args)

    monkeypatch.setattr(_rel, "verify_archive", spy)
    assert _promote(frozen) == 0
    assert checked_before_the_tag == [True]
    assert RELEASE in _remote_tags(repo)
    (create,) = _creates(releases)
    assert create[2] == RELEASE and "--draft" in create
    assert {Path(a).name for a in create[3:5]} == {ARCHIVE, MANIFEST}
    stored = releases.releases[RELEASE]
    assert stored["draft"] is True  # never published by the run
    assert stored["assets"] == {
        ARCHIVE: (frozen / ARCHIVE).read_bytes(),
        MANIFEST: (frozen / MANIFEST).read_bytes(),
    }
    # The attached files were downloaded and compared (DOCBW-08-022).
    assert "download" in releases.verbs()
    assert not {"edit", "upload"} & set(releases.verbs())


@pytest.mark.spec("DOCBW-08-010")
@pytest.mark.parametrize(
    "entries",
    [
        [("draft-1", "unreleased", None)],
        # Released by an earlier release, which carried it.
        "earlier",
        # No register at all: a commit from before the register.
        [],
    ],
    ids=["open-draft", "earlier-draft", "no-register"],
)
def test_a_release_that_carries_no_draft_gets_no_asset(
    repo: Path, releases: _Releases, entries: Any
) -> None:
    if entries == "earlier":
        _commit_register(repo, ("draft-1", "released", "v2026.10.0"))
        tag_as_bot(repo, "v2026.10.0")
        releases.add("v2026.10.0", draft=False, assets={})
        _publish(
            repo,
            ("draft-1", "released", "v2026.10.0"),
            ("draft-2", "unreleased", None),
        )
    elif entries:
        _publish(repo, *entries)
    else:
        tag_as_bot(repo, PUBLISH)
    assert _promote(None, draft="") == 0
    (create,) = _creates(releases)
    assert create[3] == "--repo", "no file was named"
    assert releases.releases[RELEASE]["assets"] == {}


@pytest.mark.spec("DOCBW-08-011")
@pytest.mark.parametrize(
    "case", ["unmade-tag", "earlier-tag-never-carried-it"]
)
def test_a_register_naming_another_tag_is_refused(
    repo: Path,
    releases: _Releases,
    capsys: pytest.CaptureFixture[str],
    case: str,
) -> None:
    if case == "unmade-tag":
        _publish(repo, ("draft-1", "released", "v2026.12.0"))
        why = "v2026.12.0, which does not exist"
    else:
        _commit_register(repo, ("draft-1", "unreleased", None))
        tag_as_bot(repo, "v2026.10.0")
        _publish(
            repo,
            ("draft-1", "released", "v2026.10.0"),
            ("draft-2", "unreleased", None),
        )
        why = "never carried it"
    assert _promote(None, draft="") == 1
    assert why in capsys.readouterr().err
    made = {t.name for t in _tags.release_tags()}
    assert made == (set() if case == "unmade-tag" else {"v2026.10.0"})
    assert RELEASE not in _remote_tags(repo)
    assert releases.calls == []


@pytest.mark.spec("DOCBW-08-012")
def test_a_register_with_an_open_draft_beside_the_release_is_refused(
    repo: Path, releases: _Releases, tmp_path: Path
) -> None:
    commit = _publish(repo, RELEASED, ("draft-2", "unreleased", None))
    assert _promote(_frozen(tmp_path, commit)) == 1
    assert RELEASE not in _remote_tags(repo)
    assert releases.calls == []


@pytest.mark.spec("DOCBW-08-021")
@pytest.mark.parametrize(
    "fault", ["leaving-reference", "manifest-mismatch", "missing"]
)
def test_a_failed_archive_check_leaves_no_tag_and_no_release(
    repo: Path, releases: _Releases, tmp_path: Path, fault: str
) -> None:
    commit = _publish(repo, RELEASED)
    frozen = _frozen(tmp_path, commit)
    if fault == "leaving-reference":
        files = {"index.html": b'<a href="../../start/">x</a>'}
        (frozen / ARCHIVE).write_bytes(
            _fd.archive_bytes(files, _fd.datetime(2026, 11, 2))
        )
        (frozen / MANIFEST).write_text(_fd.manifest_text(files))
    elif fault == "manifest-mismatch":
        text = (frozen / MANIFEST).read_text()
        (frozen / MANIFEST).write_text("f" * 64 + text[64:])
    else:
        (frozen / MANIFEST).unlink()
    assert _promote(frozen) == 1
    assert RELEASE not in _remote_tags(repo)
    assert releases.releases == {}
    assert _creates(releases) == []


@pytest.mark.spec("DOCBW-08-022", "DOCBW-08-023")
@pytest.mark.parametrize("failure", ["upload", "check", "after-the-check"])
def test_a_failure_after_the_create_deletes_the_draft_release(
    repo: Path,
    releases: _Releases,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    commit = _publish(repo, RELEASED)
    if failure == "upload":
        releases.fail_upload = True
    elif failure == "check":
        releases.tamper = True
    else:
        real = _rel._report

        def report(title: str, text: str) -> None:
            if title == "Promoted":
                raise OSError("the summary could not be written")
            real(title, text)

        monkeypatch.setattr(_rel, "_report", report)
    with pytest.raises((subprocess.CalledProcessError, ValueError, OSError)):
        _promote(_frozen(tmp_path, commit))
    assert RELEASE in _remote_tags(repo)  # the tag stays
    assert releases.releases == {}
    assert "delete" in releases.verbs()


@pytest.mark.spec("DOCBW-08-022")
def test_an_attached_archive_that_differs_fails_the_run(
    repo: Path, releases: _Releases, tmp_path: Path
) -> None:
    commit = _publish(repo, RELEASED)
    releases.tamper = True
    with pytest.raises(
        _rel.PromotionRefusedError, match=f"{ARCHIVE}, which differ"
    ):
        _promote(_frozen(tmp_path, commit))


@pytest.mark.spec("DOCBW-08-037")
def test_a_failed_delete_says_the_draft_release_must_not_be_published(
    repo: Path,
    releases: _Releases,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    commit = _publish(repo, RELEASED)
    releases.fail_upload = True
    releases.fail_delete = True
    with pytest.raises(_rel.IncompleteDraftReleaseError) as caught:
        _promote(_frozen(tmp_path, commit))
    message = str(caught.value)
    assert f"The draft release {RELEASE} is incomplete" in message
    assert "must not be published" in message
    assert message in capsys.readouterr().err
    assert RELEASE in releases.releases


@pytest.mark.spec("DOCBW-08-024", "DOCBW-07-016")
def test_a_rerun_finding_a_complete_draft_release_leaves_it_alone(
    repo: Path,
    releases: _Releases,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """AC-3: a re-run that finds the archive attached does not replace it."""
    commit = _publish(repo, RELEASED)
    assert _promote(_frozen(tmp_path, commit)) == 0
    before = json.dumps(releases.releases[RELEASE], default=bytes.hex)
    calls = len(releases.calls)
    # The second run builds its own archive, with other bytes.
    assert _promote(_frozen(tmp_path, commit)) == 1
    err = capsys.readouterr().err
    assert f"the draft release {RELEASE} is complete" in err
    assert "waiting for the maintainer to publish it" in err
    assert json.dumps(releases.releases[RELEASE], default=bytes.hex) == before
    assert {c[1] for c in releases.calls[calls:]} <= {"view", "download"}
    assert [t.name for t in _tags.release_tags()] == [RELEASE]


def _left_by_a_stopped_run(
    repo: Path, releases: _Releases, tmp_path: Path, kind: str
) -> str:
    """The tag and an incomplete draft release a run stopped from outside left.

    Returns the promoted commit.
    """
    commit = _publish(repo, RELEASED)
    tag_as_bot(repo, RELEASE)
    git(repo, "push", "-q", "origin", f"refs/tags/{RELEASE}")
    old = _frozen(tmp_path / "old", commit)
    assets = {ARCHIVE: (old / ARCHIVE).read_bytes()}
    if kind == "mismatched":
        assets[MANIFEST] = b"0" * 64 + b"  index.html\n"
    releases.add(RELEASE, draft=True, assets=assets)
    return commit


@pytest.mark.spec("DOCBW-08-025", "DOCBW-07-010")
@pytest.mark.parametrize("kind", ["archive-only", "mismatched"])
def test_a_rerun_finding_an_incomplete_draft_release_replaces_it(
    repo: Path, releases: _Releases, tmp_path: Path, kind: str
) -> None:
    commit = _left_by_a_stopped_run(repo, releases, tmp_path, kind)
    tags_before = _remote_tags(repo)
    frozen = _frozen(tmp_path, commit)
    assert _promote(frozen) == 0
    assert "delete" in releases.verbs()
    assert releases.releases[RELEASE]["assets"] == {
        ARCHIVE: (frozen / ARCHIVE).read_bytes(),
        MANIFEST: (frozen / MANIFEST).read_bytes(),
    }
    assert _remote_tags(repo) == tags_before  # no new tag
    assert [t.name for t in _tags.release_tags()] == [RELEASE]


@pytest.mark.spec("DOCBW-08-026", "DOCBW-07-016")
def test_a_published_release_without_the_pair_is_refused(
    repo: Path,
    releases: _Releases,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    commit = _left_by_a_stopped_run(repo, releases, tmp_path, "archive-only")
    releases.releases[RELEASE]["draft"] = False
    before = dict(releases.releases[RELEASE]["assets"])
    assert _promote(_frozen(tmp_path, commit)) == 1
    err = capsys.readouterr().err
    assert f"the published release {RELEASE} lacks a matching archive" in err
    assert "cannot take the archive" in err
    assert releases.releases[RELEASE]["assets"] == before
    assert _creates(releases) == []


@pytest.mark.spec("DOCBW-07-016")
def test_a_published_release_with_the_pair_is_released_already(
    repo: Path,
    releases: _Releases,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    commit = _publish(repo, RELEASED)
    assert _promote(_frozen(tmp_path, commit)) == 0
    releases.releases[RELEASE]["draft"] = False
    assert _promote(_frozen(tmp_path, commit)) == 1
    assert "it is released already" in capsys.readouterr().err


def test_a_plan_that_changed_is_refused(
    repo: Path, releases: _Releases, tmp_path: Path
) -> None:
    commit = _publish(repo, RELEASED)
    frozen = _frozen(tmp_path, commit)
    assert _promote(frozen, release="v2026.11.1") == 1
    assert _promote(frozen, draft="") == 1
    assert releases.calls == []
    assert RELEASE not in _remote_tags(repo)


@pytest.mark.spec("DOCBW-08-009")
@pytest.mark.parametrize("carries", [True, False])
def test_the_plan_names_the_release_and_its_draft(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, carries: bool
) -> None:
    entry = RELEASED if carries else ("draft-1", "unreleased", None)
    commit = _publish(repo, entry)
    out = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    assert _rel.main(["plan", "--ref", MAIN, "--publish-tag", ""]) == 0
    assert out.read_text() == (
        f"commit={commit}\npublish-tag={PUBLISH}\npublish-date=2026-11-02\n"
        f"release={RELEASE}\ndraft={'draft-1' if carries else ''}\n"
    )
    assert (
        _rel.main(["plan", "--ref", "refs/heads/x", "--publish-tag", ""]) == 1
    )


def test_register_at_reads_mains_drafts_register(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []
    answers = iter(
        [
            json.dumps(
                {
                    "register": "x",
                    "current": {"version": "draft-2", "date": "2026-11-07"},
                    "released": [
                        {
                            "version": "draft-1",
                            "date": "2026-11-06",
                            "release": RELEASE,
                        }
                    ],
                }
            ),
            "null\n",
        ]
    )

    def run(*argv: str) -> str:
        calls.append(argv)
        return next(answers)

    monkeypatch.setattr(_rel, "run", run)
    register = _rel.register_at("abc")
    assert register.released_by(RELEASE) == _rel.DraftEntry(
        "draft-1", "2026-11-06", RELEASE
    )
    assert register.current == _rel.DraftEntry("draft-2", "2026-11-07")
    assert _rel.register_at("old") is None
    assert calls[0][:4] == ("uv", "run", "--no-sync", "drafts-register")
    assert calls[0][-3:] == ("--ref", "abc", "--absent-ok")


@pytest.mark.spec("DOCBW-08-037")
def test_a_release_no_longer_a_draft_is_never_deleted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _Releases()
    fake.add(RELEASE, draft=False, assets={})
    monkeypatch.setattr(_rel, "gh", fake)
    with pytest.raises(_rel.IncompleteDraftReleaseError):
        _rel.discard_draft_release("O/R", RELEASE)
    assert "delete" not in fake.verbs()


# --- the workflow ---------------------------------------------------------------------


def _jobs() -> dict[str, Any]:
    return dict(load_workflow(PROMOTE)["jobs"])


@pytest.mark.spec("DOCBW-08-019")
def test_the_archive_job_cannot_write() -> None:
    job = _jobs()["frozen-draft"]
    assert job["permissions"] == {"contents": "read"}
    assert job["if"] == "needs.plan.outputs.draft != ''"
    uses = [str(s.get("uses", "")) for s in job["steps"]]
    assert BUILD_SITE_ACTION in uses
    (build,) = [s for s in job["steps"] if s.get("uses") == BUILD_SITE_ACTION]
    assert build["with"] == {"ref": "${{ needs.plan.outputs.commit }}"}
    # DOCBW-08-014: the build inputs name the publish and the release.
    assert build["env"] == {
        "VULTRON_PUBLISH_TAG": "${{ needs.plan.outputs.publish-tag }}",
        "VULTRON_PUBLISH_DATE": "${{ needs.plan.outputs.publish-date }}",
        "VULTRON_RELEASE_TAG": "${{ needs.plan.outputs.release }}",
    }
    # The archive is built by main's script, checked out after the build.
    (scripts,) = [
        s for s in job["steps"]
        if str(s.get("uses", "")).startswith("actions/checkout@")
        and s.get("with", {}).get("path") == ".promote"
    ]  # fmt: skip
    assert scripts["with"]["ref"] == "${{ github.sha }}"
    assert uses.index(BUILD_SITE_ACTION) < job["steps"].index(scripts)
    assert any(
        ".promote/.github/scripts/frozen_draft.py build"
        in str(s.get("run", ""))
        for s in job["steps"]
    )


@pytest.mark.spec("DOCBW-08-020")
def test_the_attaching_job_runs_only_mains_code() -> None:
    jobs = _jobs()
    job = jobs["promote"]
    assert job["needs"] == ["plan", "frozen-draft"]
    for step in job["steps"]:
        uses = str(step.get("uses", ""))
        assert uses != BUILD_SITE_ACTION
        if uses.startswith("actions/checkout@"):
            assert "ref" not in step.get("with", {}), "checks out main only"
    (download,) = [
        s for s in job["steps"]
        if str(s.get("uses", "")).startswith("actions/download-artifact@")
    ]  # fmt: skip
    (upload,) = [
        s for s in jobs["frozen-draft"]["steps"]
        if str(s.get("uses", "")).startswith("actions/upload-artifact@")
    ]  # fmt: skip
    # The newest archive attempt not later than this job's own.
    assert upload["with"]["name"] == (
        _rel.FROZEN_ARTIFACT_PREFIX + "${{ github.run_attempt }}"
    )
    (find,) = [s for s in job["steps"] if s.get("id") == "artifact"]
    assert "release.py frozen-artifact" in find["run"]
    assert find["env"]["RUN_ATTEMPT"] == "${{ github.run_attempt }}"
    assert download["with"]["name"] == "${{ steps.artifact.outputs.name }}"
    assert job["permissions"] == {"contents": "write", "actions": "read"}
    assert download["with"]["path"] == "frozen/"
    (promote,) = [
        s for s in job["steps"] if "release.py promote" in str(s.get("run"))
    ]
    assert "--frozen-dir frozen" in promote["run"]
    assert (
        promote["env"]["PLANNED_RELEASE"]
        == "${{ needs.plan.outputs.release }}"
    )
    assert promote["env"]["PLANNED_DRAFT"] == "${{ needs.plan.outputs.draft }}"
    # It runs for a release with no draft, whose archive job is skipped.
    assert "needs.frozen-draft.result == 'skipped'" in job["if"]


@pytest.mark.spec("DOCBW-08-009")
def test_the_run_never_publishes_the_release() -> None:
    """The maintainer publishes the draft release by hand (ADR-0188)."""
    source = Path(str(_rel.__file__)).read_text(encoding="utf-8")
    assert '"edit"' not in source and "--draft=false" not in source
    assert '"--draft",' in source


# --- failure branches -------------------------------------------------------------


def test_a_duplicate_member_is_refused(tmp_path: Path) -> None:
    one = _file("index.html", b"a")
    two = _file("index.html", b"b")
    archive = tmp_path / ARCHIVE
    archive.write_bytes(_tar([one, two], {"index.html": b"a"}))
    with pytest.raises(_fd.FrozenDraftError, match="listed twice"):
        _fd.unpack(archive, tmp_path / "into")


@pytest.mark.parametrize("damage", ["truncated", "not-gzip"])
def test_a_damaged_archive_is_refused(tmp_path: Path, damage: str) -> None:
    archive, manifest = _pair(tmp_path, {"index.html": b"<p>x</p>" * 500})
    data = archive.read_bytes()
    archive.write_bytes(
        data[: len(data) // 2] if damage == "truncated" else b"x"
    )
    with pytest.raises(_fd.FrozenDraftError, match=ARCHIVE):
        _fd.verify_archive(archive, manifest)


@pytest.mark.parametrize(
    ("text", "fault"),
    [
        ("not a line\n", "not a sha256sum line"),
        (f"{'a' * 64}  x\n{'b' * 64}  x\n", "x is listed twice"),
        ("", "lists no file"),
    ],
    ids=["malformed", "twice", "empty"],
)
def test_a_malformed_manifest_is_named(text: str, fault: str) -> None:
    assert fault in " ".join(_fd.read_manifest(text, MANIFEST)[1])


def test_a_site_without_a_canonical_link_is_refused(tmp_path: Path) -> None:
    index = _page("x", head="")
    with pytest.raises(_fd.FrozenDraftError, match="no canonical link"):
        _build(tmp_path, **{"index.html": index})


def test_a_symlinked_site_file_is_refused(tmp_path: Path) -> None:
    site = _site(tmp_path)
    target = site / "assets" / "app.js"
    target.unlink()
    target.symlink_to(site / "assets" / "main.css")
    with pytest.raises(
        _fd.FrozenDraftError, match=r"app\.js: not a regular file"
    ):
        _fd.build_archive(site, tmp_path / "frozen", _draft())


def test_a_file_name_the_manifest_cannot_hold_is_refused(
    tmp_path: Path,
) -> None:
    with pytest.raises(_fd.FrozenDraftError, match="the manifest cannot hold"):
        _build(tmp_path, **{"odd\nname.txt": "x"})


@pytest.mark.spec("DOCBW-08-022")
def test_a_built_file_that_was_never_attached_fails_the_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        _rel, "gh", lambda *a, retry=True: ""
    )  # downloads nothing
    built = tmp_path / ARCHIVE
    built.write_bytes(b"x")
    with pytest.raises(
        _rel.PromotionRefusedError, match="differ from the files"
    ):
        _rel.check_attached("O/R", RELEASE, [built])


@pytest.mark.spec("DOCBW-08-024")
def test_an_extra_asset_does_not_make_a_complete_draft_incomplete(
    repo: Path,
    releases: _Releases,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    commit = _publish(repo, RELEASED)
    assert _promote(_frozen(tmp_path, commit)) == 0
    releases.releases[RELEASE]["assets"]["notes.txt"] = b"extra"
    assert _promote(_frozen(tmp_path, commit)) == 1
    assert "is complete" in capsys.readouterr().err
    assert "delete" not in releases.verbs()
    releases.releases[RELEASE]["draft"] = False
    assert _promote(_frozen(tmp_path, commit)) == 1
    assert "it is released already" in capsys.readouterr().err


@pytest.mark.spec("DOCBW-08-025", "DOCBW-08-037")
def test_a_failed_delete_of_an_incomplete_draft_says_so(
    repo: Path,
    releases: _Releases,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commit = _left_by_a_stopped_run(repo, releases, tmp_path, "archive-only")
    releases.fail_delete = True
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    with pytest.raises(_rel.IncompleteDraftReleaseError):
        _promote(_frozen(tmp_path, commit))
    assert "Draft release incomplete" in summary.read_text()
    assert _creates(releases) == []


def test_the_failure_summary_says_whether_it_deleted_a_release(
    repo: Path,
    releases: _Releases,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A create that fails before landing leaves nothing to delete."""
    commit = _publish(repo, RELEASED)

    def refused(tag: str, args: tuple[str, ...], retry: bool) -> str:
        raise subprocess.CalledProcessError(1, ["gh", *args])

    monkeypatch.setattr(releases, "_create", refused)
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    with pytest.raises(subprocess.CalledProcessError):
        _promote(_frozen(tmp_path, commit))
    assert f"it left no draft release {RELEASE}" in summary.read_text()


@pytest.mark.parametrize(
    ("names", "attempt", "taken"),
    [
        (["frozen-draft-attempt-1", "frozen-draft-attempt-2"], 2, "2"),
        (["frozen-draft-attempt-1"], 3, "1"),  # the promote job re-run alone
        (["frozen-draft-attempt-1", "frozen-draft-attempt-3"], 2, "1"),
    ],
)
def test_the_promote_takes_the_newest_archive_not_later_than_its_attempt(
    names: list[str], attempt: int, taken: str
) -> None:
    assert (
        _rel.frozen_artifact(names, attempt) == f"frozen-draft-attempt-{taken}"
    )


def test_no_archive_artifact_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with pytest.raises(_rel.PromotionRefusedError, match="attempts 1 to 2"):
        _rel.frozen_artifact(["other"], 2)
    monkeypatch.setattr(
        _rel,
        "paginated",
        lambda endpoint, key=None: [{"name": "frozen-draft-attempt-1"}],
    )
    out = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    argv = [
        "frozen-artifact",
        "--repo",
        "O/R",
        "--run-id",
        "7",
        "--attempt",
        "2",
    ]
    assert _rel.main(argv) == 0
    assert out.read_text() == "name=frozen-draft-attempt-1\n"
