"""The case shadow tool leaves no copy of a case on the host after it exits.

A child process runs the tool's page over a synthetic case whose content
holds a marker string, inside the launcher's private temporary directory,
and writes one transient working file that holds the marker too.  After
the child exits, the marker is in no file under its working directory, its
temporary directory or its home (which holds ``~/.streamlit``): when it
exits normally (AC-1), when the read fails partway through translation,
and when it is stopped with ``SIGTERM`` while it holds the case (AC-2).
The child drives the page with Streamlit's ``AppTest``, so it reads and
holds the case exactly as a browser session would, without a socket.

The launcher runs Streamlit inside the private directory, and a real
``vultron-shadow`` server stopped with ``SIGTERM`` removes it.

Spec: SHD-01-003.
"""

from __future__ import annotations

import ast
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from click.testing import CliRunner

from test.support.child_env import child_env
from vultron.demo.recordings.layout import RECORDINGS_DIR
from vultron.metadata.base import repo_root
from vultron.shadow.dashboard import cli
from vultron.shadow.dashboard.lifecycle import TEMPDIR_PREFIX, private_tempdir

_SHADOW = repo_root() / "vultron" / "shadow"

#: The recorded case the synthetic one is made from, and the text in it the
#: marker replaces: the case's name, which every snapshot of it repeats.
_RECORDING = RECORDINGS_DIR / "rv" / "case-actor.jsonl"
_CASE_NAME = "Remote Code Execution in Network Stack"
_ROWS = 3

#: Seconds a child may take to start, read a case and exit.
_CHILD_TIMEOUT = 25

_DRIVER = """
import sys, tempfile, time
from pathlib import Path

from streamlit.testing.v1 import AppTest

from vultron.shadow.dashboard.app import APP_PATH
from vultron.shadow.dashboard.lifecycle import private_tempdir

mode, case_id, marker, ready = sys.argv[1:]
with private_tempdir():
    # A transient working file that holds the case's content.
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(marker)
    at = AppTest.from_file(str(APP_PATH), default_timeout=20).run()
    at.selectbox[0].select(case_id).run()
    assert not at.exception, at.exception
    errors = [e.value for e in at.error]
    subheaders = [s.value for s in at.subheader]
    if mode == "fails":
        assert errors and "Participants" not in subheaders, errors
    else:
        assert not errors and "Participants" in subheaders, errors
    if mode == "sigterm":
        # Written only now: the SIGTERM handler is set and the case is held.
        Path(ready).write_text("held")
        time.sleep(60)
        sys.exit("SIGTERM did not stop the run")
"""


#: ``vultron-shadow`` itself, run by this checkout's interpreter.
_LAUNCHER = "from vultron.shadow.dashboard.cli import main; main()"


@dataclass(frozen=True)
class _Host:
    """The directories a child run may write to, and the case it reads."""

    work: Path
    home: Path
    tmp: Path
    cases: Path
    marker: str

    def env(self) -> dict[str, str]:
        env = child_env()
        env.update(
            HOME=str(self.home),
            TMPDIR=str(self.tmp),
            VULTRON_SHADOW__LEDGER_DIR=str(self.cases),
        )
        env.pop("VULTRON_SHADOW__CONNECTOR", None)
        return env

    def files_holding_the_marker(self) -> list[Path]:
        needle = self.marker.encode()
        return sorted(
            path
            for root in (self.work, self.home, self.tmp)
            for path in root.rglob("*")
            if path.is_file() and needle in path.read_bytes()
        )

    def leftover_tempdirs(self) -> list[Path]:
        return sorted(self.tmp.glob(f"{TEMPDIR_PREFIX}*"))


@pytest.fixture
def host(tmp_path: Path) -> _Host:
    marker = f"SHADOW-MARKER-{uuid.uuid4().hex}"
    found = _Host(
        work=tmp_path / "work",
        home=tmp_path / "home",
        tmp=tmp_path / "tmp",
        cases=tmp_path / "cases",
        marker=marker,
    )
    for path in (found.work, found.home, found.tmp, found.cases):
        path.mkdir()
    # The recording's first rows: a ledger with no hole, short enough that
    # its analysis is quick.
    rows = _RECORDING.read_text().splitlines()[:_ROWS]
    assert _CASE_NAME in rows[0]
    synthetic = "".join(f"{row}\n" for row in rows).replace(_CASE_NAME, marker)
    (found.cases / "held.jsonl").write_text(synthetic)
    # A read that fails partway: the marker's rows, then a row that is not
    # a ledger entry.
    (found.cases / "fails.jsonl").write_text(synthetic + "not json\n")
    return found


def _driver(host: _Host, mode: str, case_id: str) -> list[str]:
    return [
        sys.executable,
        "-c",
        _DRIVER,
        mode,
        case_id,
        host.marker,
        str(host.work / "ready"),
    ]


def _run(host: _Host, mode: str, case_id: str) -> None:
    result = subprocess.run(
        _driver(host, mode, case_id),
        check=False,
        capture_output=True,
        text=True,
        cwd=host.work,
        env=host.env(),
        timeout=_CHILD_TIMEOUT,
    )
    assert result.returncode == 0, result.stderr


def _assert_nothing_left(host: _Host) -> None:
    assert host.files_holding_the_marker() == []
    assert host.leftover_tempdirs() == []


@pytest.mark.spec("SHD-01-003")
def test_a_case_read_leaves_no_copy_after_the_process_exits(host):
    _run(host, "held", "held.jsonl")
    _assert_nothing_left(host)


