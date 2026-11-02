"""``prepush-ci-mirror`` plans and runs CI's pull-request checks locally (PAD-18-021).

Planning is checked against stand-in workflow steps, so each rule (trigger
filter, narrowed paths, PR number, missing tool, ``--skip``) is pinned on its
own; running is checked with real subprocesses, and the command line on a
throwaway repository.
"""

from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path

import pytest

from test.support.git_repo import git, init_git_repo
from vultron.metadata.planning import ci_mirror
from vultron.metadata.planning.ci_mirror._registry import (
    MIRROR_CHECKS,
    CheckContext,
    MirrorCheck,
    markdownlint_command,
)
from vultron.metadata.planning.ci_mirror._run import (
    STEP_SHELL,
    CheckStatus,
    PlannedCheck,
    plan,
    run_checks,
)
from vultron.metadata.planning.ci_mirror._workflows import (
    PullRequestTrigger,
    WorkflowStep,
    matches_filter,
)


@pytest.fixture(autouse=True)
def _private_tempdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The mirror's logs go under the temp directory; keep them in tmp_path.
    temp = tmp_path / "temp"
    temp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp))


@pytest.mark.parametrize(
    ("path", "patterns", "expected"),
    [
        ("README.md", ("**/*.md",), True),
        ("docs/a/b.md", ("**/*.md",), True),
        ("docs/a.py", ("**/*.md",), False),
        ("vultron/x.py", ("vultron/*",), True),
        ("vultron/a/x.py", ("vultron/*",), False),
        ("vultron/a/x.py", ("vultron/**",), True),
        (
            "vultron/metadata/x.py",
            ("vultron/**", "!vultron/metadata/**"),
            False,
        ),
        ("vultron/core/x.py", ("vultron/**", "!vultron/metadata/**"), True),
        ("a/b.py", ("a/**", "!a/**", "a/b.py"), True),
        ("mkdocs.yml", ("mkdocs.yml",), True),
        ("mkdocsXyml", ("mkdocs.yml",), False),
        ("x.md", (), False),
    ],
)
def test_path_filters_follow_github_rules(path, patterns, expected):
    assert matches_filter(path, patterns) is expected


def test_a_trigger_runs_only_for_its_branches_and_paths():
    trigger = PullRequestTrigger(("main",), ("src/**",), None)

    assert trigger.runs_for("main", ["src/a.py"])
    assert not trigger.runs_for("main", ["docs/a.md"])
    assert not trigger.runs_for("release", ["src/a.py"])


def test_paths_ignore_runs_when_any_path_is_not_ignored():
    trigger = PullRequestTrigger(None, None, ("docs/**",))

    assert trigger.runs_for("main", ["docs/a.md", "src/a.py"])
    assert not trigger.runs_for("main", ["docs/a.md"])


_KEY = "ci.yml::job::Lint"
_STEP = WorkflowStep(
    key=_KEY,
    workflow="ci.yml",
    job="job",
    run="make lint",
    uses=None,
    env={"KEEP": "1", "TOKEN": "${{ secrets.GITHUB_TOKEN }}"},
    working_directory="sub",
)
_TRIGGERS = {"ci.yml": PullRequestTrigger(None, ("src/**",), None)}


def _plan(
    check: MirrorCheck,
    changed: tuple[str, ...] = ("src/a.py",),
    *,
    pr: str = "",
    skip: tuple[str, ...] = (),
    tool_found: bool = True,
    root: Path = Path("."),
) -> PlannedCheck:
    context = CheckContext({"base": "main", "pr": pr}, changed, root)
    [planned] = plan(
        [check],
        {_KEY: _STEP},
        _TRIGGERS,
        context,
        base="main",
        skip=skip,
        which=lambda tool: "/bin/" + tool if tool_found else None,
    )
    return planned


@pytest.mark.spec("PAD-18-021")
def test_a_verbatim_check_runs_its_steps_own_script():
    planned = _plan(MirrorCheck("lint", _KEY))

    assert planned.status is None
    assert planned.argv == (*STEP_SHELL, "make lint")
    assert planned.cwd == "sub"


def test_a_github_expression_in_step_env_is_dropped():
    planned = _plan(MirrorCheck("lint", _KEY, env={"PR": "{pr}"}), pr="7")

    assert planned.env == {"KEEP": "1", "PR": "7"}


