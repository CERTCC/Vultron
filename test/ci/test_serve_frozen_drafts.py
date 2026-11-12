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
_fd = load_script("frozen_draft")
_serve = load_script("serve_frozen_drafts")

DEPLOY = WORKFLOWS_DIR / "deploy_site.yml"
REVIEW = WORKFLOWS_DIR / "docs-build-check.yml"
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
    return list(_serve.serve(register, site, "O/R"))


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
    with pytest.raises(_fd.FrozenDraftError) as caught:
        _serve_into(site, _register(("draft-1", RELEASE)))
    assert _downloads(releases) == _serve.DOWNLOAD_ATTEMPTS == 2
    assert all(
        f.startswith(f"draft-1 (release {RELEASE}): ")
        for f in caught.value.faults
    )
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
    assert _serve_into(site, None) == []
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


def test_the_command_refuses_a_register_that_is_not_one(
    tmp_path: Path, releases: _FlakyReleases
) -> None:
    register = tmp_path / "register.json"
    register.write_text("[1, 2]")
    argv = ["--register", str(register), "--repo", "O/R"]
    assert _serve.main([*argv, "--site", str(_built_site(tmp_path))]) == 1


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
    with pytest.raises(_fd.FrozenDraftError) as caught:
        _serve_into(site, _register(("draft-1", RELEASE)))
    (fault,) = caught.value.faults
    assert fault.startswith(
        f"draft-1 (release {RELEASE}): the download failed"
    )
    assert not (site / "spec").exists()


def test_a_release_lookup_that_fails_fails_the_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only "release not found" reads as unpublished; any other error is a
    failure, never a placeholder."""

    def gh(*args: str, retry: bool = True) -> str:
        raise subprocess.CalledProcessError(
            1, ["gh", *args], stderr="HTTP 500\n"
        )

    monkeypatch.setattr(_rel, "gh", gh)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    register = tmp_path / "register.json"
    register.write_text(
        json.dumps(
            {
                "current": None,
                "released": [
                    {
                        "version": "draft-1",
                        "date": "2026-11-06",
                        "release": RELEASE,
                    }
                ],
            }
        )
    )
    site = _built_site(tmp_path)
    argv = ["--register", str(register), "--repo", "O/R", "--site", str(site)]
    assert _serve.main(argv) == 1
    assert not (site / "spec").exists()
