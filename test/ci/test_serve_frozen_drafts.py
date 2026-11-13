"""CI verification test — every site build serves each released draft's frozen pages.

Implements the serving side of DOCBW-08 (ADR-0188, #6287): DOCBW-08-027 to
DOCBW-08-035. DOCBW-08-036 is covered beside the checks it exempts, in
``test/metadata/docs/test_legacy_urls.py`` and ``test_path_boxes.py``, and
DOCBW-08-038 beside the rollback gate, in ``test/ci/test_publish_gate.py``.

``.github/scripts/serve_frozen_drafts.py`` serves fixture archives, built by
``frozen_draft.py`` from the fixture site of ``test_frozen_drafts.py``, into
a fixture ``site/``, with ``gh`` replaced by the same fake that keeps a
repository's releases and their assets. The workflows that run it,
``deploy_site.yml`` and ``docs-build-check.yml``, are read for the job and
the step order.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tarfile
from pathlib import Path
from typing import Any

import pytest

from test.ci._scratch_git import git, isolate_git_config, scratch_clone
from test.ci._scripts import load_script
from test.ci._workflows import (
    BUILD_SITE_ACTION,
    WORKFLOWS_DIR,
    load_workflow,
    local_action_steps,
    site_building_workflows,
    triggers,
)
from test.ci.test_frozen_drafts import (
    ARCHIVE,
    MANIFEST,
    RELEASE,
    _build,
    _commit_register,
    _file,
    _pair,
    _Releases,
    _tar,
)
from vultron.metadata.docs import drafts_register as dr

_rel = load_script("release")
# The release lookup lives in its own module, so a fake gh patches both.
_releases = load_script("github_releases")
_fd = load_script("frozen_draft")
_serve = load_script("serve_frozen_drafts")

DEPLOY = WORKFLOWS_DIR / "deploy_site.yml"
REVIEW = WORKFLOWS_DIR / "docs-build-check.yml"
PROMOTE = WORKFLOWS_DIR / "promote_release.yml"
SERVE_ACTION = "./.github/actions/serve-frozen-drafts"
PUBLICATION_CHECKS = "./.github/actions/check-site-publication"
LATER = "v2026.12.0"


class _FlakyReleases(_Releases):
    """The fake ``gh``, whose first *tampered* archive downloads are corrupt.

    A corrupt download here is a well-formed archive of other files, so it
    fails its manifest rather than failing to unpack.
    """

    def __init__(self, tampered: int = 0) -> None:
        super().__init__()
        self.tampered = tampered

    def _download(self, tag: str, args: tuple[str, ...], retry: bool) -> str:
        out = super()._download(tag, args, retry)
        if self.tampered > 0:
            self.tampered -= 1
            into = Path(args[args.index("--dir") + 1])
            (into / ARCHIVE).write_bytes(
                _fd.archive_bytes(
                    {"index.html": b"other"}, _fd.datetime(2026, 11, 2)
                )
            )
        return out


@pytest.fixture
def releases(monkeypatch: pytest.MonkeyPatch) -> _FlakyReleases:
    fake = _FlakyReleases()
    monkeypatch.setattr(_rel, "gh", fake)
    monkeypatch.setattr(_releases, "gh", fake)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    return fake


def _register(*released: tuple[str, str]) -> Any:
    return _rel.Register(
        None,
        tuple(
            _rel.DraftEntry(version, "2026-11-06", release)
            for version, release in released
        ),
    )


def _built_site(tmp_path: Path) -> Path:
    """What the shared build leaves: nothing below ``spec/``.

    Beside, not in, the fixture site ``_build`` makes the archive from.
    """
    site = tmp_path / "deploy" / "site"
    (site / "reference/vultron-spec").mkdir(parents=True)
    (site / "index.html").write_text("<p>home</p>")
    (site / "reference/vultron-spec/index.html").write_text("<p>spec</p>")
    return site


def _publish_pair(
    fake: _Releases, archive: Path, manifest: Path, tag: str = RELEASE
) -> None:
    fake.add(
        tag,
        draft=False,
        assets={
            ARCHIVE: archive.read_bytes(),
            MANIFEST: manifest.read_bytes(),
        },
    )


def _serve_into(site: Path, register: Any) -> list[str]:
    """The summary lines of a serve that must succeed; its faults raise."""
    lines, faults = _serve.serve(register, site, "O/R")
    if faults:
        raise _fd.FrozenDraftError(faults)
    return list(lines)


def _register_file(tmp_path: Path, data: object) -> Path:
    path = tmp_path / "register.json"
    path.write_text(json.dumps(data))
    return path


def _released_json(*released: tuple[str, str]) -> dict[str, object]:
    return {
        "register": dr.REGISTER_PATH,
        "current": None,
        "released": [
            {"version": version, "date": "2026-11-06", "release": release}
            for version, release in released
        ],
    }


def _downloads(fake: _Releases) -> int:
    return sum(1 for verb in fake.verbs() if verb == "download")


# --- serving a published draft (DOCBW-08-028, DOCBW-08-030) ---------------------


@pytest.mark.spec("DOCBW-08-028", "DOCBW-08-030")
def test_a_published_draft_is_served_byte_for_byte_as_its_manifest_lists(
    tmp_path: Path, releases: _FlakyReleases
) -> None:
    archive, manifest = _build(tmp_path)
    _publish_pair(releases, archive, manifest)
    site = _built_site(tmp_path)
    lines = _serve_into(site, _register(("draft-1", RELEASE)))
    served = site / "spec/draft-1"
    listed = {
        name: digest
        for digest, name in (
            line.split("  ", 1) for line in manifest.read_text().splitlines()
        )
    }
    files = {
        p.relative_to(served).as_posix(): p
        for p in served.rglob("*")
        if p.is_file()
    }
    assert set(files) == set(listed)
    for name, path in files.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == listed[name]
    assert (served / "index.html").is_file()
    assert lines == [f"- `draft-1`: served from release `{RELEASE}`."]
    # The rest of the site is left as the build wrote it.
    assert (site / "reference/vultron-spec/index.html").read_text() == (
        "<p>spec</p>"
    )


@pytest.mark.spec("DOCBW-08-030")
def test_a_corrupt_download_is_tried_once_more(
    tmp_path: Path, releases: _FlakyReleases
) -> None:
    """A published release never changes, so a mismatch is first taken for
    a corrupt download."""
    archive, manifest = _build(tmp_path)
    _publish_pair(releases, archive, manifest)
    releases.tampered = 1
    site = _built_site(tmp_path)
    _serve_into(site, _register(("draft-1", RELEASE)))
    assert (site / "spec/draft-1/index.html").is_file()
    assert _downloads(releases) == 2


@pytest.mark.spec("DOCBW-08-030", "DOCBW-08-033")
def test_an_archive_that_fails_twice_fails_naming_the_draft_and_release(
    tmp_path: Path, releases: _FlakyReleases
) -> None:
    archive, manifest = _build(tmp_path)
    _publish_pair(releases, archive, manifest)
    releases.tampered = 99
    site = _built_site(tmp_path)
    lines, faults = _serve.serve(_register(("draft-1", RELEASE)), site, "O/R")
    assert _downloads(releases) == _serve.DOWNLOAD_ATTEMPTS == 2
    assert lines == [
        f"- `draft-1`: **failed**, the archive of release `{RELEASE}` does "
        "not match its manifest."
    ]
    assert faults
    assert all(
        f.startswith(f"draft-1 (release {RELEASE}): attempt ") for f in faults
    )
    # Both attempts' faults are kept.
    assert {f.split(": ")[1] for f in faults} == {"attempt 1", "attempt 2"}
    assert not (site / "spec").exists()


@pytest.mark.spec("DOCBW-08-030")
@pytest.mark.parametrize("fault", ["missing", "extra", "changed"])
def test_a_tree_that_is_not_its_manifest_is_not_served(
    tmp_path: Path, releases: _FlakyReleases, fault: str
) -> None:
    archive, manifest = _pair(
        tmp_path, {"index.html": b"<p>x</p>", "a.css": b"a{}"}
    )
    lines = manifest.read_text().splitlines()
    if fault == "changed":
        lines[0] = "0" * 64 + lines[0][64:]
    elif fault == "missing":
        lines.append(f"{'1' * 64}  gone.html")
    else:
        lines = lines[1:]
    manifest.write_text("\n".join(lines) + "\n")
    _publish_pair(releases, archive, manifest)
    site = _built_site(tmp_path)
    with pytest.raises(_fd.FrozenDraftError) as caught:
        _serve_into(site, _register(("draft-1", RELEASE)))
    assert {
        "changed": "its SHA-256 is not the listed one",
        "missing": "gone.html: listed, but not in the archive",
        "extra": "in the archive, but not listed",
    }[fault] in str(caught.value)
    assert not (site / "spec").exists()


def test_serving_does_not_judge_the_archives_references(
    tmp_path: Path, releases: _FlakyReleases
) -> None:
    """The promote checked the references once; a later, stricter rule must
    not fail an archive that can never change (ADR-0188)."""
    archive, manifest = _pair(
        tmp_path, {"index.html": b'<a href="../../../nowhere/">x</a>'}
    )
    with pytest.raises(_fd.FrozenDraftError, match="leaves the archive"):
        _fd.verify_archive(archive, manifest)
    _publish_pair(releases, archive, manifest)
    site = _built_site(tmp_path)
    _serve_into(site, _register(("draft-1", RELEASE)))
    assert (site / "spec/draft-1/index.html").is_file()


# --- unsafe archives (DOCBW-08-029) -------------------------------------------------


@pytest.mark.spec("DOCBW-08-029")
@pytest.mark.parametrize("kind", ["absolute", "dotdot", "symlink"])
def test_an_unsafe_member_is_refused_and_nothing_is_written(
    tmp_path: Path, releases: _FlakyReleases, kind: str
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
    manifest = tmp_path / MANIFEST
    manifest.write_text(f"{hashlib.sha256(payload).hexdigest()}  index.html\n")
    _publish_pair(releases, archive, manifest)
    site = _built_site(tmp_path)
    before = sorted(p for p in tmp_path.rglob("*") if "evil" in p.name)
    with pytest.raises(_fd.FrozenDraftError) as caught:
        _serve_into(site, _register(("draft-1", RELEASE)))
    assert {
        "absolute": "an absolute path",
        "dotdot": "a '..' component",
        "symlink": "neither a regular file nor a folder",
    }[kind] in str(caught.value)
    assert not (site / "spec").exists()
    assert sorted(p for p in tmp_path.rglob("*") if "evil" in p.name) == before


# --- unpublished and broken releases (DOCBW-08-032, DOCBW-08-033) -------------------


@pytest.mark.spec("DOCBW-08-032")
@pytest.mark.parametrize("state", ["no-tag", "no-release", "draft-release"])
def test_an_unpublished_release_gets_a_placeholder_and_a_summary_line(
    tmp_path: Path, releases: _FlakyReleases, state: str
) -> None:
    """``gh release view`` answers "not found" both for a tag that does not
    exist and for one with no release; a read-only token also gets it for a
    draft release, which a token that can see it reports as a draft."""
    if state == "draft-release":
        archive, _manifest = _build(tmp_path)
        releases.add(
            RELEASE, draft=True, assets={ARCHIVE: archive.read_bytes()}
        )
    site = _built_site(tmp_path)
    lines = _serve_into(site, _register(("draft-1", RELEASE)))
    page = (site / "spec/draft-1/index.html").read_text()
    assert RELEASE in page and "not published yet" in page
    assert [p.name for p in (site / "spec/draft-1").iterdir()] == [
        "index.html"
    ]
    assert lines == [
        f"- `draft-1`: release `{RELEASE}` is not published yet; a "
        "placeholder page is served."
    ]
    assert _downloads(releases) == 0
    # The placeholder's own links resolve in the site the link check reads.
    assert _fd.reference_faults(site) == []


@pytest.mark.spec("DOCBW-08-033")
@pytest.mark.parametrize("lacks", [ARCHIVE, MANIFEST])
def test_a_published_release_lacking_a_file_fails_naming_both(
    tmp_path: Path, releases: _FlakyReleases, lacks: str
) -> None:
    archive, manifest = _build(tmp_path)
    assets = {ARCHIVE: archive.read_bytes(), MANIFEST: manifest.read_bytes()}
    del assets[lacks]
    releases.add(RELEASE, draft=False, assets=assets)
    site = _built_site(tmp_path)
    with pytest.raises(_fd.FrozenDraftError) as caught:
        _serve_into(site, _register(("draft-1", RELEASE)))
    assert caught.value.faults == [
        f"draft-1 (release {RELEASE}): the published release lacks {lacks}"
    ]
    assert _downloads(releases) == 0


@pytest.mark.spec("DOCBW-08-032", "DOCBW-08-033")
def test_every_draft_is_tried_before_the_step_fails(
    tmp_path: Path, releases: _FlakyReleases
) -> None:
    archive, _manifest = _build(tmp_path)
    releases.add(RELEASE, draft=False, assets={ARCHIVE: archive.read_bytes()})
    site = _built_site(tmp_path)
    with pytest.raises(_fd.FrozenDraftError) as caught:
        _serve_into(site, _register(("draft-1", RELEASE), ("draft-2", LATER)))
    assert caught.value.faults == [
        f"draft-1 (release {RELEASE}): the published release lacks {MANIFEST}"
    ]
    assert (site / "spec/draft-2/index.html").is_file()


@pytest.mark.spec("DOCBW-08-028")
def test_a_register_with_no_released_draft_serves_nothing(
    tmp_path: Path, releases: _FlakyReleases
) -> None:
    site = _built_site(tmp_path)
    assert _serve_into(site, _register()) == []
    assert not (site / "spec").exists()
    assert releases.calls == []


# --- spec/ is reserved (DOCBW-08-034) ----------------------------------------------


@pytest.mark.spec("DOCBW-08-034")
@pytest.mark.parametrize("built", ["spec/draft-1/index.html", "spec/x.html"])
def test_a_build_that_wrote_below_spec_fails_before_serving(
    tmp_path: Path, releases: _FlakyReleases, built: str
) -> None:
    site = _built_site(tmp_path)
    (site / built).parent.mkdir(parents=True)
    (site / built).write_text("<p>built</p>")
    with pytest.raises(_fd.FrozenDraftError) as caught:
        _serve_into(site, _register(("draft-1", RELEASE)))
    assert caught.value.faults == [
        f"{built}: the build wrote it, but spec/ holds frozen drafts only"
    ]
    assert releases.calls == []


@pytest.mark.spec("DOCBW-08-034")
def test_a_build_that_wrote_a_file_named_spec_fails(
    tmp_path: Path, releases: _FlakyReleases
) -> None:
    site = _built_site(tmp_path)
    (site / "spec").write_text("x")
    with pytest.raises(_fd.FrozenDraftError, match="where frozen drafts go"):
        _serve_into(site, _register())


# --- the command ----------------------------------------------------------------------


@pytest.mark.spec("DOCBW-08-032", "DOCBW-08-033")
def test_the_command_writes_the_run_summary_and_fails_loudly(
    tmp_path: Path,
    releases: _FlakyReleases,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    register = tmp_path / "register.json"
    data = {
        "register": dr.REGISTER_PATH,
        "current": None,
        "released": [
            {"version": "draft-1", "date": "2026-11-06", "release": RELEASE}
        ],
    }
    register.write_text(json.dumps(data))
    argv = ["--register", str(register), "--repo", "O/R"]
    assert _serve.main([*argv, "--site", str(_built_site(tmp_path))]) == 0
    assert "`draft-1`: release `v2026.11.0` is not published yet" in (
        summary.read_text()
    )
    releases.add(RELEASE, draft=False, assets={})
    other = _built_site(tmp_path / "other")
    assert _serve.main([*argv, "--site", str(other)]) == 1
    err = capsys.readouterr().err
    assert f"::error::draft-1 (release {RELEASE}): the published" in err
    assert "Frozen drafts: failed" in summary.read_text()


@pytest.mark.parametrize(
    "data",
    [
        None,
        [1, 2],
        {"current": None},
        {"current": None, "released": {"a": 1}},
        {"current": None, "released": ["draft-1"]},
        {"current": "draft-2", "released": []},
    ],
)
def test_the_command_refuses_a_register_that_is_not_one(
    tmp_path: Path,
    releases: _FlakyReleases,
    monkeypatch: pytest.MonkeyPatch,
    data: object,
) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    register = _register_file(tmp_path, data)
    argv = ["--register", str(register), "--repo", "O/R"]
    assert _serve.main([*argv, "--site", str(_built_site(tmp_path))]) == 1
    assert "not a drafts register" in summary.read_text()
    assert releases.calls == []


@pytest.mark.parametrize(
    ("released", "fault"),
    [
        (
            [{"version": "draft-1", "date": "2026-11-06", "release": None}],
            "released entry 0: no release tag",
        ),
        (
            [{"version": "draft-1", "date": "2026-11-06"}],
            "released entry 0: no release tag",
        ),
        (
            [{"version": "../x", "date": "2026-11-06", "release": RELEASE}],
            "released entry 0: not a draft-N version",
        ),
        (
            [
                {
                    "version": "draft-1",
                    "date": "2026-11-06",
                    "release": RELEASE,
                },
                {"version": "draft-1", "date": "2026-11-06", "release": LATER},
            ],
            "draft-1 is released twice",
        ),
    ],
    ids=["null-release", "no-release", "unsafe-version", "repeated-version"],
)
def test_the_command_refuses_a_released_entry_it_cannot_serve(
    tmp_path: Path,
    releases: _FlakyReleases,
    monkeypatch: pytest.MonkeyPatch,
    released: list[dict[str, object]],
    fault: str,
) -> None:
    """A released entry's version names its folder below spec/, and its
    release is the tag looked up, so each must be usable before any lookup."""
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    register = _register_file(
        tmp_path, {"current": None, "released": released}
    )
    argv = ["--register", str(register), "--repo", "O/R"]
    assert _serve.main([*argv, "--site", str(_built_site(tmp_path))]) == 1
    assert fault in summary.read_text()
    assert releases.calls == []


@pytest.mark.spec("DOCBW-08-032", "DOCBW-08-033")
def test_a_failed_run_still_names_every_draft_in_the_summary(
    tmp_path: Path,
    releases: _FlakyReleases,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One draft fails and another is unpublished: the summary carries the
    placeholder line, the failure line and the fault."""
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    releases.add(RELEASE, draft=False, assets={})
    register = _register_file(
        tmp_path, _released_json(("draft-1", RELEASE), ("draft-2", LATER))
    )
    site = _built_site(tmp_path)
    argv = ["--register", str(register), "--repo", "O/R", "--site", str(site)]
    assert _serve.main(argv) == 1
    text = summary.read_text()
    assert "### Frozen drafts: failed" in text
    assert f"- `draft-1`: **failed**, release `{RELEASE}` lacks" in text
    assert (
        f"- `draft-2`: release `{LATER}` is not published yet; a placeholder "
        "page is served." in text
    )
    assert (
        f"- draft-1 (release {RELEASE}): the published release lacks" in text
    )


