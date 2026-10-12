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

"""Unit tests for the demo case ledger SSE stream (ADR-0104, #3641)."""

import asyncio
import json
import logging
import signal
import threading
from collections.abc import Iterator
from types import FrameType

import pytest

from test.adapters.driving.fastapi.sse_helpers import (
    parse_sse_body,
    save_ledger_entry,
)
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.adapters.driving.fastapi.ledger_stream import (
    case_ledger_entries,
    format_close_event,
    format_entry_event,
    install_shutdown_signal_hook,
    ledger_entry_payload,
    resolve_resume_index,
    stream_case_ledger,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

POLL = 0.01
ACTOR = "urn:uuid:4d1c0b7e-2f3a-4e5b-8c6d-7e8f9a0b1c2d"


@pytest.fixture
def dl() -> Iterator[SqliteDataLayer]:
    actor = as_Service(name="Stream Actor Co")
    reset_datalayer(actor.id_)
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=actor.id_)
    store.clear_all()
    store.create(actor)
    yield store
    store.close()
    reset_datalayer(actor.id_)


@pytest.fixture
def case(dl: SqliteDataLayer) -> as_VulnerabilityCase:
    case_obj = as_VulnerabilityCase(name="STREAM-CASE")
    dl.create(case_obj)
    return case_obj


def _parse(frame: str) -> dict[str, str]:
    """Parse one SSE frame into its field → value map."""
    assert frame.endswith("\n\n"), frame
    (event,) = parse_sse_body(frame)
    return event


async def _never_disconnected() -> bool:
    return False


async def _collect(
    dl: SqliteDataLayer,
    case_id: str,
    *,
    after_index: int | None = None,
    shutdown: threading.Event | None = None,
    is_disconnected=_never_disconnected,
    limit: int = 50,
) -> list[str]:
    if shutdown is None:
        shutdown = threading.Event()
        shutdown.set()
    frames: list[str] = []
    async for frame in stream_case_ledger(
        dl,
        case_id,
        actor_id=ACTOR,
        after_index=after_index,
        poll_seconds=POLL,
        is_disconnected=is_disconnected,
        shutdown=shutdown,
    ):
        frames.append(frame)
        assert len(frames) <= limit, "stream did not end"
    return frames


class TestResolveResumeIndex:
    def test_neither_means_replay_everything(self):
        assert resolve_resume_index(None, None) is None

    def test_since_alone(self):
        assert resolve_resume_index(3, None) == 3

    def test_last_event_id_alone(self):
        assert resolve_resume_index(None, "4") == 4

    def test_higher_of_both_wins(self):
        # A browser reconnect keeps the original ?since= and adds the header.
        assert resolve_resume_index(1, "5") == 5
        assert resolve_resume_index(7, "5") == 7

    def test_surrounding_whitespace_is_tolerated(self):
        assert resolve_resume_index(None, " 2 ") == 2

    @pytest.mark.parametrize("bad", ["", "abc", "-1", "1.5"])
    def test_non_index_last_event_id_is_refused(self, bad: str):
        with pytest.raises(ValueError, match="Last-Event-ID"):
            resolve_resume_index(None, bad)


class TestFraming:
    def test_entry_event_carries_index_and_list_payload(self, dl, case):
        entry = save_ledger_entry(dl, case.id_, 2)
        fields = _parse(format_entry_event(entry))
        assert fields["id"] == "2"
        assert json.loads(fields["data"]) == ledger_entry_payload(entry)

    def test_payload_is_the_wire_form_without_nones(self, dl, case):
        payload = ledger_entry_payload(save_ledger_entry(dl, case.id_, 0))
        assert payload["logIndex"] == 0
        assert "log_index" not in payload
        assert None not in payload.values()

    def test_close_event(self):
        assert _parse(format_close_event()) == {"event": "close", "data": ""}


class TestCaseLedgerEntries:
    def test_sorted_and_scoped_to_the_case(self, dl, case):
        other = as_VulnerabilityCase(name="OTHER")
        dl.create(other)
        for i in (2, 0, 1):
            save_ledger_entry(dl, case.id_, i)
        save_ledger_entry(dl, other.id_, 0)
        entries = case_ledger_entries(dl, case.id_)
        assert [e.log_index for e in entries] == [0, 1, 2]
        assert {e.case_id for e in entries} == {case.id_}