@pytest.mark.spec("PAD-18-021")
def test_a_check_whose_workflow_would_not_run_is_not_triggered():
    planned = _plan(MirrorCheck("lint", _KEY), changed=("docs/a.md",))

    assert planned.status is CheckStatus.NOT_TRIGGERED
    assert planned.argv is None


def test_a_narrowed_check_needs_a_changed_path_in_its_set():
    check = MirrorCheck("lint", _KEY, paths=("src/b.py",), narrowed="slow")

    planned = _plan(check)

    assert planned.status is CheckStatus.NOT_TRIGGERED
    assert "narrowed" in planned.reason
    assert _plan(check, changed=("src/b.py",)).status is None


def test_a_check_that_needs_a_pr_waits_for_one():
    check = MirrorCheck("owners", _KEY, needs_pr=True)

    assert _plan(check).status is CheckStatus.NOT_APPLICABLE
    assert _plan(check, pr="12").status is None


@pytest.mark.spec("PAD-18-021")
def test_a_missing_tool_blocks():
    planned = _plan(
        MirrorCheck("lint", _KEY, tool="actionlint"), tool_found=False
    )

    assert planned.status is CheckStatus.UNAVAILABLE
    assert planned.status.blocks


def test_a_check_naming_a_step_that_no_longer_runs_blocks():
    planned = _plan(MirrorCheck("gone", "ci.yml::job::Removed"))

    assert planned.status is CheckStatus.FAILED
    assert "registry is stale" in planned.reason


def test_a_skipped_check_is_reported_and_does_not_block():
    planned = _plan(MirrorCheck("lint", _KEY), skip=("lint",))

    assert planned.status is CheckStatus.SKIPPED
    assert not planned.status.blocks


def test_a_command_is_filled_from_the_placeholders():
    check = MirrorCheck(
        "x", _KEY, command=("tool", "--base", "{base}"), note="n"
    )

    assert _plan(check).argv == ("tool", "--base", "main")


def test_a_builder_with_nothing_to_read_is_not_triggered():
    check = MirrorCheck("x", _KEY, command=lambda _context: None, note="n")

    assert _plan(check).status is CheckStatus.NOT_TRIGGERED


_GUARD = next(c for c in MIRROR_CHECKS if c.id == "guard-tests")


@pytest.mark.spec("PAD-18-023")
@pytest.mark.parametrize("changed", [(), ("docs/page.md",), ("notes/x.md",)])
def test_the_guard_tests_run_on_every_diff(changed):
    context = CheckContext({"base": "main", "pr": ""}, changed, Path("."))

    [planned] = plan([_GUARD], {}, {}, context, base="main")

    assert planned.status is None
    assert planned.argv is not None
    assert "-m" in planned.argv and "" in planned.argv


def test_markdownlint_reads_the_branchs_present_markdown(tmp_path: Path):
    (tmp_path / "kept.md").write_text("# x\n")
    context = CheckContext({}, ("kept.md", "deleted.md", "code.py"), tmp_path)

    argv = markdownlint_command(context)

    assert argv is not None
    assert argv[-1] == "kept.md"
    assert "deleted.md" not in argv


def test_markdownlint_reads_the_tree_when_a_config_changes(tmp_path: Path):
    context = CheckContext({}, ("docs/.markdownlint-cli2.yaml",), tmp_path)

    argv = markdownlint_command(context)

    assert argv is not None and argv[-1] == "**/*.md"


def test_markdownlint_has_nothing_to_read_without_markdown(tmp_path: Path):
    assert markdownlint_command(CheckContext({}, ("a.py",), tmp_path)) is None


def _runnable(check_id: str, script: str, group: str | None = None):
    return PlannedCheck(
        MirrorCheck(check_id, None, command=("x",), note="n", group=group),
        (*STEP_SHELL, script),
        None,
        {},
        None,
    )


@pytest.mark.spec("PAD-18-021")
def test_execute_reports_pass_and_failure(tmp_path: Path):
    results = run_checks(
        [_runnable("ok", "true"), _runnable("bad", "exit 3")], tmp_path, jobs=2
    )

    assert [(r.id, r.status, r.returncode) for r in results] == [
        ("ok", CheckStatus.PASSED, 0),
        ("bad", CheckStatus.FAILED, 3),
    ]


def test_a_failing_stage_of_a_pipe_fails_the_step(tmp_path: Path):
    # GitHub runs `run:` with -eo pipefail; a mirror without it would pass this.
    [result] = run_checks(
        [_runnable("pipe", "false | true")], tmp_path, jobs=1
    )

    assert result.status is CheckStatus.FAILED


