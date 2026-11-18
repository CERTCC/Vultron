"""The CI check that the shadow image's live reader reads a node's case (#6642).

``.github/scripts/shadow_live_read.py`` runs in the shadow container beside
the demo stack's ``case-actor`` node. The dev container has no Docker, so
these tests run it over a scripted node stream, and read the workflow that
runs it (SHD-02-001, SHD-02-002, SHD-04-001).
"""

from __future__ import annotations

import pytest

from test.ci._scripts import load_script
from test.ci._workflows import REPO_ROOT, load_workflow
from test.support.ledger_stream import (
    ACTOR,
    CLOSE,
    NODE,
    ScriptedStream,
    ledger_entry_row,
    sse_event,
)
from vultron.shadow.readers import VultronNodeCaseReader

_live = load_script("shadow_live_read")

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "shadow-image.yml"
_CASE = "urn:uuid:case-1"


class _Clock:
    """A clock that moves only when the check pauses."""

    def __init__(self) -> None:
        self.now = 0.0
        self.pauses = 0

    def __call__(self) -> float:
        return self.now

    def pause(self, seconds: float) -> None:
        self.pauses += 1
        self.now += seconds


def _run(script: ScriptedStream, *args: str) -> tuple[int, _Clock]:
    clock = _Clock()
    status = _live.main(
        [NODE, ACTOR, _CASE, *args],
        reader_for=lambda _node: script.reader(reconnects=0),
        clock=clock,
        pause=clock.pause,
    )
    return status, clock


def _entries(*indices: int) -> str:
    return "".join(sse_event(ledger_entry_row(_CASE, i), i) for i in indices)


def test_a_case_with_an_entry_passes(capsys):
    script = ScriptedStream(_entries(0, 1) + CLOSE)
    status, _ = _run(script)
    assert status == 0
    assert "ledger entries: 1" in capsys.readouterr().out


@pytest.mark.spec("SHD-04-001")
def test_the_check_sends_only_gets_of_the_ledger_stream():
    script = ScriptedStream(CLOSE, _entries(0) + CLOSE)
    status, _ = _run(script)
    assert status == 0
    assert {r.method for r in script.requests} == {"GET"}
    assert all(r.url.path.endswith("/log/stream") for r in script.requests)


def test_a_case_not_committed_yet_is_tried_again(capsys):
    """A new case's first entry lands a moment after it is created."""
    script = ScriptedStream((404, "{}"), CLOSE, _entries(0) + CLOSE)
    status, clock = _run(script)
    assert status == 0
    assert clock.pauses == 2


def test_no_entry_by_the_deadline_fails_with_the_last_reason(capsys):
    script = ScriptedStream(*[(404, "{}")] * 10)
    status, _ = _run(script, "--deadline", "3")
    assert status == 1
    out = capsys.readouterr().out
    assert "timed out" in out
    assert "HTTP 404" in out


def test_a_quiet_case_stops_at_the_deadline(capsys):
    """A stream that only keeps alive is stopped by its heartbeat."""

    class Quiet:
        def follow_case(self, case_id, *, heartbeat):
            while True:
                clock.now += 1.0
                heartbeat()
                yield from ()

    clock = _Clock()
    status = _live.main(
        [NODE, ACTOR, _CASE, "--deadline", "5"],
        reader_for=lambda _node: Quiet(),
        clock=clock,
        pause=clock.pause,
    )
    assert status == 1
    assert "timed out" in capsys.readouterr().out
    assert clock.now == 5.0


def test_a_node_reader_that_cannot_follow_is_refused(monkeypatch):
    monkeypatch.setattr(
        _live, "configured_case_reader", lambda *_a, **_k: object()
    )
    with pytest.raises(TypeError, match="cannot follow"):
        _live.page_reader(_live.typed_node(NODE, ACTOR))


def test_a_refused_node_sends_no_request(capsys):
    script = ScriptedStream()
    clock = _Clock()
    status = _live.main(
        ["http://user:secret@node.test/api/v2", ACTOR, _CASE],
        reader_for=lambda _node: script.reader(),
        clock=clock,
        pause=clock.pause,
    )
    assert status == 2
    assert not script.requests
    assert "secret" not in capsys.readouterr().out


def test_the_check_reads_through_the_pages_node_reader():
    reader = _live.page_reader(_live.typed_node(NODE, ACTOR))
    assert isinstance(reader, VultronNodeCaseReader)
    assert reader.node_url == NODE


# ── The workflow that runs the check ───────────────────────────────────────


def _steps() -> list[dict[str, object]]:
    steps = load_workflow(WORKFLOW)["jobs"]["shadow-image"]["steps"]
    assert isinstance(steps, list)
    return steps


def _index(steps: list[dict[str, object]], needle: str) -> int:
    """The first step whose run script or environment holds *needle*."""
    return next(
        i
        for i, s in enumerate(steps)
        if needle in str(s.get("run", "")) + str(s.get("env", ""))
    )


def test_the_job_reads_a_case_off_the_case_actor_node():
    """AC-5: the node starts, a case is created, the image reads it."""
    steps = _steps()
    start = _index(steps, "docker-compose-multi-actor.yml \\\n  up")
    seed = _index(steps, "trigger/create-case")
    check = _index(steps, "shadow_live_read.py")
    assert start < seed < check
    assert "case-actor" in str(steps[start]["run"])
    run = str(steps[check]["run"])
    assert "docker compose -f docker/docker-compose.yml exec -T shadow" in run
    env = steps[check]["env"]
    assert isinstance(env, dict)
    assert env["NODE_URL"] == "http://case-actor:7999/api/v2"
    assert env["CASE_ID"] == "${{ steps.seed.outputs.case-id }}"


def test_the_job_builds_the_node_image_with_the_shadow_image():
    steps = _steps()
    (build,) = [s for s in steps if s.get("name") == "Build the shadow image"]
    assert build["with"] == {
        "compose-file": "docker-compose.yml",
        "targets": "shadow api-dev",
    }


@pytest.mark.spec("SHD-02-001", "SHD-02-002")
def test_the_shadow_service_is_still_checked_before_the_node_starts():
    """The node's network and volumes are its own: the shadow service still
    mounts nothing and publishes on loopback only."""
    steps = _steps()
    loopback = _index(
        steps, "docker compose -f docker/docker-compose.yml port"
    )
    start = _index(steps, "docker-compose-multi-actor.yml \\\n  up")
    assert loopback < start
    run = str(steps[loopback]["run"])
    assert '"$mounts" != "[]"' in run
    assert '"$published" != "127.0.0.1:8501"' in run
