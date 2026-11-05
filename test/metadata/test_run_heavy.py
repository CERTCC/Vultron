"""``.agents/skills/shared/run-heavy.py`` caps concurrent heavy checks per host (#5947).

Every slot container on a host shares the slot lock files in one named volume.
Each test points the wrapper at its own directory (``VULTRON_HEAVY_LOCK_DIR``),
so a suite that is itself running in a real slot neither waits on the real
slots nor holds one up. The wrapper runs under this interpreter rather than
``uv run python``: the behavior under test is the script's, not uv's.
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType

import pytest

from vultron.metadata.planning.heavy_lock import (
    HEAVY_LOCK,
    HEAVY_LOCK_SCRIPT,
    WAIT_EXPIRED,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / HEAVY_LOCK_SCRIPT
BASH = shutil.which("bash") or "/bin/bash"
WAIT_LINE = "heavy-check slots on this host are busy; waiting"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("run_heavy", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run_heavy = _load()


@pytest.fixture
def lock_dir(tmp_path: Path) -> Path:
    path = tmp_path / "locks"
    path.mkdir()
    (path / "slots").write_text("2\n")
    return path


@pytest.fixture
def env(lock_dir: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["VULTRON_HEAVY_LOCK_DIR"] = str(lock_dir)
    env.pop("VULTRON_HEAVY_LOCK_HELD", None)
    return env


def _start(
    env: dict[str, str],
    *command: str,
    wait: int | None = None,
    capture: bool = True,
) -> subprocess.Popen[str]:
    limit = [] if wait is None else ["--wait", str(wait)]
    out = subprocess.PIPE if capture else subprocess.DEVNULL
    return subprocess.Popen(
        [sys.executable, str(SCRIPT), *limit, "--", *command],
        env=env,
        stdout=out,
        stderr=out,
        text=True,
        start_new_session=True,
    )


def _finish(proc: subprocess.Popen[str]) -> subprocess.CompletedProcess[str]:
    out, err = proc.communicate(timeout=60)
    return subprocess.CompletedProcess(proc.args, proc.returncode, out, err)


def _run(
    env: dict[str, str], *command: str, wait: int | None = None
) -> subprocess.CompletedProcess[str]:
    return _finish(_start(env, *command, wait=wait))


def _await(path: Path, seconds: float = 20.0) -> None:
    deadline = time.monotonic() + seconds
    while not path.exists():
        assert time.monotonic() < deadline, f"{path} never appeared"
        time.sleep(0.05)


def _holder(where: Path, name: str, status: int, release: Path) -> str:
    """Touch ``<name>.started``, wait for *release*, touch ``<name>.ended``."""
    started, ended = where / f"{name}.started", where / f"{name}.ended"
    return (
        f"touch {started}; while [ ! -e {release} ]; do sleep 0.05; done; "
        f"touch {ended}; exit {status}"
    )


def test_a_third_check_waits_until_one_of_two_slots_frees(
    tmp_path: Path, env: dict[str, str]
):
    release_a, release_b = tmp_path / "go-a", tmp_path / "go-b"
    a = _start(env, BASH, "-c", _holder(tmp_path, "a", 3, release_a))
    b = _start(env, BASH, "-c", _holder(tmp_path, "b", 4, release_b))
    _await(tmp_path / "a.started")
    _await(tmp_path / "b.started")

    c = _start(env, BASH, "-c", f"touch {tmp_path}/c.started; exit 5")
    time.sleep(1.5)
    waited = not (tmp_path / "c.started").exists()
    release_a.touch()
    c_done = _finish(c)
    release_b.touch()
    a_done, b_done = _finish(a), _finish(b)

    assert waited, "the third check ran while both slots were held"
    assert (tmp_path / "a.ended").exists()
    assert (a_done.returncode, b_done.returncode, c_done.returncode) == (
        3,
        4,
        5,
    )
    assert c_done.stderr.count(WAIT_LINE) == 1
    assert "all 2 heavy-check slots" in c_done.stderr
    assert f"pid {a.pid} on " in c_done.stderr


def test_a_killed_holder_frees_its_slot(lock_dir: Path, env: dict[str, str]):
    (lock_dir / "slots").write_text("1\n")
    started = lock_dir.parent / "started"
    # Not captured: the orphaned command would hold the pipes open.
    holder = _start(
        env, BASH, "-c", f"touch {started}; sleep 30", capture=False
    )
    _await(started)

    os.kill(holder.pid, signal.SIGKILL)
    holder.wait(timeout=60)
    try:
        # The command outlives the killed wrapper, and holds no slot.
        waiter = _run(env, "true", wait=10)
    finally:
        os.killpg(holder.pid, signal.SIGKILL)

    assert waiter.returncode == 0


def test_a_terminated_wrapper_stops_its_command_first(
    lock_dir: Path, env: dict[str, str]
):
    # SIGTERM reaches the command, so the slot frees once the command ends.
    where = lock_dir.parent
    started, survived = where / "started", where / "survived"
    script = f"trap 'exit 9' TERM; touch {started}; sleep 5 & wait; touch {survived}"
    holder = _start(env, BASH, "-c", script)
    _await(started)

    holder.send_signal(signal.SIGTERM)
    result = _finish(holder)

    assert result.returncode == 9
    assert not survived.exists()


def test_a_waiting_check_runs_when_a_slot_frees_in_time(
    lock_dir: Path, env: dict[str, str]
):
    (lock_dir / "slots").write_text("1\n")
    where = lock_dir.parent
    holder = _start(env, BASH, "-c", _holder(where, "h", 0, where / "go"))
    _await(where / "h.started")

    waiter = _start(env, BASH, "-c", "exit 6", wait=30)
    time.sleep(1.0)
    (where / "go").touch()

    assert _finish(waiter).returncode == 6
    assert _finish(holder).returncode == 0


def test_a_check_that_waits_too_long_gives_up_unrun(
    lock_dir: Path, env: dict[str, str]
):
    (lock_dir / "slots").write_text("1\n")
    where = lock_dir.parent
    marker = where / "ran"
    holder = _start(env, BASH, "-c", _holder(where, "h", 0, where / "go"))
    _await(where / "h.started")

    try:
        waiter = _run(env, "touch", str(marker), wait=1)
    finally:
        (where / "go").touch()
        _finish(holder)

    assert waiter.returncode == WAIT_EXPIRED
    assert "gave up after 1s waiting for a heavy-check slot" in waiter.stderr
    assert not marker.exists()


def test_an_uncontested_check_prints_nothing_and_keeps_its_status(
    env: dict[str, str],
):
    result = _run(env, BASH, "-c", "echo out; exit 7")

    assert (result.returncode, result.stdout, result.stderr) == (
        7,
        "out\n",
        "",
    )


def test_a_command_ended_by_a_signal_exits_128_plus_it(env: dict[str, str]):
    assert _run(env, BASH, "-c", "kill -KILL $$").returncode == 128 + 9


def test_a_missing_command_exits_127(env: dict[str, str]):
    result = _run(env, "no-such-command-5947")

    assert result.returncode == 127
    assert "command not found: no-such-command-5947" in result.stderr


def test_a_check_inside_a_check_takes_no_second_slot(
    lock_dir: Path, env: dict[str, str]
):
    (lock_dir / "slots").write_text("1\n")
    nested = f"{sys.executable} {SCRIPT} --wait 2 -- true; echo nested=$?"

    result = _run(env, BASH, "-c", nested)

    assert (result.returncode, result.stdout) == (0, "nested=0\n")


def test_an_unusable_lock_directory_runs_without_a_slot(
    tmp_path: Path, env: dict[str, str]
):
    blocker = tmp_path / "file"
    blocker.write_text("")
    env = {**env, "VULTRON_HEAVY_LOCK_DIR": str(blocker / "locks")}

    result = _run(env, BASH, "-c", "exit 6")

    assert result.returncode == 6
    assert "running without a slot" in result.stderr


@pytest.mark.parametrize(
    ("content", "expected"),
    [("3\n", 3), ("1", 1), ("0\n", 2), ("-4\n", 2), ("many\n", 2), (None, 2)],
)
def test_the_slot_count_comes_from_the_slots_file(
    tmp_path: Path, content: str | None, expected: int
):
    if content is not None:
        (tmp_path / "slots").write_text(content)

    assert run_heavy.slot_count(tmp_path) == expected


@pytest.mark.parametrize(
    "args", [[], ["--"], ["--wait"], ["--wait", "soon", "true"]]
)
def test_a_malformed_call_is_a_usage_error(
    args: list[str], env: dict[str, str]
):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert result.stderr.startswith("run-heavy: ")


def test_the_wait_has_a_default_limit():
    # A gate behind a holder that never ends still ends (TB-14-005).
    wait, command = run_heavy.parse_args(["true"])

    assert (wait, command) == (run_heavy.DEFAULT_WAIT, ["true"])
    assert run_heavy.WAIT_EXPIRED == WAIT_EXPIRED


def test_the_python_tools_run_the_script_through_uv():
    assert HEAVY_LOCK == ("uv", "run", "python", HEAVY_LOCK_SCRIPT)
    assert SCRIPT.is_file()


# --- start-dev.sh writes the slot count. It runs on the host; these tests run
# its arithmetic and check where it is called, not the docker calls. --------

START_DEV = REPO_ROOT / "start-dev.sh"


def _function(name: str) -> str:
    text = START_DEV.read_text(encoding="utf-8")
    match = re.search(rf"^{name}\(\) \{{\n.*?^\}}\n", text, re.M | re.S)
    assert match, f"start-dev.sh defines no {name}()"
    return match.group(0)


@pytest.mark.parametrize(
    ("vm_cpus", "slot_cpus", "heavy_slots", "expected"),
    [
        ("20", "6", "", "3"),
        ("4", "6", "", "1"),
        ("20", "1.5", "", "20"),
        ("20", "6", "5", "5"),
        ("20", "6", "x", "3"),
        ("20", "6", "0", "3"),
        ("20", "6", "00", "3"),
        ("20", "6", "08", "8"),
        ("20", "0", "", "20"),
        ("20", "00", "", "20"),
        ("unknown", "6", "", "1"),
    ],
)
def test_start_dev_derives_the_slot_count(
    vm_cpus: str, slot_cpus: str, heavy_slots: str, expected: str
):
    script = (
        f"_vm_cpus='{vm_cpus}'; SLOT_CPUS='{slot_cpus}'; "
        f"HEAVY_SLOTS='{heavy_slots}'\n{_function('_heavy_slots_invalid')}"
        f"{_function('_heavy_slots')}_heavy_slots\n"
    )
    result = subprocess.run(
        [BASH, "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout == f"{expected}\n"
    warned = heavy_slots in ("x", "0", "00")
    assert ("is not a positive whole number" in result.stderr) is warned


def test_start_dev_writes_the_slot_count_on_create_and_on_attach():
    text = START_DEV.read_text(encoding="utf-8")
    writer = _function("_write_heavy_slots")
    attach = text[
        text.index("# Container exists") : text.index(
            "_exec_shell\n    exit 0"
        )
    ]
    create = text[text.index('docker run -d "${DOCKER_ARGS[@]}"') :]

    assert (
        '"$dir/slots"' in writer and "dir=/home/vscode/.data/locks" in writer
    )
    # Each writer has its own temp file in the shared directory.
    assert 'mktemp "$dir/slots.XXXXXX"' in writer
    assert "_write_heavy_slots" in attach
    assert "_write_heavy_slots" in create.split("_exec_shell")[0]


def test_an_unopenable_slot_file_is_skipped(
    lock_dir: Path, env: dict[str, str]
):
    # A slot file the wrapper cannot open does not switch the limit off.
    (lock_dir / "heavy-0.lock").mkdir()

    result = _run(env, BASH, "-c", "exit 4")

    assert result.returncode == 4
    assert result.stderr == ""
    assert (lock_dir / "heavy-1.holder").exists()


def test_no_openable_slot_file_runs_without_a_slot(
    lock_dir: Path, env: dict[str, str]
):
    (lock_dir / "heavy-0.lock").mkdir()
    (lock_dir / "heavy-1.lock").mkdir()

    result = _run(env, BASH, "-c", "exit 4")

    assert result.returncode == 4
    assert "running without a slot" in result.stderr


def test_a_command_that_is_not_executable_exits_126(
    tmp_path: Path, env: dict[str, str]
):
    script = tmp_path / "not-executable"
    script.write_text("#!/bin/sh\nexit 0\n")
    script.chmod(0o644)

    result = _run(env, str(script))

    assert result.returncode == 126
    assert f"command not executable: {script}" in result.stderr


def test_a_holder_record_that_cannot_be_written_still_runs(
    lock_dir: Path, env: dict[str, str]
):
    # The record only names the holder in a wait line; losing it is harmless.
    (lock_dir / "heavy-0.holder").mkdir()

    result = _run(env, BASH, "-c", "exit 8")

    assert (result.returncode, result.stderr) == (8, "")