def test_a_group_stops_at_its_first_failure(tmp_path: Path):
    marker = tmp_path / "ran"
    results = run_checks(
        [
            _runnable("build", "exit 1", group="site"),
            _runnable("read", f"touch {marker}", group="site"),
        ],
        tmp_path,
        jobs=2,
    )

    assert [r.status for r in results] == [
        CheckStatus.FAILED,
        CheckStatus.FAILED,
    ]
    assert "build failed first" in results[1].reason
    assert not marker.exists()


def test_a_check_that_runs_alone_waits_for_the_others(tmp_path: Path):
    marker = tmp_path / "shared-done"
    alone = PlannedCheck(
        MirrorCheck("solo", None, command=("x",), note="n", alone=True),
        (*STEP_SHELL, f"test -e {marker}"),
        None,
        {},
        None,
    )
    shared = _runnable("shared", f"sleep 1 && touch {marker}")

    results = run_checks([alone, shared], tmp_path, jobs=4)

    assert [r.status for r in results] == [
        CheckStatus.PASSED,
        CheckStatus.PASSED,
    ]


def test_a_check_over_its_timeout_fails(tmp_path: Path):
    [result] = run_checks(
        [_runnable("slow", "sleep 5")], tmp_path, jobs=1, timeout=1
    )

    assert result.status is CheckStatus.FAILED
    assert "timed out" in result.reason


def test_unplanned_checks_keep_their_planned_verdict(tmp_path: Path):
    skipped = PlannedCheck(
        MirrorCheck("s", None), None, None, {}, CheckStatus.SKIPPED, "asked"
    )

    [result] = run_checks([skipped], tmp_path, jobs=1)

    assert (result.status, result.reason) == (CheckStatus.SKIPPED, "asked")


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "a.txt").write_text("a\n")
    init_git_repo(tmp_path, monkeypatch)
    git(tmp_path, "update-ref", "refs/remotes/origin/main", "HEAD")
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.spec("PAD-18-021")
def test_a_dirty_tree_is_a_setup_error(repo: Path, capsys):
    (repo / "a.txt").write_text("changed\n")

    assert ci_mirror.main(["--no-fetch"]) == 2
    assert "mirror exit: 2" in capsys.readouterr().out


def test_an_unknown_base_is_a_setup_error(repo: Path):
    assert ci_mirror.main(["--no-fetch", "--base", "nope"]) == 2


def test_an_unknown_skip_id_is_a_setup_error(repo: Path):
    assert ci_mirror.main(["--no-fetch", "--skip", "nope"]) == 2