class TestStreamCaseLedger:
    def test_replays_stored_entries_then_closes_on_shutdown(self, dl, case):
        for i in range(3):
            save_ledger_entry(dl, case.id_, i)
        frames = asyncio.run(_collect(dl, case.id_))
        assert [_parse(f).get("id") for f in frames[:-1]] == ["0", "1", "2"]
        assert frames[-1] == format_close_event()

    def test_after_index_skips_entries_at_or_below_it(self, dl, case):
        for i in range(4):
            save_ledger_entry(dl, case.id_, i)
        frames = asyncio.run(_collect(dl, case.id_, after_index=1))
        assert [_parse(f).get("id") for f in frames[:-1]] == ["2", "3"]

    def test_empty_ledger_sends_only_close(self, dl, case):
        assert asyncio.run(_collect(dl, case.id_)) == [format_close_event()]

    def test_pushes_an_entry_committed_after_connect(self, dl, case):
        save_ledger_entry(dl, case.id_, 0)
        shutdown = threading.Event()

        async def scenario() -> list[str]:
            frames: list[str] = []
            stream = stream_case_ledger(
                dl,
                case.id_,
                actor_id=ACTOR,
                after_index=None,
                poll_seconds=POLL,
                is_disconnected=_never_disconnected,
                shutdown=shutdown,
            )
            frames.append(await anext(stream))
            save_ledger_entry(dl, case.id_, 1)
            frames.append(await asyncio.wait_for(anext(stream), 5))
            shutdown.set()
            frames.extend([f async for f in stream])
            return frames

        frames = asyncio.run(scenario())
        assert [_parse(f).get("id") for f in frames[:2]] == ["0", "1"]
        assert frames[2:] == [format_close_event()]

    def test_disconnect_ends_the_stream_without_a_close_event(
        self, dl, case, caplog
    ):
        save_ledger_entry(dl, case.id_, 0)
        calls: int = 0

        async def disconnects_on_second_check() -> bool:
            nonlocal calls
            calls += 1
            return calls >= 2

        with caplog.at_level(logging.INFO):
            frames = asyncio.run(
                _collect(
                    dl,
                    case.id_,
                    shutdown=threading.Event(),
                    is_disconnected=disconnects_on_second_check,
                )
            )
        assert [_parse(f).get("id") for f in frames] == ["0"]
        assert calls == 2
        assert "client disconnected" in caplog.text

    def test_a_failing_read_is_logged_as_a_failure_not_a_disconnect(
        self, dl, case, caplog, monkeypatch
    ):
        def broken(*_args, **_kwargs):
            raise RuntimeError("store unavailable")

        monkeypatch.setattr(dl, "list_objects", broken)
        with caplog.at_level(logging.INFO):
            with pytest.raises(RuntimeError, match="store unavailable"):
                asyncio.run(_collect(dl, case.id_))
        assert "stream failed" in caplog.text
        assert "client disconnected" not in caplog.text

    def test_shutdown_is_logged_as_the_close_reason(self, dl, case, caplog):
        with caplog.at_level(logging.INFO):
            asyncio.run(_collect(dl, case.id_))
        assert f"Ledger stream opened (actor_id={ACTOR}" in caplog.text
        assert "server shutting down" in caplog.text


class TestInstallShutdownSignalHook:
    @pytest.fixture
    def saved_handlers(self) -> Iterator[None]:
        saved = {
            s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)
        }
        yield
        for sig, handler in saved.items():
            signal.signal(sig, handler)

    @pytest.fixture
    def on_main_thread(self) -> None:
        if threading.current_thread() is not threading.main_thread():
            pytest.fail("signal hook tests must run on the main thread")

    @pytest.mark.usefixtures("saved_handlers", "on_main_thread")
    def test_chains_onto_the_server_handler(self):
        received: list[int] = []

        def server_exit(signum: int, frame: FrameType | None) -> None:
            received.append(signum)

        signal.signal(signal.SIGTERM, server_exit)
        shutdown = threading.Event()
        undo = install_shutdown_signal_hook(shutdown)

        hook = signal.getsignal(signal.SIGTERM)
        assert callable(hook) and hook is not server_exit
        hook(signal.SIGTERM, None)

        assert shutdown.is_set()
        assert received == [signal.SIGTERM]
        undo()
        assert signal.getsignal(signal.SIGTERM) is server_exit

    @pytest.mark.usefixtures("saved_handlers", "on_main_thread")
    def test_default_disposition_is_left_alone(self):
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        undo = install_shutdown_signal_hook(threading.Event())
        assert signal.getsignal(signal.SIGTERM) is signal.SIG_DFL
        undo()
        assert signal.getsignal(signal.SIGTERM) is signal.SIG_DFL

    @pytest.mark.usefixtures("saved_handlers", "on_main_thread")
    def test_undo_does_not_clobber_a_later_handler(self):
        def server_exit(signum: int, frame: FrameType | None) -> None:
            pass

        def later(signum: int, frame: FrameType | None) -> None:
            pass

        signal.signal(signal.SIGTERM, server_exit)
        undo = install_shutdown_signal_hook(threading.Event())
        signal.signal(signal.SIGTERM, later)
        undo()
        assert signal.getsignal(signal.SIGTERM) is later

    @pytest.mark.usefixtures("saved_handlers")
    def test_off_the_main_thread_installs_nothing(self):
        before = signal.getsignal(signal.SIGINT)
        result: list[object] = []

        def worker() -> None:
            undo = install_shutdown_signal_hook(threading.Event())
            undo()
            result.append(signal.getsignal(signal.SIGINT))

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()
        assert result == [before]