# --- main's register (DOCBW-08-027) ---------------------------------------------------


@pytest.mark.spec("DOCBW-08-027")
def test_a_rollback_still_serves_a_draft_released_after_its_target(
    tmp_path: Path,
    releases: _FlakyReleases,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The site rolls back to a commit whose register still holds draft-1 as
    unreleased; main's register, which the deploy reads, has released it."""
    isolate_git_config(monkeypatch)
    work = scratch_clone(tmp_path / "repo")
    target = _commit_register(work, ("draft-1", "unreleased", None))
    main = _commit_register(work, ("draft-1", "released", RELEASE))
    assert dr.load_register_at(target, work).released == ()  # type: ignore[union-attr]
    archive, manifest = _build(tmp_path)
    _publish_pair(releases, archive, manifest)
    git(work, "checkout", "-q", target)
    found = dr.load_register_at(main, work)
    assert found is not None
    site = _built_site(tmp_path)
    _serve_into(site, _rel.Register.from_json(found.as_json()))
    assert (site / "spec/draft-1/index.html").is_file()


def _job(path: Path, name: str) -> dict[str, Any]:
    return dict(load_workflow(path)["jobs"][name])


def _uses(job: dict[str, Any]) -> list[str]:
    return [str(s.get("uses") or s.get("name")) for s in job["steps"]]


@pytest.mark.spec("DOCBW-08-027")
def test_the_deploy_reads_the_register_as_main_holds_it() -> None:
    drafts = _job(DEPLOY, "drafts")
    assert drafts["permissions"] == {"contents": "read"}
    checkout = drafts["steps"][0]
    assert str(checkout["uses"]).startswith("actions/checkout@")
    # The run's own commit: main's tip when the run started.
    assert "ref" not in (checkout.get("with") or {})
    (read,) = [s for s in drafts["steps"] if s.get("id") == "read"]
    assert "drafts-register show" in read["run"]
    assert "--ref" not in read["run"]
    assert drafts["outputs"]["register"] == (
        "${{ steps.read.outputs.register }}"
    )
    build = _job(DEPLOY, "build")
    assert "drafts" in build["needs"]
    (serve,) = [s for s in build["steps"] if s.get("uses") == SERVE_ACTION]
    assert serve["with"] == {
        "register-json": "${{ needs.drafts.outputs.register }}"
    }
    assert "drafts" in _job(DEPLOY, "notify")["needs"]


# --- the step's place (DOCBW-08-028, DOCBW-08-033, DOCBW-08-035) ---------------------


@pytest.mark.spec("DOCBW-08-028", "DOCBW-08-033")
def test_the_deploy_serves_in_the_build_job_before_the_gates_and_upload() -> (
    None
):
    jobs = load_workflow(DEPLOY)["jobs"]
    serving = [n for n, j in jobs.items() if SERVE_ACTION in _uses(j)]
    assert serving == ["build"]
    uses = _uses(jobs["build"])
    upload = next(
        i for i, u in enumerate(uses) if u.startswith("actions/upload-pages")
    )
    assert (
        uses.index(BUILD_SITE_ACTION)
        < uses.index(SERVE_ACTION)
        < uses.index(PUBLICATION_CHECKS)
        < upload
    )
    # The build job holds no token that can write or deploy.
    assert jobs["build"]["permissions"] == {
        "contents": "read",
        "pages": "read",
    }


@pytest.mark.spec("DOCBW-08-035")
def test_the_review_serves_the_checked_out_register_before_its_checks() -> (
    None
):
    (name,) = load_workflow(REVIEW)["jobs"]
    job = _job(REVIEW, name)
    uses = _uses(job)
    assert (
        uses.index(BUILD_SITE_ACTION)
        < uses.index(SERVE_ACTION)
        < uses.index(PUBLICATION_CHECKS)
    )
    (serve,) = [s for s in job["steps"] if s.get("uses") == SERVE_ACTION]
    # No register given: the action reads the checked-out tree's.
    assert "with" not in serve
    paths = triggers(load_workflow(REVIEW))["pull_request"]["paths"]
    assert ".github/actions/serve-frozen-drafts/**" in paths
    assert ".github/scripts/serve_frozen_drafts.py" in paths


@pytest.mark.spec("DOCBW-08-039")
def test_the_promote_archive_job_serves_before_its_checks_and_build() -> None:
    jobs = load_workflow(PROMOTE)["jobs"]
    serving = [n for n, j in jobs.items() if SERVE_ACTION in _uses(j)]
    assert serving == ["frozen-draft"]
    job = jobs["frozen-draft"]
    uses = _uses(job)
    archive = next(
        i
        for i, step in enumerate(job["steps"])
        if "frozen_draft.py build" in str(step.get("run", ""))
    )
    assert (
        uses.index(BUILD_SITE_ACTION)
        < uses.index(SERVE_ACTION)
        < uses.index(PUBLICATION_CHECKS)
        < archive
    )
    (serve,) = [s for s in job["steps"] if s.get("uses") == SERVE_ACTION]
    # No register given: the action reads the promoted commit's, which
    # build-site checked out.
    assert "with" not in serve
    # Serving only reads releases: the job still cannot write (DOCBW-08-019).
    assert job["permissions"] == {"contents": "read"}


def test_the_action_reads_the_checked_out_register_only_when_given_none() -> (
    None
):
    (step,) = local_action_steps(SERVE_ACTION)
    run = str(step["run"])
    assert 'if [ -n "$REGISTER_JSON" ]' in run
    assert "uv run drafts-register show >" in run
    assert "--ref" not in run
    assert ".github/scripts/serve_frozen_drafts.py" in run
    assert step["env"]["REGISTER_JSON"] == "${{ inputs.register-json }}"


# --- no build renders another commit (DOCBW-08-031) -----------------------------------

_OTHER_REF = re.compile(r"\bgit\s+(?:checkout|switch|worktree\s+add)\b")


@pytest.mark.spec("DOCBW-08-031")
def test_no_site_build_renders_a_commit_it_did_not_check_out() -> None:
    workflows = site_building_workflows()
    assert DEPLOY in workflows and REVIEW in workflows
    for path in workflows:
        for name, job in load_workflow(path)["jobs"].items():
            job_steps = job.get("steps") or []
            builds = [
                s for s in job_steps if s.get("uses") == BUILD_SITE_ACTION
            ]
            assert len(builds) <= 1, (path.name, name)
            for step in job_steps:
                ref = str((step.get("with") or {}).get("ref", ""))
                assert not re.match(r"^(?:refs/tags/)?v\d", ref), (
                    path.name,
                    name,
                    ref,
                )
                assert not _OTHER_REF.search(str(step.get("run", ""))), (
                    path.name,
                    name,
                    step.get("name"),
                )


@pytest.mark.spec("DOCBW-08-033")
def test_a_download_that_keeps_failing_fails_naming_the_draft_and_release(
    tmp_path: Path, releases: _FlakyReleases, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive, manifest = _build(tmp_path)
    _publish_pair(releases, archive, manifest)

    def broken(*args: str, retry: bool = True) -> str:
        raise subprocess.CalledProcessError(1, ["gh", *args], stderr="502\n")

    monkeypatch.setattr(releases, "_download", broken)
    site = _built_site(tmp_path)
    lines, faults = _serve.serve(_register(("draft-1", RELEASE)), site, "O/R")
    assert lines == [
        f"- `draft-1`: **failed**, the archive of release `{RELEASE}` could "
        "not be downloaded."
    ]
    assert faults == [
        f"draft-1 (release {RELEASE}): attempt {n}: the download failed: 502"
        for n in (1, 2)
    ]
    assert not (site / "spec").exists()


@pytest.mark.spec("DOCBW-08-033")
def test_a_mismatch_then_a_failed_download_keeps_both_faults(
    tmp_path: Path,
    releases: _FlakyReleases,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The last attempt names how it failed; every attempt's fault is kept,
    and the second download is announced."""
    archive, manifest = _build(tmp_path)
    _publish_pair(releases, archive, manifest)
    releases.tampered = 1
    first = releases._download
    calls: list[int] = []

    def flaky(tag: str, args: tuple[str, ...], retry: bool) -> str:
        calls.append(1)
        if len(calls) > 1:
            raise subprocess.CalledProcessError(1, ["gh"], stderr="502\n")
        return first(tag, args, retry)

    monkeypatch.setattr(releases, "_download", flaky)
    site = _built_site(tmp_path)
    lines, faults = _serve.serve(_register(("draft-1", RELEASE)), site, "O/R")
    assert "could not be downloaded" in lines[0]
    assert any(
        f.startswith(f"draft-1 (release {RELEASE}): attempt 1: ")
        and "download failed" not in f
        for f in faults
    )
    assert faults[-1] == (
        f"draft-1 (release {RELEASE}): attempt 2: the download failed: 502"
    )
    assert "failed its checks; downloading it again" in capsys.readouterr().out


@pytest.mark.spec("DOCBW-08-033")
def test_a_failed_first_download_is_announced_and_retried(
    tmp_path: Path,
    releases: _FlakyReleases,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    archive, manifest = _build(tmp_path)
    _publish_pair(releases, archive, manifest)
    first = releases._download
    calls: list[int] = []

    def flaky(tag: str, args: tuple[str, ...], retry: bool) -> str:
        calls.append(1)
        if len(calls) == 1:
            raise subprocess.CalledProcessError(1, ["gh"], stderr="502\n")
        return first(tag, args, retry)

    monkeypatch.setattr(releases, "_download", flaky)
    site = _built_site(tmp_path)
    assert _serve_into(site, _register(("draft-1", RELEASE))) == [
        f"- `draft-1`: served from release `{RELEASE}`."
    ]
    assert "could not be downloaded; downloading it again" in (
        capsys.readouterr().out
    )


@pytest.mark.spec("DOCBW-08-032", "DOCBW-08-033")
@pytest.mark.parametrize(
    "reply",
    ["not json", json.dumps({"assets": []})],
    ids=["unreadable", "no-isDraft"],
)
def test_an_unexpected_lookup_reply_fails_that_draft_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reply: str,
) -> None:
    """An error the lookup does not expect fails its own draft; the next
    draft is still tried, and the summary keeps every line."""
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    def gh(*args: str, retry: bool = True) -> str:
        if args[2] == RELEASE:
            return reply
        raise subprocess.CalledProcessError(
            1, ["gh"], stderr="release not found\n"
        )

    monkeypatch.setattr(_rel, "gh", gh)
    monkeypatch.setattr(_releases, "gh", gh)
    register = _register_file(
        tmp_path, _released_json(("draft-1", RELEASE), ("draft-2", LATER))
    )
    site = _built_site(tmp_path)
    argv = ["--register", str(register), "--repo", "O/R", "--site", str(site)]
    assert _serve.main(argv) == 1
    text = summary.read_text()
    assert (
        f"- `draft-1`: **failed**, release `{RELEASE}` could not be served."
        in text
    )
    assert f"- `draft-2`: release `{LATER}` is not published yet" in text
    assert "Nothing was served." not in text
    assert (site / "spec/draft-2/index.html").is_file()


def test_a_release_lookup_that_fails_is_retried_then_names_the_draft(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only "release not found" reads as unpublished, and it is never
    retried; any other lookup error is retried, then fails that draft, never
    a placeholder, and the next draft is still tried."""
    looked: list[str] = []

    def gh(*args: str, retry: bool = True) -> str:
        looked.append(args[2])
        stderr = "HTTP 500\n" if args[2] == RELEASE else "release not found\n"
        raise subprocess.CalledProcessError(1, ["gh", *args], stderr=stderr)

    monkeypatch.setattr(_rel, "gh", gh)
    monkeypatch.setattr(_releases, "gh", gh)
    monkeypatch.setattr(_releases.time, "sleep", lambda _seconds: None)
    monkeypatch.setenv("GH_RETRY_ATTEMPTS", "3")
    site = _built_site(tmp_path)
    lines, faults = _serve.serve(
        _register(("draft-1", RELEASE), ("draft-2", LATER)), site, "O/R"
    )
    assert looked == [RELEASE, RELEASE, RELEASE, LATER]
    assert faults == [
        f"draft-1 (release {RELEASE}): the release lookup failed: HTTP 500"
    ]
    assert lines[0].startswith(f"- `draft-1`: **failed**, release `{RELEASE}`")
    assert not (site / "spec/draft-1").exists()
    assert (site / "spec/draft-2/index.html").is_file()
