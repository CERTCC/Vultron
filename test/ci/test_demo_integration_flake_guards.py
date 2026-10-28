#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""Guards against the Demo Integration workflow's known CI flakes.

- A re-run harness judged the first attempt's case log (#4577,
  DEMOCI-04-003): each attempt now uploads its own artifact, and the harness
  picks the one from the latest demo attempt at or before its own.
- A hang after a passing demo looked like a demo timeout (#4573,
  DEMOCI-02-009): the demo step now has its own, shorter bound.
- An anonymous Docker Hub pull hit a 429 (#4450, DEMOCI-02-005): the image
  build pulls Docker Hub images through ``mirror.gcr.io``, with no secret.
"""

from __future__ import annotations

import os
import subprocess
import tomllib
from pathlib import Path
from typing import Any

import pytest

from test.ci._workflows import REPO_ROOT, load_workflow, local_action_steps

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "demo-integration.yml"
BUILD_ACTION = "./.github/actions/build-demo-images"
MIRROR = "mirror.gcr.io"


def _job(name: str) -> dict[str, Any]:
    job = load_workflow(WORKFLOW)["jobs"][name]
    assert isinstance(job, dict)
    return job


def _steps(job: str) -> list[dict[str, Any]]:
    return list(_job(job)["steps"])


def _step(job: str, *, key: str, needle: str) -> dict[str, Any]:
    matches = [s for s in _steps(job) if needle in str(s.get(key, ""))]
    assert len(matches) == 1, (
        f"Expected one {job} step whose {key} contains {needle!r}, found "
        f"{len(matches)}; update this test if the step was renamed."
    )
    return matches[0]


def _index(job: str, *, key: str, needle: str) -> int:
    return _steps(job).index(_step(job, key=key, needle=needle))


# ── #4577: a re-run harness judges its own attempt's case log ──────────────


def _case_log_upload() -> dict[str, Any]:
    return _step("demo", key="name", needle="Upload case log")


def test_each_demo_attempt_uploads_its_own_case_log_artifact() -> None:
    upload = _case_log_upload()
    assert upload["with"]["name"] == (
        "${{ matrix.demo }}-case-logs-attempt-${{ github.run_attempt }}"
    ), (
        "A re-run uploads a second artifact; without the attempt in its name "
        "the harness cannot tell it from the first attempt's (#4577)."
    )


def test_case_log_upload_fails_when_it_finds_nothing() -> None:
    assert _case_log_upload()["with"].get("if-no-files-found") == "error"


def test_sentinel_is_written_before_the_images_are_built() -> None:
    """A failed build (a 429, #4450) still uploads this attempt's artifact.

    Otherwise a re-run whose build failed would leave the harness only the
    earlier attempt's log to judge.
    """
    sentinel = _index("demo", key="name", needle="sentinel manifest")
    build = _index("demo", key="uses", needle=BUILD_ACTION)
    assert sentinel < build


def test_harness_downloads_the_artifact_it_resolved() -> None:
    download = _step(
        "invariant-harness", key="uses", needle="download-artifact"
    )
    assert download["with"]["name"] == (
        "${{ steps.case-log-artifact.outputs.name }}"
    )
    resolve = _index("invariant-harness", key="id", needle="case-log-artifact")
    assert resolve < _steps("invariant-harness").index(download)


def _run_resolver(
    tmp_path: Path, artifacts: list[str], *, demo: str, attempt: int
) -> tuple[subprocess.CompletedProcess[str], str]:
    """Run the harness's resolve step against a fake ``gh``.

    The fake answers the run's list-artifacts call with *artifacts*, one name
    per line, as the step's ``--jq`` would print them.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_gh = bin_dir / "gh"
    fake_gh.write_text('#!/usr/bin/env bash\nprintf "%s" "$FAKE_NAMES"\n')
    fake_gh.chmod(0o755)
    output = tmp_path / "output"
    output.touch()
    step = _step("invariant-harness", key="id", needle="case-log-artifact")
    result = subprocess.run(
        ["bash", "-e", "-c", str(step["run"])],
        check=False,
        cwd=REPO_ROOT,
        env={
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "FAKE_NAMES": "".join(f"{a}\n" for a in artifacts),
            "GH_RETRY_DELAY": "0",
            "GH_TOKEN": "fake-token",
            "GITHUB_OUTPUT": str(output),
            "REPO": "OWNER/REPO",
            "RUN_ID": "1",
            "RUN_ATTEMPT": str(attempt),
            "DEMO": demo,
        },
        capture_output=True,
        text=True,
    )
    return result, output.read_text()


@pytest.mark.parametrize(
    ("artifacts", "attempt", "expected"),
    [
        pytest.param(
            ["rcv-case-logs-attempt-1"],
            1,
            "rcv-case-logs-attempt-1",
            id="first",
        ),
        pytest.param(
            ["rcv-case-logs-attempt-1", "rcv-case-logs-attempt-2"],
            2,
            "rcv-case-logs-attempt-2",
            id="demo-re-run",
        ),
        pytest.param(
            ["rcv-case-logs-attempt-1", "rcv-embargo-case-logs-attempt-2"],
            2,
            "rcv-case-logs-attempt-1",
            id="only-the-harness-re-ran",
        ),
        pytest.param(
            ["rcv-case-logs-attempt-1", "rcv-case-logs-attempt-3"],
            2,
            "rcv-case-logs-attempt-1",
            id="never-a-later-attempt",
        ),
    ],
)
def test_harness_picks_the_latest_demo_attempt_at_or_before_its_own(
    tmp_path: Path, artifacts: list[str], attempt: int, expected: str
) -> None:
    result, output = _run_resolver(
        tmp_path, artifacts, demo="rcv", attempt=attempt
    )
    assert result.returncode == 0, result.stderr
    assert output == f"name={expected}\n"


def test_harness_fails_when_no_attempt_uploaded_a_case_log(
    tmp_path: Path,
) -> None:
    result, output = _run_resolver(
        tmp_path, ["rcv-embargo-case-logs-attempt-1"], demo="rcv", attempt=1
    )
    assert result.returncode != 0
    assert output == ""


# ── #4573: a post-demo hang is told apart from a demo timeout ──────────────


def test_demo_step_has_a_bound_shorter_than_the_job_cap() -> None:
    job_cap = _job("demo")["timeout-minutes"]
    assert job_cap == 15, "DEMOCI-02-009 fixes the job cap at 15 minutes."
    demo_step = _step("demo", key="name", needle="Run ${{ matrix.demo }}")
    step_cap = demo_step.get("timeout-minutes")
    assert isinstance(step_cap, int), (
        "The demo step needs its own timeout-minutes, so a hung demo fails in "
        "that step and a job that reaches the 15-minute cap with the demo "
        "step green is a post-step hang, not a demo failure (#4573)."
    )
    # Room for checkout and the image build before it, and for log
    # collection and teardown after it.
    assert step_cap <= job_cap - 5


# ── #4450: Docker Hub pulls go through a mirror, with no credential ────────


def _buildx_setup() -> dict[str, Any]:
    steps = [
        s
        for s in local_action_steps(BUILD_ACTION)
        if "docker/setup-buildx-action" in str(s.get("uses", ""))
    ]
    assert len(steps) == 1
    return steps[0]


def test_buildkit_pulls_docker_hub_images_through_the_mirror() -> None:
    config = tomllib.loads(_buildx_setup()["with"]["buildkitd-config-inline"])
    assert config["registry"]["docker.io"]["mirrors"] == [MIRROR], (
        "The base image and the Dockerfile syntax frontend come from Docker "
        "Hub; anonymous pulls there hit 429 Too Many Requests (#4450)."
    )


def test_buildkit_image_itself_comes_from_the_mirror() -> None:
    driver_opts = str(_buildx_setup()["with"]["driver-opts"])
    assert f"image={MIRROR}/moby/buildkit:" in driver_opts


def test_image_build_uses_no_registry_login() -> None:
    """The fix must not need a secret (fork PRs have none)."""
    for step in local_action_steps(BUILD_ACTION):
        assert "login" not in str(step.get("uses", ""))
        assert "docker login" not in str(step.get("run", ""))
