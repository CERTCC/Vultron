"""``prepush-ci-mirror`` plans and runs CI's pull-request checks locally (PAD-18-021).

Planning is checked against stand-in workflow steps, so each rule (trigger
filter, narrowed paths, PR number, missing tool, ``--skip``) is pinned on its
own; running is checked with real subprocesses, and the command line on a
throwaway repository.
"""

from __future__ import annotations

import fcntl
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import pytest

from test.support.git_repo import git, init_git_repo
from vultron.metadata.planning import ci_mirror
from vultron.metadata.planning.ci_mirror import _run
from vultron.metadata.planning.ci_mirror._registry import (
    EXCLUSIONS,
    MIRROR_CHECKS,
    RUN_IF_CHANGED,
    SITE_READER_PREFIX,
    SITE_READERS,
    CheckContext,
    MirrorCheck,
    markdownlint_command,
)
from vultron.metadata.planning.ci_mirror._run import (
    DEFAULT_TIMEOUT,
    LOCK_WAIT,
    STEP_SHELL,
    CheckStatus,
    PlannedCheck,
    heavy_ceiling,
    locked,
    plan,
    run_checks,
    run_in_session,
    stop_running,
    verdict,
)
from vultron.metadata.planning.ci_mirror._workflows import (
    PullRequestTrigger,
    WorkflowStep,
    matches_filter,
    pull_request_steps,
)
from vultron.metadata.planning.heavy_lock import HEAVY_LOCK, HEAVY_LOCK_SCRIPT

REPO_ROOT = Path(__file__).resolve().parents[2]


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


#: Every CI step PAD-18-023 makes CI's, by the exclusion key that names it.
#: All of them, not a representative of each kind: the five built-site readers
#: are one kind, and pinning one left the other four covered by nothing, so a
#: reader moved back into the mirror with its exclusion deleted passed both
#: this test and the parity test. Named, not counted: a renamed CI step must
#: fail here, and the parity test (PAD-18-022) refuses a key naming no step,
#: so neither can go stale unnoticed.
_CI_OWNED_STEPS = (
    "python-app.yml::lint-pyright::Type-check with pyright",
    "spec-check.yml::spec-tests::Run spec_corpus pytest suite",
    "guard-tests.yml::guard-tests::Run the guard tests",
    "docs-build-check.yml::docs-build-check::Build Site > Build Site",
    *(SITE_READER_PREFIX + label for label in SITE_READERS),
)


@pytest.mark.spec("PAD-18-023")
def test_the_pin_covers_every_built_site_reader() -> None:
    """Non-vacuity: the pin is built from the registry's own label list, so a
    sixth reader joins it without an edit here — and a shortened list cannot
    quietly drop one.
    """
    pinned = {s for s in _CI_OWNED_STEPS if s.startswith(SITE_READER_PREFIX)}
    assert pinned == {
        k for k in EXCLUSIONS if k.startswith(SITE_READER_PREFIX)
    }
    assert len(pinned) == len(SITE_READERS) >= 5


@pytest.mark.spec("PAD-18-023")
@pytest.mark.parametrize("step", _CI_OWNED_STEPS)
def test_the_mirror_leaves_cis_expensive_checks_to_ci(step: str) -> None:
    """None is mirrored, and each exclusion names CI as its owner."""
    assert step not in {c.step for c in MIRROR_CHECKS}
    reason = EXCLUSIONS[step]
    assert "CI" in reason, reason
    assert "PAD-18-023" in reason, reason


#: Diffs a command builder is probed with: Markdown alone and a lint config,
#: the two branches ``markdownlint_command`` has. A builder's command is as
#: much a command as a literal one.
_PROBE_DIFFS = (("AGENTS.md",), (".markdownlint-cli2.yaml",))


