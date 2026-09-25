"""CI verification test — confirm every qualifying workflow includes notify-failure.

Implements CISEC-05-004 from specs/ci-security.yaml: every qualifying workflow
(triggered by push to ``main`` or by a ``schedule`` event) SHOULD include the
``.github/actions/notify-failure`` composite action step.

A qualifying workflow is one whose ``on:`` trigger includes:
- ``push`` to the ``main`` branch, OR
- a ``schedule`` entry.

For each qualifying workflow the test asserts that at least one step across all
jobs uses ``./.github/actions/notify-failure`` in ``notify`` mode (CISEC-05-001)
and at least one step uses it in ``close`` mode (CISEC-05-002).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from test.ci._workflows import triggers

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
NOTIFY_FAILURE_USES = "./.github/actions/notify-failure"
DEMO_WORKFLOW = WORKFLOWS_DIR / "demo-integration.yml"


def _normalize_expr(expr: str) -> str:
    """Collapse whitespace/newlines in a GHA ``if:`` expression for matching."""
    return " ".join(expr.split())


def _load_workflow(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text())  # type: ignore[no-any-return]


def _is_qualifying(wf_data: dict[str, Any]) -> bool:
    """Return True when the workflow triggers on push-to-main or schedule."""
    on = triggers(wf_data)
    if not isinstance(on, dict):
        return False
    if "schedule" in on:
        return True
    push = on.get("push", {})
    if isinstance(push, dict):
        branches = push.get("branches", [])
        if isinstance(branches, list) and "main" in branches:
            return True
    return False


def _notify_failure_steps(
    wf_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return all steps that reference the notify-failure composite action."""
    steps = []
    for job in wf_data.get("jobs", {}).values():
        for step in job.get("steps", []):
            if isinstance(step, dict) and step.get("uses", "").startswith(
                NOTIFY_FAILURE_USES
            ):
                steps.append(step)
    return steps


def _qualifying_workflow_files() -> list[Path]:
    files = []
    for wf in sorted(WORKFLOWS_DIR.glob("*.yml")):
        try:
            data = _load_workflow(wf)
        except Exception:  # pragma: no cover
            continue
        if _is_qualifying(data):
            files.append(wf)
    return files


# ---------------------------------------------------------------------------
# Parametrize: one test case per qualifying workflow
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def qualifying_workflows() -> list[Path]:
    found = _qualifying_workflow_files()
    assert found, f"No qualifying workflows found under {WORKFLOWS_DIR}"
    return found


def test_qualifying_workflows_found(qualifying_workflows: list[Path]) -> None:
    """At least one qualifying workflow must exist."""
    assert len(qualifying_workflows) >= 1


@pytest.mark.parametrize(
    "wf", _qualifying_workflow_files(), ids=lambda p: p.name
)
def test_qualifying_workflow_has_notify_step(wf: Path) -> None:
    """CISEC-05-004/CISEC-05-001: qualifying workflow must have a notify step."""
    data = _load_workflow(wf)
    steps = _notify_failure_steps(data)
    notify_steps = [
        s for s in steps if s.get("with", {}).get("mode") == "notify"
    ]
    assert notify_steps, (
        f"{wf.name} is a qualifying workflow (push-to-main or schedule) "
        f"but has no ./.github/actions/notify-failure step with mode: notify. "
        f"Add the step per CISEC-05-001."
    )


@pytest.mark.parametrize(
    "wf", _qualifying_workflow_files(), ids=lambda p: p.name
)
def test_qualifying_workflow_has_close_step(wf: Path) -> None:
    """CISEC-05-004/CISEC-05-002: qualifying workflow must have a close step."""
    data = _load_workflow(wf)
    steps = _notify_failure_steps(data)
    close_steps = [
        s for s in steps if s.get("with", {}).get("mode") == "close"
    ]
    assert close_steps, (
        f"{wf.name} is a qualifying workflow (push-to-main or schedule) "
        f"but has no ./.github/actions/notify-failure step with mode: close. "
        f"Add the step per CISEC-05-002."
    )


