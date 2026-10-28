"""CI verification test — confirm every qualifying workflow includes notify-failure.

Implements CISEC-05-004 from specs/ci-security.yaml: every qualifying workflow
(triggered by push to ``main`` or by a ``schedule`` event) SHOULD include the
``.github/actions/notify-failure`` composite action step.

A qualifying workflow is one whose ``on:`` trigger includes:
- ``push`` to the ``main`` branch, OR
- ``push`` to the ``publish`` branch — the publication workflow, which
  DOCBW-06-003 binds to the same notify and close steps, OR
- a ``schedule`` entry.

For each qualifying workflow the test asserts that at least one step across all
jobs uses ``./.github/actions/notify-failure`` in ``notify`` mode (CISEC-05-001)
and at least one step uses it in ``close`` mode (CISEC-05-002).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from test.ci._workflows import triggers

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
NOTIFY_FAILURE_USES = "./.github/actions/notify-failure"
NOTIFY_FAILURE_ACTION = (
    REPO_ROOT / ".github" / "actions" / "notify-failure" / "action.yml"
)
DEMO_WORKFLOW = WORKFLOWS_DIR / "demo-integration.yml"
ENSURE_ISSUE_TYPE = REPO_ROOT / ".github" / "scripts" / "ensure-issue-type.sh"
PUBLICATION_WORKFLOW = WORKFLOWS_DIR / "deploy_site.yml"
# ``main`` for CISEC-05-001; ``publish`` for the publication workflow, whose
# failed run leaves the live site stale with no failing pull request to notice
# it (DOCBW-06-003).
QUALIFYING_PUSH_BRANCHES = frozenset({"main", "publish"})


def _normalize_expr(expr: str) -> str:
    """Collapse whitespace/newlines in a GHA ``if:`` expression for matching."""
    return " ".join(expr.split())


def _load_workflow(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text())  # type: ignore[no-any-return]


def _is_qualifying(wf_data: dict[str, Any]) -> bool:
    """Return True when the workflow triggers on schedule or a qualifying push."""
    on = triggers(wf_data)
    if not isinstance(on, dict):
        return False
    if "schedule" in on:
        return True
    push = on.get("push", {})
    if isinstance(push, dict):
        branches = push.get("branches", [])
        if isinstance(branches, list) and QUALIFYING_PUSH_BRANCHES & set(
            branches
        ):
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
        except Exception:  # noqa: BLE001, S112  # ruff-baseline #3989  # pragma: no cover
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


@pytest.mark.spec("DOCBW-06-003")
def test_publication_workflow_qualifies(
    qualifying_workflows: list[Path],
) -> None:
    """The per-workflow checks below cover the publication workflow.

    It triggers on a push to ``publish``, not ``main``, so without the
    ``publish`` branch in the qualifying set its notify and close steps would
    go untested.
    """
    assert PUBLICATION_WORKFLOW in qualifying_workflows, (
        f"{PUBLICATION_WORKFLOW.name} is not in the qualifying set, so nothing "
        "checks that a failed publish files a ci:main-failure issue "
        "(DOCBW-06-003)."
    )


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


def _notify_action_run_scripts() -> list[str]:
    """Return the ``run:`` script of every step in the composite action."""
    data = yaml.safe_load(NOTIFY_FAILURE_ACTION.read_text())
    steps = data.get("runs", {}).get("steps", [])
    return [str(step["run"]) for step in steps if "run" in step]


def _notify_action_create_script() -> str:
    """Return the one composite-action step script that runs ``gh issue create``."""
    scripts = _notify_action_run_scripts()
    assert scripts, f"{NOTIFY_FAILURE_ACTION} has no run: steps"
    creating = [s for s in scripts if "gh issue create" in s]
    assert len(creating) == 1, (
        "Expected exactly one step in notify-failure/action.yml to run "
        f"`gh issue create`; found {len(creating)} (CISEC-05-007)."
    )
    return creating[0]


def _type_setting_calls(script: str, type_name: str) -> list[str]:
    """Return each call of the shared type helper for *type_name* in *script*."""
    return re.findall(
        rf'^\s*bash "\$ensure_type" .* {type_name}\s*$',
        script,
        flags=re.MULTILINE,
    )


def test_notify_action_sets_bug_issue_type() -> None:
    """CISEC-05-007: a failure issue must carry the Bug type, in both arms.

    ``gh issue create`` cannot set an issue type, and a ``bug`` label applied
    with ``GITHUB_TOKEN`` never fires the label-to-issue-type workflow, so the
    action sets the type itself through the shared helper
    (``ensure-issue-type.sh``). The helper runs on the comment-on-existing arm
    too, so an issue left untyped by a failed assignment is repaired on the
    next notify run.
    """
    script = _notify_action_create_script()
    assert "scripts/ensure-issue-type.sh" in script, (
        "The notify-failure action must set the issue type through "
        f"{ENSURE_ISSUE_TYPE.relative_to(REPO_ROOT)} (CISEC-05-007)."
    )
    assert '--label "bug"' not in script and "--label bug" not in script, (
        "The notify-failure action must not rely on a `bug` label for the "
        "label-to-issue-type workflow: GITHUB_TOKEN events never trigger it "
        "(CISEC-05-007)."
    )
    calls = _type_setting_calls(script, "Bug")
    assert len(calls) == 2, (
        "The Bug type must be set once on the create arm and once on the "
        "comment-on-existing arm, so an issue left untyped by a transient "
        f"mutation failure is repaired on the next run; found {len(calls)} "
        "call(s) (CISEC-05-007)."
    )


def test_recordings_workflow_sets_task_issue_type() -> None:
    """CISEC-05-007: the refresh Task is typed by the same helper, both arms."""
    workflow = (WORKFLOWS_DIR / "demo-recordings.yml").read_text()
    assert "ensure_type=.github/scripts/ensure-issue-type.sh" in workflow
    assert len(_type_setting_calls(workflow, "Task")) == 2


def test_issue_type_helper_resolves_the_type_by_name() -> None:
    """CISEC-05-007: the type is resolved by name and applied by mutation.

    By *name*: a hardcoded node ID would break silently if the type were
    re-created.
    """
    script = ENSURE_ISSUE_TYPE.read_text()
    assert "issueTypes" in script, (
        "The helper must resolve the issue type by name via the `issueTypes` "
        "GraphQL field (CISEC-05-007)."
    )
    assert "updateIssue" in script and "issueTypeId" in script, (
        "The helper must apply the type via the `updateIssue` mutation's "
        "`issueTypeId` (CISEC-05-007)."
    )


def test_issue_type_helper_fails_visibly_without_the_type() -> None:
    """CISEC-05-007: no type of that name in the repository is a loud failure.

    The guard has to come *after* a jq expression that tolerates a null
    ``issueTypes`` connection (an owner with no issue types at all); otherwise
    ``set -e`` kills the step before the ``::error::`` line can name the issue.
    """
    script = ENSURE_ISSUE_TYPE.read_text()
    assert "(.data.repository.issueTypes.nodes // [])" in script, (
        "The type lookup must default a null `issueTypes` connection to an "
        "empty list, or jq aborts the step before the guard runs "
        "(CISEC-05-007)."
    )
    assert 'if [ -z "$type_id" ]' in script, (
        "The helper must guard on an empty type ID (CISEC-05-007)."
    )
    guard = script.index('if [ -z "$type_id" ]')
    guard_body = script[guard : script.index("fi", guard)]
    assert "::error::" in guard_body and "exit 1" in guard_body, (
        "A missing issue type must fail the step with an `::error::` "
        "annotation, not leave the filed issue silently untyped "
        "(CISEC-05-007)."
    )


# A stand-in for the ``gh`` CLI: it logs every call and answers the direct
# list-issues REST call with the JSON page ``$FAKE_ISSUES_PAGE``, filtered
# through the caller's real ``--jq`` expression, while a search-backed
# ``gh issue list`` answers with nothing, as the lagging search index did when
# it let the ADR Status Drift workflow file a second tracker (#5105). With
# ``$FAKE_API_FAIL`` set, the list-issues call fails as an API error would.
_FAKE_GH = r"""#!/usr/bin/env bash
printf '%s\n' "$*" >> "$FAKE_GH_LOG"
case "$1 $2" in
  "api graphql")
    case "$*" in
      *issueTypes*) printf 'Bug\tBUG_TYPE_ID\n' ;;
      *) echo "Set issue type: Bug" ;;
    esac ;;
  "api "*)
    jq_expr="" prev=""
    for arg in "$@"; do
      [ "$prev" = "--jq" ] && jq_expr="$arg"
      prev="$arg"
    done
    for arg in "$@"; do
      case "$arg" in
        repos/*/issues\?*)
          if [ -n "${FAKE_API_FAIL:-}" ]; then
            echo "HTTP 502: Bad Gateway" >&2
            exit 1
          fi
          printf '%s' "$FAKE_ISSUES_PAGE" | jq -r "$jq_expr" ;;
      esac
    done ;;
  "issue view") printf 'ISSUE_NODE_ID\nBug\n' ;;
  "issue create") echo "https://github.com/OWNER/REPO/issues/999" ;;
esac
"""


def _notify_action_lookup_script() -> str:
    """Return the composite-action step that finds, files, and closes issues."""
    scripts = _notify_action_run_scripts()
    lookup = [s for s in scripts if "ISSUE_NUMS" in s]
    assert len(lookup) == 1, (
        "Expected exactly one step in notify-failure/action.yml to look up "
        f"the open failure issue; found {len(lookup)} (CISEC-05-003)."
    )
    return lookup[0]


def _run_notify_action(
    tmp_path: Path,
    mode: str,
    open_issues: list[int],
    *,
    open_pull_requests: tuple[int, ...] = (),
    api_fails: bool = False,
    details: str | None = None,
) -> list[str]:
    """Run the action's lookup step against a fake ``gh``; return its calls.

    ``details`` is written to a file passed as the ``details-file`` input.

    ``open_pull_requests`` are listed on the page as the list-issues endpoint
    lists a labelled pull request, with a ``pull_request`` key. The step's
    exit status is checked: a failing run raises ``CalledProcessError``, and
    its calls stay readable in ``tmp_path / "gh.log"``.
    """
    page = [{"number": n} for n in open_issues] + [
        {"number": n, "pull_request": {"url": f"https://example/pulls/{n}"}}
        for n in open_pull_requests
    ]
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_gh = bin_dir / "gh"
    fake_gh.write_text(_FAKE_GH)
    fake_gh.chmod(0o755)
    log = tmp_path / "gh.log"
    log.touch()
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "FAKE_GH_LOG": str(log),
        "FAKE_ISSUES_PAGE": json.dumps(page),
        "GH_TOKEN": "fake-token",
        "REPO": "OWNER/REPO",
        "MODE": mode,
        "WORKFLOW_LABEL": "ci:workflow-example",
        "WORKFLOW_NAME": "Example",
        "RUN_URL": "https://github.com/OWNER/REPO/actions/runs/1",
        "REF": "refs/heads/main",
        # The runner sets this in a composite action; the step finds the
        # shared ensure-issue-type.sh helper through it.
        "GITHUB_ACTION_PATH": str(NOTIFY_FAILURE_ACTION.parent),
    }
    if api_fails:
        env["FAKE_API_FAIL"] = "1"
    if details is not None:
        details_file = tmp_path / "details.md"
        details_file.write_text(details)
        env["DETAILS_FILE"] = str(details_file)
    subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", _notify_action_lookup_script()],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return log.read_text().splitlines()


def test_notify_action_finds_existing_issue_without_search_index(
    tmp_path: Path,
) -> None:
    """CISEC-05-003: an open tracker is found, not duplicated (#5105).

    ``gh issue list --label`` runs through the search index, which lags: it
    once returned nothing while the ADR Status Drift tracker was open, so the
    action filed a second one. The lookup must use the direct list-issues
    call, which matches both labels against current data.
    """
    calls = _run_notify_action(tmp_path, "notify", [5087])
    assert not any(c.startswith("issue create") for c in calls), (
        "The notify action filed a new issue although one was open; its "
        f"lookup must not depend on the search index (#5105). Calls: {calls}"
    )
    assert any(c.startswith("issue comment 5087") for c in calls), (
        f"The notify action must comment on the open issue. Calls: {calls}"
    )


def test_notify_action_closes_duplicate_trackers(tmp_path: Path) -> None:
    """MS-14-007, CISEC-05-003: notify leaves one tracker, the oldest, open.

    A duplicate filed before this lookup was fixed, or by any future miss,
    is closed as a duplicate of the oldest open tracker on the next run.
    """
    calls = _run_notify_action(tmp_path, "notify", [5087, 5105])
    assert any(c.startswith("issue comment 5087") for c in calls), (
        f"The notify action must comment on the oldest tracker. Calls: {calls}"
    )
    closes = [c for c in calls if c.startswith("issue close")]
    assert len(closes) == 1 and closes[0].startswith("issue close 5105"), (
        f"The notify action must close the newer tracker only. Calls: {calls}"
    )
    assert "#5087" in closes[0], (
        "A closed duplicate must point to the tracker that stays open. "
        f"Calls: {calls}"
    )
    assert not any(c.startswith("issue create") for c in calls), calls


def test_close_mode_closes_every_open_tracker(tmp_path: Path) -> None:
    """CISEC-05-002: recovery closes every open tracker for the workflow."""
    calls = _run_notify_action(tmp_path, "close", [5087, 5105])
    closes = sorted(c.split()[2] for c in calls if c.startswith("issue close"))
    assert closes == ["5087", "5105"], calls


def test_notify_action_files_a_tracker_when_none_is_open(
    tmp_path: Path,
) -> None:
    """CISEC-05-001, CISEC-05-007: with no open tracker, notify files one.

    A labelled pull request on the list-issues page is not a tracker: the
    endpoint lists pull requests too, and the lookup must drop them.
    """
    calls = _run_notify_action(
        tmp_path, "notify", [], open_pull_requests=(4242,)
    )
    creates = [c for c in calls if c.startswith("issue create")]
    assert len(creates) == 1, (
        f"The notify action must file exactly one tracker. Calls: {calls}"
    )
    assert not any(
        c.startswith(("issue comment", "issue close")) for c in calls
    ), (
        "A labelled pull request must not be taken for an open tracker. "
        f"Calls: {calls}"
    )


def test_notify_action_fails_when_the_lookup_fails(tmp_path: Path) -> None:
    """CISEC-05-003: an API error fails the step, never files a duplicate.

    Read through ``mapfile < <(...)``, a failed lookup escapes ``set -e``
    and looks like "no open tracker", so the action would file a second one.
    """
    with pytest.raises(subprocess.CalledProcessError):
        _run_notify_action(tmp_path, "notify", [5087], api_fails=True)
    calls = (tmp_path / "gh.log").read_text().splitlines()
    assert not any(c.startswith("issue create") for c in calls), (
        "A failed lookup must stop the step before it files a tracker. "
        f"Calls: {calls}"
    )


_DETAILS = "- #12 is CLOSED:\n  - `test/x.py:3` `KNOWN_A`"


@pytest.mark.parametrize("open_issues", [[], [5087]])
def test_notify_action_includes_the_details_file(
    tmp_path: Path, open_issues: list[int]
) -> None:
    """ARCH-18-004: a tracker can say what failed, filed or updated.

    The new issue's body and the update comment both carry the caller's
    ``details-file`` text after the run link.
    """
    calls = _run_notify_action(
        tmp_path, "notify", open_issues, details=_DETAILS
    )
    log = "\n".join(calls)
    verb = "issue comment 5087" if open_issues else "issue create"
    assert verb in log, calls
    assert "actions/runs/1)\n\n" + _DETAILS in log, calls


def test_notify_action_adds_nothing_for_an_empty_details_file(
    tmp_path: Path,
) -> None:
    calls = _run_notify_action(tmp_path, "notify", [5087], details="")
    (comment,) = [c for c in calls if c.startswith("issue comment")]
    assert comment.endswith(
        "[run](https://github.com/OWNER/REPO/actions/runs/1)"
    )