def _resolved_commands() -> dict[str, tuple[str, ...]]:
    """Every check's command text, however the registry spells it.

    A check with no ``command`` runs its CI step's own ``run:`` script
    (``_run._argv``), which is exactly where a forbidden invocation would
    hide. Reading only the tuple-valued commands inspected one of the 26
    (#5535), and ``MirrorCheck.command`` is typed ``Sequence[str]``, so a
    list literal — the natural form — was skipped too.
    """
    steps = pull_request_steps(REPO_ROOT)
    resolved: dict[str, tuple[str, ...]] = {}
    for check in MIRROR_CHECKS:
        if check.command is None:
            step = steps.get(check.step) if check.step else None
            assert step is not None and step.run is not None, (
                f"{check.id}: no command and no step run: script"
            )
            resolved[check.id] = (step.run,)
        elif callable(check.command):
            builder = check.command
            resolved[check.id] = tuple(
                " ".join(argv)
                for diff in _PROBE_DIFFS
                if (argv := builder(CheckContext({}, diff, REPO_ROOT)))
                is not None
            )
        else:
            resolved[check.id] = (" ".join(check.command),)
    return resolved


#: What PAD-18-023 forbids a mirror command, as patterns over its text.
#: Not the bare word ``pytest``: two mirror checks run one named test file
#: apiece (``story-page-shape``, ``docs-path-ratchet``), which is cheap and
#: allowed. What PAD-18-023 names is a *suite*, and both of the ones it names
#: are marker-selected — ``-m ""`` for the full tiers, ``-m spec_corpus`` for
#: the spec corpus — so marker selection is the bar.
_FORBIDDEN_COMMAND = (
    ("pyright", re.compile(r"(?<![\w./-])pyright(?![\w:])")),
    ("a marker-selected pytest suite", re.compile(r"pytest\b.*\s-m\s")),
    ("the site build", re.compile(r"mkdocs\s+build|mkdocs-build-strict\.sh")),
)


@pytest.mark.spec("PAD-18-023")
def test_no_mirror_check_runs_pyright_a_pytest_suite_or_the_site_build() -> (
    None
):
    """The commands too, not only the step keys: PAD-18-027 is about pyright
    wherever it is spelled, and the two pytest suites and the site build were
    the mirror's own commands as much as a verbatim CI step.
    """
    offenders = {
        f"{check_id}: {label}": line.strip()
        for check_id, commands in _resolved_commands().items()
        for command in commands
        for line in command.splitlines()
        for label, pattern in _FORBIDDEN_COMMAND
        if pattern.search(line)
    }

    assert not offenders, offenders


@pytest.mark.spec("PAD-18-023")
def test_the_command_scan_reads_every_check() -> None:
    """Non-vacuity: a scan that resolved nothing would find no offender."""
    resolved = _resolved_commands()

    assert set(resolved) == {c.id for c in MIRROR_CHECKS}
    assert all(resolved.values()), [k for k, v in resolved.items() if not v]
    # All three spellings reach the scan: a step's own `run:`, a literal
    # command, and a builder's output.
    assert "uv run ruff check" in resolved["ruff-check"][0]
    assert "uv run mypy" in resolved["mypy"][0]
    assert all("markdownlint" in c for c in resolved["markdownlint"])
    assert len(resolved["markdownlint"]) == len(_PROBE_DIFFS)


@pytest.mark.spec("PAD-18-023")
@pytest.mark.parametrize(
    "command",
    [
        "uv run pyright vultron/",
        "uvx pyright",
        'uv run pytest -m "" -n auto test/',
        'uv run pytest -m "" -n auto test/architecture/test_x.py',
        "uv run pytest -m spec_corpus",
        "mkdocs build --strict",
        ".github/scripts/mkdocs-build-strict.sh",
    ],
)
def test_the_forbidden_command_patterns_catch_each_form(command: str) -> None:
    """A detector that matched none of these would pass over a real breach."""
    assert any(p.search(command) for _, p in _FORBIDDEN_COMMAND), command


@pytest.mark.spec("PAD-18-023")
@pytest.mark.parametrize(
    "command",
    [
        "uv run pytest test/metadata/docs/test_story_pages.py -q -n 0",
        "uv run pytest test/architecture/test_codebase_docs_paths.py",
        "PYTHONPATH='' uv run docs-site --check",
        "bash .agents/skills/shared/run-if-changed.sh mypy vultron/",
    ],
)
def test_the_forbidden_command_patterns_allow_a_cheap_check(
    command: str,
) -> None:
    """And one that matched these would red on the mirror as it stands."""
    assert not [lbl for lbl, p in _FORBIDDEN_COMMAND if p.search(command)]


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


