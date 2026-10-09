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

"""Integration tests: the demo ledger stream against a real uvicorn server.

``TestClient`` reads a response to its end, so it cannot follow a stream that
stays open; these tests serve the app with uvicorn and read the stream over a
socket (ADR-0104 § Validation, #3641 AC-4).
"""

import json
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx2 as httpx
import pytest
import uvicorn

from test.adapters.driving.fastapi import ledger_stream_server as srv
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.adapters.utils import strip_id_prefix
from vultron.config import config_override

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[4]
STREAM_PATH = (
    f"/api/v2/actors/{srv.ACTOR_ID}/demo/cases/"
    f"{strip_id_prefix(srv.CASE_ID)}/log/stream"
)


def _read_event(lines: Iterator[str]) -> dict[str, str]:
    """Read lines up to the blank line that ends one SSE event."""
    fields: dict[str, str] = {}
    for line in lines:
        if line == "":
            if fields:
                return fields
            continue
        name, _, value = line.partition(": ")
        fields[name] = value
    raise AssertionError(f"stream ended mid-event: {fields}")


def _wait_until(predicate, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("condition not met before timeout")
        time.sleep(0.02)


@pytest.fixture
def stream_dl() -> Iterator[SqliteDataLayer]:
    reset_datalayer(srv.ACTOR_ID)
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=srv.ACTOR_ID)
    dl.clear_all()
    yield dl
    dl.close()
    reset_datalayer(srv.ACTOR_ID)


@pytest.fixture
def base_url(stream_dl: SqliteDataLayer) -> Iterator[str]:
    """Serve :func:`srv.build_app` with uvicorn on a worker thread."""
    with config_override(
        VULTRON_MODE="prototype",
        VULTRON_SERVER__LEDGER_STREAM_POLL_SECONDS="0.05",
    ):
        app = srv.build_app(stream_dl)
        config = uvicorn.Config(
            app, host="127.0.0.1", port=0, log_level="warning", lifespan="on"
        )
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, daemon=True)
        # The sync-log-entry fan-out runs as a background task; keep it off
        # the network.
        with patch(
            "vultron.adapters.driving.fastapi.outbox_handler.get_default_emitter",
            return_value=AsyncMock(),
        ):
            thread.start()
            _wait_until(lambda: server.started)
            port = server.servers[0].sockets[0].getsockname()[1]
            yield f"http://127.0.0.1:{port}"
            server.should_exit = True
            thread.join(timeout=15)
    assert not thread.is_alive(), "uvicorn did not shut down"


def _commit(client: httpx.Client, event_type: str) -> int:
    response = client.post(
        f"/api/v2/actors/{srv.ACTOR_ID}/demo/sync-log-entry",
        json={
            "case_id": srv.CASE_ID,
            "object_id": srv.CASE_ID,
            "event_type": event_type,
        },
    )
    assert response.status_code == 202, response.text
    return response.json()["log_index"]


def test_connect_replay_commit_receive_disconnect(base_url: str, caplog):
    """AC-4: connect → existing entries → commit → receive it → disconnect."""
    with httpx.Client(base_url=base_url, timeout=10) as client:
        first = _commit(client, "before_connect_0")
        second = _commit(client, "before_connect_1")
        listed = client.get(
            f"/api/v2/actors/{srv.ACTOR_ID}/demo/cases/"
            f"{strip_id_prefix(srv.CASE_ID)}/log"
        ).json()

        with caplog.at_level(logging.INFO):
            with client.stream("GET", STREAM_PATH) as response:
                assert response.status_code == 200
                assert response.headers["content-type"].startswith(
                    "text/event-stream"
                )
                lines = response.iter_lines()

                replayed = [_read_event(lines), _read_event(lines)]
                assert [int(e["id"]) for e in replayed] == [first, second]
                assert [json.loads(e["data"]) for e in replayed] == listed

                third = _commit(client, "after_connect")
                pushed = _read_event(lines)
                assert int(pushed["id"]) == third
                assert json.loads(pushed["data"])["eventType"] == (
                    "after_connect"
                )
            # Leaving the block closes the connection.

            _wait_until(lambda: "client disconnected" in caplog.text)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_sigterm_sends_close_and_lets_the_server_exit():
    """A real SIGTERM ends an open stream with ``event: close``.

    uvicorn waits for open connections before running lifespan shutdown, so
    without the signal hook this server would hang until the graceful
    shutdown timeout instead of exiting.
    """
    port = _free_port()
    env = {
        **os.environ,
        "VULTRON_MODE": "prototype",
        "VULTRON_SERVER__LEDGER_STREAM_POLL_SECONDS": "0.05",
        "PYTHONPATH": str(REPO_ROOT),
    }
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "--factory",
            "test.adapters.driving.fastapi.ledger_stream_server:make_seeded_app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        url = f"http://127.0.0.1:{port}"

        def up() -> bool:
            try:
                httpx.get(f"{url}/api/v2/health/ready", timeout=0.5)
            except httpx.TransportError:
                return False
            return True

        _wait_until(up, timeout=30)
        with httpx.Client(base_url=url, timeout=10) as client:
            with client.stream("GET", STREAM_PATH) as response:
                assert response.status_code == 200
                lines = response.iter_lines()
                replayed = [
                    _read_event(lines) for _ in range(srv.SEEDED_ENTRIES)
                ]
                assert [e["id"] for e in replayed] == ["0", "1"]

                proc.send_signal(signal.SIGTERM)

                assert _read_event(lines) == {"event": "close", "data": ""}
        # uvicorn's default graceful-shutdown timeout is unbounded, so an exit
        # at all means the stream let go.  After a clean shutdown uvicorn
        # re-raises the signal it caught, hence -SIGTERM rather than 0.
        assert proc.wait(timeout=15) in (0, -signal.SIGTERM)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        if proc.stdout is not None:
            proc.stdout.close()
