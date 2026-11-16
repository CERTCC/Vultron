"""The pull-request checkouts fetch the merge base, not every branch's history.

A check that compares against the merge base with the base branch used to check
out with ``fetch-depth: 0``: every branch's whole history and every tag. When
that fetch hung, the job's ``timeout-minutes`` cancelled it before any test ran
and the ``CI gate`` went red (#6535, #6390). Those checkouts now take the
default one-commit checkout and run ``.github/scripts/fetch-merge-base.sh``
(through the ``fetch-merge-base`` action), which deepens only as far as the
merge base.

The script tests run it against a real shallow clone of a scratch ``origin``,
so what they check is what git does, not a stand-in.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from test.ci._workflows import (
    REPO_ROOT,
    WORKFLOWS_DIR,
    load_workflow,
    triggers,
)

SCRIPT = REPO_ROOT / ".github" / "scripts" / "fetch-merge-base.sh"
ACTION = "./.github/actions/fetch-merge-base"

#: Jobs that compare against the merge base, and so must fetch it.
MERGE_BASE_JOBS = {
    ("guard-tests.yml", "guard-tests"),
    ("adr-lifecycle.yml", "adr-lifecycle-check"),
    ("python-app.yml", "test"),
    ("spec-check.yml", "spec-tests"),
}


# --- the workflows --------------------------------------------------------


def _checkouts(job: dict[str, Any]) -> list[tuple[int, dict[str, Any]]]:
    return [
        (i, s)
        for i, s in enumerate(job.get("steps", []))
        if str(s.get("uses", "")).startswith("actions/checkout")
    ]


def _pull_request_workflows() -> list[Path]:
    return sorted(
        p
        for p in WORKFLOWS_DIR.glob("*.yml")
        if "pull_request" in triggers(load_workflow(p))
    )


@pytest.mark.parametrize(
    "path", _pull_request_workflows(), ids=lambda p: p.name
)
def test_no_pull_request_checkout_fetches_the_whole_history(
    path: Path,
) -> None:
    """A literal ``fetch-depth: 0`` fetches every branch on every pull request.

    The one expression allowed is the build job's, which fetches the whole
    history only on a push (asserted below).
    """
    for name, job in load_workflow(path)["jobs"].items():
        for _, step in _checkouts(job):
            depth = (step.get("with") or {}).get("fetch-depth")
            assert depth != 0, (
                f"{path.name}:{name} checks out every branch's history on a "
                f"pull request; fetch the merge base with {ACTION} instead"
            )


@pytest.mark.parametrize("workflow,job_name", sorted(MERGE_BASE_JOBS), ids=str)
def test_a_merge_base_job_fetches_the_merge_base_after_checkout(
    workflow: str, job_name: str
) -> None:
    job = load_workflow(WORKFLOWS_DIR / workflow)["jobs"][job_name]
    (at, checkout), *_ = _checkouts(job)
    assert "fetch-depth" not in (checkout.get("with") or {})
    assert job["steps"][at + 1].get("uses") == ACTION


def test_the_build_job_fetches_history_only_on_a_push() -> None:
    """``uv build`` needs tags for its version only where the artifact is kept."""
    job = load_workflow(WORKFLOWS_DIR / "python-app.yml")["jobs"]["build"]
    (_, checkout), *_ = _checkouts(job)
    settings = checkout["with"]
    assert (
        settings["fetch-depth"]
        == "${{ github.event_name == 'pull_request' && 1 || 0 }}"
    )
    assert (
        settings["fetch-tags"] == "${{ github.event_name != 'pull_request' }}"
    )


def test_the_action_runs_the_script_and_skips_without_a_base() -> None:
    action = load_workflow(
        REPO_ROOT / ".github/actions/fetch-merge-base/action.yml"
    )
    assert action["inputs"]["base-ref"]["default"] == "${{ github.base_ref }}"
    (step,) = action["runs"]["steps"]
    assert step["if"] == "inputs.base-ref != ''"
    assert ".github/scripts/fetch-merge-base.sh" in step["run"]


# --- the script -----------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.org", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(repo: Path, label: str) -> str:
    (repo / "f.txt").write_text(label, encoding="utf-8")
    _git(repo, "add", "f.txt")
    _git(repo, "commit", "-q", "-m", label)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def isolated_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _origin(
    tmp_path: Path, *, fork_at: int, main_after: int
) -> tuple[Path, str]:
    """A bare origin whose ``feature`` leaves ``main`` after *fork_at* commits.

    ``main`` then gains *main_after* more commits, so its tip is not the
    merge base. Returns the bare repository and the fork commit.
    """
    work = tmp_path / "seed"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    fork = ""
    for n in range(fork_at):
        fork = _commit(work, f"main {n}")
    _git(work, "switch", "-q", "-c", "feature")
    for n in range(3):
        _commit(work, f"feature {n}")
    _git(work, "switch", "-q", "main")
    for n in range(main_after):
        _commit(work, f"main after {n}")
    bare = tmp_path / "origin.git"
    _git(tmp_path, "clone", "-q", "--bare", str(work), str(bare))
    return bare, fork


def _shallow_feature(tmp_path: Path, bare: Path) -> Path:
    """A one-commit clone of ``feature``, as ``actions/checkout`` makes."""
    clone = tmp_path / "checkout"
    _git(
        tmp_path,
        "clone",
        "-q",
        "--depth=1",
        "--single-branch",
        "--branch",
        "feature",
        f"file://{bare}",
        str(clone),
    )
    return clone


def _run(clone: Path, **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), "main"],
        cwd=clone,
        capture_output=True,
        text=True,
        env={**os.environ, "GH_RETRY_DELAY": "0", **env},
        check=False,
    )


@pytest.mark.usefixtures("isolated_git")
def test_it_finds_the_merge_base_without_unshallowing(tmp_path: Path) -> None:
    bare, fork = _origin(tmp_path, fork_at=30, main_after=4)
    clone = _shallow_feature(tmp_path, bare)

    result = _run(clone)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == fork
    # The fork commit, not main's tip, and still a shallow checkout.
    assert _git(clone, "rev-parse", "origin/main") != fork
    assert _git(clone, "rev-parse", "--is-shallow-repository") == "true"


@pytest.mark.usefixtures("isolated_git")
def test_it_unshallows_when_the_deepen_steps_fall_short(
    tmp_path: Path,
) -> None:
    bare, fork = _origin(tmp_path, fork_at=3, main_after=30)
    clone = _shallow_feature(tmp_path, bare)

    result = _run(clone, FETCH_DEEPEN_STEPS="1")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == fork
    assert "fetching the full history" in result.stderr


@pytest.mark.usefixtures("isolated_git")
def test_unrelated_histories_fail_loudly(tmp_path: Path) -> None:
    bare, _ = _origin(tmp_path, fork_at=2, main_after=1)
    clone = _shallow_feature(tmp_path, bare)
    # Replace main on origin with a branch that shares no history.
    orphan = tmp_path / "orphan"
    orphan.mkdir()
    _git(orphan, "init", "-q", "-b", "main")
    _commit(orphan, "unrelated")
    _git(orphan, "push", "-q", "--force", str(bare), "main:main")

    result = _run(clone)

    assert result.returncode == 1
    assert result.stdout == ""
    assert "share no history" in result.stderr


def test_it_refuses_a_missing_base() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), ""], capture_output=True, text=True, check=False
    )
    assert result.returncode == 2
    assert "usage" in result.stderr