@pytest.mark.parametrize(
    "wf", _qualifying_workflow_files(), ids=lambda p: p.name
)
def test_qualifying_workflow_notify_step_has_workflow_label(wf: Path) -> None:
    """CISEC-05-004/CISEC-05-003: each notify step must carry a workflow-label."""
    data = _load_workflow(wf)
    steps = _notify_failure_steps(data)
    for step in steps:
        label = step.get("with", {}).get("workflow-label", "")
        assert label, (
            f"{wf.name}: a ./.github/actions/notify-failure step is missing "
            f"the workflow-label input (CISEC-05-003)."
        )


@pytest.mark.parametrize(
    "wf", _qualifying_workflow_files(), ids=lambda p: p.name
)
def test_notify_step_does_not_file_on_cancellation(wf: Path) -> None:
    """CISEC-05-006 (#3249): the failure-notify step must not file a
    ci:main-failure issue on a cancelled (concurrency-superseded) run.

    A push-to-main run cancelled by the concurrency group is not an actual
    failure — a newer run is authoritative. The notify step's ``if:`` guard
    must therefore require a genuine failure AND exclude cancellation, and must
    not use the ``|| contains(needs.*.result, 'cancelled')`` pattern that files
    on cancellation directly.
    """
    data = _load_workflow(wf)
    notify_steps = [
        s
        for s in _notify_failure_steps(data)
        if s.get("with", {}).get("mode") == "notify"
    ]
    for step in notify_steps:
        guard = _normalize_expr(str(step.get("if", "")))
        # Never file on cancellation directly.
        assert "|| contains(needs.*.result, 'cancelled')" not in guard, (
            f"{wf.name}: the notify (file) step must NOT file on cancellation "
            f"via `|| contains(needs.*.result, 'cancelled')` (CISEC-05-006, "
            f"#3249). Current guard: {guard!r}"
        )
        # The `needs.*.result` aggregate idiom can observe a `failure` laundered
        # from a cancelled run (a cancelled upstream job leaving a downstream job
        # to hard-fail on a missing artifact, #3249), so it MUST pair the failure
        # check with an explicit cancellation exclusion. The `failure()` status
        # function excludes cancellation inherently and needs no extra guard.
        if "contains(needs.*.result, 'failure')" in guard:
            assert "!contains(needs.*.result, 'cancelled')" in guard, (
                f"{wf.name}: a notify (file) step that keys on "
                f"`contains(needs.*.result, 'failure')` must also exclude "
                f"cancelled runs via `!contains(needs.*.result, 'cancelled')` "
                f"so a superseded run does not file a spurious ci:main-failure "
                f"issue (CISEC-05-006, #3249). Current guard: {guard!r}"
            )


def test_invariant_harness_skipped_when_demo_cancelled() -> None:
    """Regression (#3249): a concurrency-cancelled demo job must not cascade
    into a spurious ``ci:main-failure`` issue.

    When the ``demo`` job is cancelled by the concurrency group (a newer push
    supersedes the run), no case-log artifact is uploaded, so the
    ``invariant-harness`` job's ``download-artifact`` step hard-errors —
    turning a *cancellation* into a job *failure* that the ``notify`` job then
    reports as a real CI failure. The harness ``if:`` must therefore exclude
    cancelled demo runs so it is *skipped* (not failed) in that case, leaving
    the ``notify`` job to correctly defer to the superseding run.

    See DEMOCI-04-007 and ``notes/ci-workflow-authoring.md``.
    """
    data = _load_workflow(DEMO_WORKFLOW)
    job = data.get("jobs", {}).get("invariant-harness")
    assert job is not None, (
        "demo-integration.yml has no invariant-harness job — the job key may "
        "have been renamed; update this regression test (#3249)."
    )
    guard = _normalize_expr(str(job.get("if", "")))
    assert "needs.demo.result != 'cancelled'" in guard, (
        "The invariant-harness `if:` must exclude cancelled demo runs "
        "(needs.demo.result != 'cancelled'), so a concurrency-cancelled "
        "push-to-main run does not cascade into a spurious ci:main-failure "
        f"issue (DEMOCI-04-007, #3249). Current guard: {guard!r}"
    )
