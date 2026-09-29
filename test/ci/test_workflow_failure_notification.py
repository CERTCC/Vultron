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


AGGREGATE_FAILURE = "contains(needs.*.result, 'failure')"
AGGREGATE_CANCELLED_EXCLUSION = "!contains(needs.*.result, 'cancelled')"
AGGREGATE_CANCELLED_INCLUSION = "|| contains(needs.*.result, 'cancelled')"


def _step_guards(wf: Path, mode: str) -> list[str]:
    """Return the normalized ``if:`` guard of every notify-failure step in
    ``wf`` running in ``mode`` (``"notify"`` or ``"close"``)."""
    data = _load_workflow(wf)
    return [
        _normalize_expr(str(step.get("if", "")))
        for step in _notify_failure_steps(data)
        if step.get("with", {}).get("mode") == mode
    ]


@pytest.mark.parametrize(
    "wf", _qualifying_workflow_files(), ids=lambda p: p.name
)
def test_notify_step_does_not_file_on_cancellation(wf: Path) -> None:
    """CISEC-05-006 (#3249): the failure-notify step must not file a
    ci:main-failure issue on a cancelled (concurrency-superseded) run.

    A push-to-main run cancelled by the concurrency group is not an actual
    failure — a newer run is authoritative. The notify step's ``if:`` guard
    must therefore require a genuine failure and must not use the
    ``|| contains(needs.*.result, 'cancelled')`` pattern that files on
    cancellation directly.
    """
    for guard in _step_guards(wf, "notify"):
        assert AGGREGATE_CANCELLED_INCLUSION not in guard, (
            f"{wf.name}: the notify (file) step must NOT file on cancellation "
            f"via `{AGGREGATE_CANCELLED_INCLUSION}` (CISEC-05-006, #3249). "
            f"Current guard: {guard!r}"
        )


@pytest.mark.parametrize(
    "wf", _qualifying_workflow_files(), ids=lambda p: p.name
)
def test_notify_step_files_on_failure_mixed_with_cancellation(
    wf: Path,
) -> None:
    """CISEC-05-006 (#3293, #3294): a genuine failure must be filed even when
    a sibling job in the same run was cancelled.

    When a job fails and a newer push then cancels the jobs still running,
    ``needs.*.result`` holds both ``failure`` and ``cancelled``. A guard of
    the form ``contains(needs.*.result, 'failure') &&
    !contains(needs.*.result, 'cancelled')`` is false for that run, so the
    observed failure is never filed — for python-app.yml when lint jobs are
    cancelled alongside failing tests (#3293), and for demo-integration.yml
    when the invariant harness is cancelled after a demo leg failed (#3294).

    The cancellation exclusion was defense in depth against a *laundered*
    failure (a cancelled upstream job leaving a downstream job to hard-fail
    on a missing artifact, #3249). That path is closed at its source by the
    harness skip guard (DEMOCI-04-007, checked by
    ``test_invariant_harness_skipped_when_demo_cancelled``), so every
    ``failure`` in the aggregate is genuine and the notify step must not
    require the absence of ``cancelled``.

    The property holds for every notify guard, not only aggregate-keyed
    ones: a ``failure()`` guard passes trivially, and a guard keyed on a
    single job's result (``needs.test.result == 'failure'``) would be
    suppressed by the exclusion just the same, so no guard is exempt.
    """
    for guard in _step_guards(wf, "notify"):
        assert AGGREGATE_CANCELLED_EXCLUSION not in guard, (
            f"{wf.name}: a notify (file) step must not require "
            f"`{AGGREGATE_CANCELLED_EXCLUSION}` — that "
            f"suppresses a genuine failure whenever a sibling job in the same "
            f"run was cancelled (CISEC-05-006, #3293, #3294). Skip artifact "
            f"consumers on a cancelled producer instead (DEMOCI-04-007). "
            f"Current guard: {guard!r}"
        )


@pytest.mark.parametrize(
    "wf", _qualifying_workflow_files(), ids=lambda p: p.name
)
def test_close_step_does_not_close_on_cancellation(wf: Path) -> None:
    """CISEC-05-002 (#3293, #3294): the close step must not declare recovery
    on a cancelled (concurrency-superseded) run.

    The notify step dropped its cancellation exclusion because a genuine
    ``failure`` sitting beside a ``cancelled`` result is still genuine
    (``test_notify_step_files_on_failure_mixed_with_cancellation``). The
    close step is the mirror image: an aggregate holding no ``failure`` but a
    ``cancelled`` result proves nothing about the commit — the cancelled job
    might have failed had it run to completion — so an aggregate-keyed close
    guard MUST keep ``!contains(needs.*.result, 'cancelled')``. A guard keyed
    on the ``success()`` status function is already safe: ``success()`` is
    false on cancellation, so it never contains the aggregate at all.
    """
    for guard in _step_guards(wf, "close"):
        if AGGREGATE_FAILURE not in guard:
            continue  # keyed on success(), which is false on cancellation
        assert AGGREGATE_CANCELLED_EXCLUSION in guard, (
            f"{wf.name}: a close step keyed on the `needs.*.result` aggregate "
            f"must also require `{AGGREGATE_CANCELLED_EXCLUSION}` — a "
            f"superseded run must not retire the ci:main-failure issue on a "
            f"commit it never finished checking (CISEC-05-002, #3293, "
            f"#3294). Current guard: {guard!r}"
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

    See DEMOCI-04-007 and ``notes/demo-ci-invariants.md`` § Cancellation
    Safety.
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