@pytest.mark.spec("SHD-01-003")
def test_a_read_that_fails_partway_leaves_no_copy(host):
    _run(host, "fails", "fails.jsonl")
    _assert_nothing_left(host)


def _wait_for(path: Path, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + _CHILD_TIMEOUT
    while not path.exists():
        if process.poll() is not None:
            _, stderr = process.communicate()
            pytest.fail(f"the run ended before it was ready: {stderr}")
        if time.monotonic() > deadline:
            process.kill()
            pytest.fail("the run was not ready in time")
        time.sleep(0.1)


@pytest.mark.spec("SHD-01-003")
def test_sigterm_while_a_case_is_held_leaves_no_copy(host):
    process = subprocess.Popen(
        _driver(host, "sigterm", "held.jsonl"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=host.work,
        env=host.env(),
    )
    try:
        _wait_for(host.work / "ready", process)
        process.send_signal(signal.SIGTERM)
        _, stderr = process.communicate(timeout=_CHILD_TIMEOUT)
    finally:
        if process.poll() is None:
            process.kill()
    assert process.returncode == 128 + signal.SIGTERM, stderr
    (host.work / "ready").unlink()
    _assert_nothing_left(host)


def test_the_scan_finds_a_copy_left_under_streamlits_home(host):
    """The checks above would see a copy: one left in ~/.streamlit is found."""
    left = host.home / ".streamlit" / "cache" / "case.bin"
    left.parent.mkdir(parents=True)
    left.write_bytes(b"\x00" + host.marker.encode() + b"\x00")
    assert host.files_holding_the_marker() == [left]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port


def _healthy(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1) as response:  # noqa: S310
            return bool(response.status == 200)
    except OSError:
        return False


@pytest.mark.spec("SHD-01-003")
def test_sigterm_stops_the_real_server_and_removes_its_tempdir(host):
    port = _free_port()
    process = subprocess.Popen(
        [sys.executable, "-c", _LAUNCHER, "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=host.work,
        env=host.env(),
    )
    try:
        deadline = time.monotonic() + _CHILD_TIMEOUT
        url = f"http://127.0.0.1:{port}/_stcore/health"
        while not _healthy(url):
            if process.poll() is not None or time.monotonic() > deadline:
                process.kill()
                _, stderr = process.communicate()
                pytest.fail(f"the server did not start: {stderr}")
            time.sleep(0.2)
        assert len(host.leftover_tempdirs()) == 1
        process.send_signal(signal.SIGTERM)
        _, stderr = process.communicate(timeout=_CHILD_TIMEOUT)
    finally:
        if process.poll() is None:
            process.kill()
    assert process.returncode == 0, stderr
    _assert_nothing_left(host)


@pytest.fixture
def outer_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    return tmp_path


def test_the_private_tempdir_takes_the_runs_temporary_files(outer_tmp):
    with private_tempdir() as private:
        assert private.parent == outer_tmp
        assert private.name.startswith(TEMPDIR_PREFIX)
        assert tempfile.gettempdir() == str(private)
        assert os.environ["TMPDIR"] == str(private)
        (private / "work.txt").write_text("transient")
    assert not private.exists()
    assert tempfile.tempdir == str(outer_tmp)
    assert os.environ["TMPDIR"] == str(outer_tmp)


def test_the_private_tempdir_is_removed_when_the_run_raises(outer_tmp):
    with pytest.raises(RuntimeError), private_tempdir() as private:
        (private / "work.txt").write_text("transient")
        raise RuntimeError("a read failed")
    assert not private.exists()


def test_with_no_tmpdir_set_none_is_left_set(outer_tmp, monkeypatch):
    monkeypatch.delenv("TMPDIR")
    with private_tempdir():
        assert "TMPDIR" in os.environ
    assert "TMPDIR" not in os.environ


def test_sigterm_handling_is_restored_after_the_run(outer_tmp):
    before = signal.getsignal(signal.SIGTERM)
    with private_tempdir():
        assert signal.getsignal(signal.SIGTERM) is not before
    assert signal.getsignal(signal.SIGTERM) is before


@pytest.mark.spec("SHD-01-003")
def test_the_launcher_runs_streamlit_in_a_private_tempdir(
    outer_tmp, monkeypatch
):
    seen: list[Path] = []

    def fake_main(*, args: list[str], prog_name: str) -> None:
        private = Path(tempfile.gettempdir())
        (private / "work.txt").write_text("transient")
        seen.append(private)

    monkeypatch.setattr(cli.streamlit_cli, "main", fake_main)
    result = CliRunner().invoke(cli.main, [])
    assert result.exit_code == 0, result.output
    (private,) = seen
    assert private.parent == outer_tmp
    assert private.name.startswith(TEMPDIR_PREFIX)
    assert not private.exists()


def _persist_calls(root: Path) -> Iterator[str]:
    """Every call under *root* that passes ``persist``, as ``path:line``."""
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and any(
                keyword.arg == "persist" for keyword in node.keywords
            ):
                yield f"{path.relative_to(root)}:{node.lineno}"


@pytest.mark.spec("SHD-01-003")
def test_no_streamlit_cache_in_the_tool_persists_to_disk():
    """``st.cache_data(persist=...)`` writes to ``~/.streamlit/cache``."""
    assert list(_persist_calls(_SHADOW)) == []


def test_the_persist_scan_sees_a_persisting_cache(tmp_path):
    """The scan above would find one: a persisting cache call is found."""
    source = tmp_path / "page.py"
    source.write_text(
        "import streamlit as st\n@st.cache_data(persist='disk')\n"
        "def f(): ...\n"
    )
    assert list(_persist_calls(tmp_path)) == ["page.py:2"]