def test_list_plans_without_running(repo: Path, capsys):
    git(repo, "checkout", "-q", "-b", "feature")
    (repo / "b.md").write_text("# b\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "b")

    # The throwaway repository has no workflows, so every check that names a
    # CI step is a stale-registry block, and --list says so in its exit.
    assert ci_mirror.main(["--no-fetch", "--list"]) == 1
    out = capsys.readouterr().out
    assert "PLAN guard-tests would run" in out
    assert "FAIL ruff-check its CI step" in out
    assert out.rstrip().endswith("mirror exit: 1")


def test_the_console_script_is_installed():
    proc = subprocess.run(
        ["uv", "run", "prepush-ci-mirror", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert "--base" in proc.stdout


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_a_list_form_trigger_and_job_defaults_are_read(tmp_path: Path):
    from vultron.metadata.planning.ci_mirror._workflows import (
        pull_request_steps,
        pull_request_workflows,
    )

    _write(
        tmp_path,
        ".github/workflows/ci.yml",
        "on: [push, pull_request]\nenv:\n  TOP: t\njobs:\n  ui:\n"
        "    env:\n      JOB: j\n    defaults:\n      run:\n"
        "        working-directory: ui\n    steps:\n"
        "      - name: Lint\n        env:\n          STEP: s\n"
        "        run: npm run lint\n",
    )

    assert pull_request_workflows(tmp_path)["ci.yml"].runs_for("any", ["x"])
    step = pull_request_steps(tmp_path)["ci.yml::ui::Lint"]
    assert step.working_directory == "ui"
    assert step.env == {"TOP": "t", "JOB": "j", "STEP": "s"}


def test_a_local_action_without_an_action_file_is_an_error(tmp_path: Path):
    from vultron.metadata.planning.ci_mirror._workflows import workflow_steps

    _write(
        tmp_path,
        ".github/workflows/ci.yml",
        "on: pull_request\njobs:\n  j:\n    steps:\n"
        "      - uses: ./.github/actions/missing\n",
    )

    with pytest.raises(FileNotFoundError, match="missing"):
        workflow_steps(tmp_path, "ci.yml")


def test_list_json_reports_every_check(repo: Path, capsys):
    import json

    assert ci_mirror.main(["--no-fetch", "--list", "--json"]) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["exit"] == 1
    statuses = {c["id"]: c["status"] for c in payload["checks"]}
    assert statuses["guard-tests"] == "PLAN"
    assert "PASS" not in statuses.values()
    assert {c["id"] for c in payload["checks"]} == {
        c.id for c in MIRROR_CHECKS
    }


def test_the_base_is_fetched_from_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
):
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    (upstream / "a.txt").write_text("a\n")
    init_git_repo(upstream, monkeypatch)
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "-q", str(upstream), str(clone))
    (upstream / "b.txt").write_text("b\n")
    git(upstream, "add", ".")
    git(upstream, "commit", "-q", "-m", "moved")
    monkeypatch.chdir(clone)

    assert ci_mirror.main(["--list"]) != 2

    moved = subprocess.run(
        ["git", "log", "-1", "--format=%s", "origin/main"],
        cwd=clone, capture_output=True, text=True, check=True,
    ).stdout.strip()  # fmt: skip
    assert moved == "moved"


def _result(status: CheckStatus, log: str | None = None):
    from vultron.metadata.planning.ci_mirror._run import CheckResult

    return CheckResult("c", status, "why", 1.0, log, 1)


@pytest.mark.spec("PAD-18-021")
@pytest.mark.parametrize(
    "status", [CheckStatus.FAILED, CheckStatus.UNAVAILABLE]
)
def test_a_blocking_result_exits_1(status: CheckStatus, capsys):
    assert (
        ci_mirror.report([_result(CheckStatus.PASSED), _result(status)], False)
        == 1
    )

    assert capsys.readouterr().out.rstrip().endswith("mirror exit: 1")


@pytest.mark.parametrize(
    "status",
    [
        CheckStatus.PASSED,
        CheckStatus.NOT_TRIGGERED,
        CheckStatus.NOT_APPLICABLE,
        CheckStatus.SKIPPED,
    ],
)
def test_a_non_blocking_result_exits_0(status: CheckStatus, capsys):
    assert ci_mirror.report([_result(status)], False) == 0
    assert capsys.readouterr().out.rstrip().endswith("mirror exit: 0")


def test_a_failure_prints_its_log_tail(tmp_path: Path, capsys):
    log = tmp_path / "c.log"
    log.write_text("first\nthe real error\n")

    ci_mirror.report([_result(CheckStatus.FAILED, str(log))], False)

    out = capsys.readouterr().out
    assert f"log: {log}" in out
    assert "the real error" in out


def test_json_reports_real_results(capsys):
    import json

    assert ci_mirror.report([_result(CheckStatus.FAILED)], True) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["exit"] == 1
    assert payload["checks"][0]["status"] == "FAIL"


def test_a_later_group_member_failing_stops_nothing(tmp_path: Path):
    marker = tmp_path / "third-ran"
    results = run_checks(
        [
            _runnable("build", "true", group="site"),
            _runnable("links", "exit 1", group="site"),
            _runnable("boxes", f"touch {marker}", group="site"),
        ],
        tmp_path,
        jobs=1,
    )

    assert [r.status for r in results] == [
        CheckStatus.PASSED,
        CheckStatus.FAILED,
        CheckStatus.PASSED,
    ]
    assert marker.exists()


def test_a_timeout_kills_the_whole_process_group(tmp_path: Path):
    marker = tmp_path / "grandchild-survived"
    script = f"bash -c 'sleep 2 && touch {marker}' & wait"

    [result] = run_checks(
        [_runnable("slow", script)], tmp_path, jobs=1, timeout=1
    )

    assert result.status is CheckStatus.FAILED
    time.sleep(2.5)
    assert not marker.exists()


def test_logs_go_to_the_given_directory(tmp_path: Path):
    logs = tmp_path / "logs"

    [result] = run_checks(
        [_runnable("ok", "echo hi")], tmp_path, jobs=1, log_dir=logs
    )

    assert result.log == str(logs / "ok.log")
    assert (logs / "ok.log").read_text() == "hi\n"