def test_a_check_over_its_timeout_has_no_verdict(tmp_path: Path):
    # A ceiling trip is the environment, not a finding, and says what to do.
    [result] = run_checks(
        [_runnable("slow", "sleep 5")], tmp_path, jobs=1, timeout=1
    )

    assert result.status is CheckStatus.NO_VERDICT
    assert result.status.blocks
    assert result.reason.startswith("timed out (1s); rerun it with a longer")
    assert "--timeout" in result.reason


@pytest.mark.parametrize(
    ("code", "output", "expected"),
    [
        (247, "", CheckStatus.NO_VERDICT),
        (-9, "", CheckStatus.NO_VERDICT),
        (137, "run-heavy: waiting for another heavy check to finish\n",
         CheckStatus.NO_VERDICT),
        (137, "Traceback: the real error\n", CheckStatus.FAILED),
        (1, "", CheckStatus.FAILED),
    ],
)  # fmt: skip
def test_a_silent_signal_death_has_no_verdict(
    tmp_path: Path, code: int, output: str, expected: CheckStatus
):
    # #5735: pyright's out-of-memory kill left an empty log and exit 247. A
    # silent exit 1 is still a finding: some checks fail without a word.
    log = tmp_path / "c.log"
    log.write_text(output)

    status, reason = verdict(MirrorCheck("c", None), code, 60, log)

    assert status is expected
    if expected is CheckStatus.NO_VERDICT:
        assert reason.startswith(f"exit {code} with no output")
        assert "rerun it with nothing else running" in reason
    else:
        assert reason == f"exit {code}"


def test_the_ceiling_defaults_and_can_be_raised(
    monkeypatch: pytest.MonkeyPatch,
):
    seen: list[int] = []
    monkeypatch.setattr(ci_mirror, "_setup", lambda _a: (Path("."), None))
    monkeypatch.setattr(ci_mirror, "plan", lambda *_a, **_k: [])
    monkeypatch.setattr(ci_mirror, "pull_request_steps", lambda *_a: {})
    monkeypatch.setattr(ci_mirror, "pull_request_workflows", lambda *_a: {})

    def fake_run(_planned, _root, *, jobs, timeout, env):
        seen.append(timeout)
        return []

    monkeypatch.setattr(ci_mirror, "run_checks", fake_run)

    assert ci_mirror.main([]) == 0
    assert ci_mirror.main(["--timeout", "2400"]) == 0
    assert seen == [DEFAULT_TIMEOUT, 2400]


@pytest.mark.parametrize("value", ["0", "-5", "soon"])
def test_a_ceiling_that_is_not_a_positive_number_is_refused(value: str):
    with pytest.raises(SystemExit) as raised:
        ci_mirror.main(["--timeout", value])

    assert raised.value.code == 2


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

    # The throwaway repository has no workflows, so every check is a
    # stale-registry block, and --list says so in its exit. Every registry
    # check names a CI step now that PAD-18-023 retired the guard-test check,
    # the one that named none; the PLAN row is covered below.
    assert ci_mirror.main(["--no-fetch", "--list"]) == 1
    out = capsys.readouterr().out
    assert "FAIL ruff-check its CI step" in out
    assert out.rstrip().endswith("mirror exit: 1")


def test_list_prints_plan_for_a_check_that_would_run(capsys):
    rows = ci_mirror._planned_rows([_plan(MirrorCheck("lint", _KEY))])

    assert ci_mirror.print_report(rows, as_json=False) == 0
    assert "PLAN lint would run" in capsys.readouterr().out


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
    # The throwaway repository has no workflows, so every check reports the
    # stale registry rather than a plan.
    assert set(statuses.values()) == {"FAIL"}
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
    "status",
    [CheckStatus.FAILED, CheckStatus.NO_VERDICT, CheckStatus.UNAVAILABLE],
)
def test_a_blocking_result_exits_1(status: CheckStatus, capsys):
    assert (
        ci_mirror.print_report(
            [_result(CheckStatus.PASSED), _result(status)], False
        )
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
    assert ci_mirror.print_report([_result(status)], False) == 0
    assert capsys.readouterr().out.rstrip().endswith("mirror exit: 0")


def test_a_failure_prints_its_log_tail(tmp_path: Path, capsys):
    log = tmp_path / "c.log"
    log.write_text("first\nthe real error\n")

    ci_mirror.print_report([_result(CheckStatus.FAILED, str(log))], False)

    out = capsys.readouterr().out
    assert f"log: {log}" in out
    assert "the real error" in out


def test_json_reports_real_results(capsys):
    import json

    assert ci_mirror.print_report([_result(CheckStatus.FAILED)], True) == 1

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

    assert result.status is CheckStatus.NO_VERDICT
    time.sleep(2.5)
    assert not marker.exists()


def test_an_interrupt_kills_the_whole_process_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # An interrupt unwinds through this wait; a check's grandchildren (an
    # xdist worker, a site build) must not outlive the mirror that started it.
    marker = tmp_path / "grandchild-survived"
    script = f"bash -c 'sleep 2 && touch {marker}' & wait"
    real_wait = subprocess.Popen.wait

    def interrupted(proc: subprocess.Popen[str], timeout: float | None = None):
        if timeout is not None:
            raise KeyboardInterrupt
        return real_wait(proc)

    monkeypatch.setattr(subprocess.Popen, "wait", interrupted)

    with (
        (tmp_path / "out.log").open("w") as out,
        pytest.raises(KeyboardInterrupt),
    ):
        run_in_session(
            ["bash", "-c", script], cwd=tmp_path, env={}, out=out, timeout=60
        )

    time.sleep(2.5)
    assert not marker.exists()


def test_logs_go_to_the_given_directory(tmp_path: Path):
    logs = tmp_path / "logs"

    [result] = run_checks(
        [_runnable("ok", "echo hi")], tmp_path, jobs=1, log_dir=logs
    )

    assert result.log == str(logs / "ok.log")
    assert (logs / "ok.log").read_text() == "hi\n"


# ---------------------------------------------------------------------------
# The per-host heavy-check slots (#5947)
# ---------------------------------------------------------------------------

_LOCK_PREFIX = (*HEAVY_LOCK, "--wait", str(LOCK_WAIT), "--")


def _with_timeout(seconds: int) -> tuple[str, ...]:
    return ("timeout", "-k", "30", str(seconds))


def _found(tool: str) -> str | None:
    return "/usr/bin/" + tool


def _missing(_tool: str) -> str | None:
    return None


@pytest.fixture(autouse=True)
def _mirror_not_stopping():
    # stop_running() sets a process-wide flag; no test may leak it.
    _run._STOPPING.clear()
    yield
    _run._STOPPING.clear()


@pytest.fixture
def slots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A private slot directory with one slot, so no test takes a real one."""
    locks = tmp_path / "locks"
    locks.mkdir()
    (locks / "slots").write_text("1\n")
    monkeypatch.setenv("VULTRON_HEAVY_LOCK_DIR", str(locks))
    monkeypatch.delenv("VULTRON_HEAVY_LOCK_HELD", raising=False)
    return locks


def test_no_registry_check_declares_itself_heavy():
    """PAD-18-023 made every check that loaded the container CI's.

    pyright, the spec-corpus suite, the guard tests and the site build were
    the four. The ``heavy`` field and its locking stay for a CI step cheap
    enough to mirror and heavy enough to queue; this fails on the next check
    that declares it, so adding one is a decision somebody makes (#5947).
    """
    assert {c.id for c in MIRROR_CHECKS if c.heavy} == set()


def test_a_heavy_check_takes_a_slot_then_its_own_timeout():
    argv = (*STEP_SHELL, "make lint")

    assert locked(argv, 900, which=_found) == (
        *_LOCK_PREFIX,
        *_with_timeout(900),
        *argv,
    )


def test_without_a_timeout_binary_only_the_backstop_bounds_the_run():
    assert locked(("uv", "run", "pytest"), 900, which=_missing) == (
        *_LOCK_PREFIX,
        *("uv", "run", "pytest"),
    )


def test_a_light_check_plans_no_slot():
    planned = _plan(MirrorCheck("lint", _KEY))

    assert planned.argv is not None
    assert HEAVY_LOCK_SCRIPT not in planned.argv


def test_locking_a_memoized_command_goes_inside_its_memo():
    # A memo hit skips without waiting behind another slot's suite. No
    # registry check declares `heavy` since PAD-18-023, so the subject is the
    # registry's one remaining memoized command rather than a hand-built
    # argv, which could drift from the shape `_memoized` really produces.
    [mypy] = [c for c in MIRROR_CHECKS if c.id == "mypy"]
    assert not callable(mypy.command) and mypy.command is not None

    argv = locked(mypy.command, 900, which=_found)

    cut = argv.index("--") + 1
    assert argv[:2] == ("bash", RUN_IF_CHANGED)
    assert argv[cut:] == (
        *_LOCK_PREFIX,
        *_with_timeout(900),
        *("uv", "run", "mypy"),
    )


def test_the_backstop_covers_the_wait_and_the_run():
    assert heavy_ceiling(900) > LOCK_WAIT + 900


def _heavy(
    check_id: str, argv: tuple[str, ...], group: str | None = None
) -> PlannedCheck:
    check = MirrorCheck(
        check_id, None, command=("x",), note="n", heavy=True, group=group
    )
    return PlannedCheck(check, argv, None, {}, None)


def test_a_heavy_check_that_never_gets_a_slot_has_no_verdict(
    tmp_path: Path, slots: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(_run, "LOCK_WAIT", 1)
    marker = tmp_path / "ran"

    with (slots / "heavy-0.lock").open("a") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        [result] = run_checks(
            [_heavy("big", ("touch", str(marker)))],
            REPO_ROOT,
            jobs=1,
            log_dir=tmp_path / "logs",
        )

    assert result.status is CheckStatus.NO_VERDICT
    assert result.reason.startswith(
        "not run: waited 1s for a heavy-check slot; rerun it"
    )
    assert not marker.exists()


def test_a_check_that_exits_75_by_itself_is_a_finding(tmp_path: Path):
    # Only the wrapper's own line marks a check that never got a slot.
    log = tmp_path / "c.log"
    log.write_text("the check's own complaint\n")

    status, reason = verdict(MirrorCheck("c", None, heavy=True), 75, 60, log)

    assert (status, reason) == (CheckStatus.FAILED, "exit 75")


@pytest.mark.skipif(shutil.which("timeout") is None, reason="needs timeout")
def test_a_heavy_check_over_its_own_timeout_has_no_verdict(
    tmp_path: Path, slots: Path
):
    # --timeout bounds the run itself, once the check holds its slot.
    [result] = run_checks(
        [_heavy("big", (*STEP_SHELL, "sleep 10"))],
        REPO_ROOT,
        jobs=1,
        timeout=1,
        log_dir=tmp_path / "logs",
    )

    assert result.status is CheckStatus.NO_VERDICT
    assert result.reason.startswith("timed out (1s)")


def test_a_lane_behind_a_check_with_no_verdict_has_no_verdict(
    tmp_path: Path, slots: Path, monkeypatch: pytest.MonkeyPatch
):
    # #5735: the site build getting no slot must not turn its readers into
    # findings.
    monkeypatch.setattr(_run, "LOCK_WAIT", 1)
    reader = _runnable("read", "true", group="site")

    with (slots / "heavy-0.lock").open("a") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        build, read = run_checks(
            [_heavy("build", ("true",), group="site"), reader],
            REPO_ROOT,
            jobs=1,
            log_dir=tmp_path / "logs",
        )

    assert build.status is CheckStatus.NO_VERDICT
    assert (read.status, read.reason) == (
        CheckStatus.NO_VERDICT,
        "not run: build had no verdict",
    )


def test_stopping_the_mirror_kills_its_running_checks(tmp_path: Path):
    # A terminated mirror must not leave a heavy check holding its slot.
    marker = tmp_path / "survived"
    script = f"bash -c 'sleep 3 && touch {marker}' & wait"
    finished: list[int | None] = []

    def run() -> None:
        with (tmp_path / "out.log").open("w") as out:
            finished.append(
                run_in_session(
                    ["bash", "-c", script],
                    cwd=tmp_path,
                    env={},
                    out=out,
                    timeout=60,
                )
            )

    worker = threading.Thread(target=run)
    worker.start()
    deadline = time.monotonic() + 20
    while not _run._RUNNING:
        assert time.monotonic() < deadline, "the check never started"
        time.sleep(0.05)

    stop_running()
    worker.join(timeout=20)

    assert len(finished) == 1 and finished[0] is not None and finished[0] < 0
    assert not _run._RUNNING
    time.sleep(3.5)
    assert not marker.exists()


@pytest.mark.skipif(shutil.which("timeout") is None, reason="needs timeout")
def test_stopping_the_mirror_ends_a_heavy_checks_command(
    tmp_path: Path, slots: Path
):
    # The real heavy argv: GNU timeout sits in a process group of its own
    # under the slot wrapper, so a kill of the session's group alone would
    # leave the command running without its slot.
    started, marker = tmp_path / "started", tmp_path / "survived"
    argv = locked(
        ("bash", "-c", f"touch {started}; sleep 3; touch {marker}"), 300
    )
    finished: list[int | None] = []

    def run() -> None:
        with (tmp_path / "out.log").open("w") as out:
            finished.append(
                run_in_session(
                    argv,
                    cwd=REPO_ROOT,
                    env=dict(os.environ),
                    out=out,
                    timeout=120,
                )
            )

    worker = threading.Thread(target=run)
    worker.start()
    deadline = time.monotonic() + 60
    while not started.exists():
        assert time.monotonic() < deadline, "the check never started"
        time.sleep(0.05)

    stop_running()
    worker.join(timeout=60)

    assert len(finished) == 1 and finished[0] != 0
    time.sleep(4)
    assert not marker.exists(), "the command outlived the stopped mirror"


@pytest.mark.skipif(shutil.which("timeout") is None, reason="needs timeout")
def test_a_heavy_check_killed_after_its_grace_has_no_verdict(
    tmp_path: Path, slots: Path, monkeypatch: pytest.MonkeyPatch
):
    # A command that ignores SIGTERM is killed after the -k grace, and
    # timeout exits 137, not 124; it still ran out of time (#5735).
    monkeypatch.setattr(_run, "_KILL_GRACE", 1)
    script = "echo progress; trap '' TERM; sleep 30"
    [result] = run_checks(
        [_heavy("stuck", (*STEP_SHELL, script))],
        REPO_ROOT,
        jobs=1,
        timeout=1,
        log_dir=tmp_path / "logs",
    )

    assert result.returncode is None
    assert result.status is CheckStatus.NO_VERDICT
    assert result.reason.startswith("timed out (1s)")


@pytest.mark.parametrize(
    ("code", "seconds", "expected"),
    [(124, 0.5, True), (137, 5.0, True), (137, 0.5, False), (1, 5.0, False)],
)
def test_only_the_checks_own_timeout_reads_as_running_out(
    code: int, seconds: float, expected: bool
):
    assert _run._ran_out(code, seconds, 2) is expected


def test_sigterm_stops_the_checks_and_exits_143(
    monkeypatch: pytest.MonkeyPatch,
):
    stopped: list[bool] = []
    monkeypatch.setattr(
        ci_mirror, "stop_running", lambda: stopped.append(True)
    )

    with pytest.raises(SystemExit) as raised:
        ci_mirror._on_sigterm(15, None)

    assert raised.value.code == ci_mirror.SIGTERM_EXIT == 143
    assert stopped == [True]


def test_no_check_starts_once_the_mirror_is_stopping(tmp_path: Path):
    # A lane must not start its next member after SIGTERM killed the last.
    marker = tmp_path / "ran"
    stop_running()

    with pytest.raises(_run.MirrorStopped):
        run_checks([_runnable("late", f"touch {marker}")], tmp_path, jobs=1)

    assert not marker.exists()


def test_main_stops_the_checks_on_sigterm_and_restores_the_handler(
    monkeypatch: pytest.MonkeyPatch,
):
    stopped: list[bool] = []
    monkeypatch.setattr(
        ci_mirror, "stop_running", lambda: stopped.append(True)
    )
    monkeypatch.setattr(ci_mirror, "_setup", lambda _a: (Path("."), None))
    monkeypatch.setattr(ci_mirror, "plan", lambda *_a, **_k: [])
    monkeypatch.setattr(ci_mirror, "pull_request_steps", lambda *_a: {})
    monkeypatch.setattr(ci_mirror, "pull_request_workflows", lambda *_a: {})

    def terminated(*_args, **_kwargs):
        os.kill(os.getpid(), signal.SIGTERM)
        time.sleep(5)  # The handler raises before this ends.
        return []

    monkeypatch.setattr(ci_mirror, "run_checks", terminated)
    before = signal.getsignal(signal.SIGTERM)

    with pytest.raises(SystemExit) as raised:
        ci_mirror.main([])

    assert raised.value.code == 143
    assert stopped == [True]
    assert signal.getsignal(signal.SIGTERM) is before
