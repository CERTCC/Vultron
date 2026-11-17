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

"""The case shadow's log records carry ids, never case content.

The page runs headless under Streamlit's ``AppTest`` over a fake case
reader whose case holds a marker string in its title, description, a
contact name, a tracker reference's name and an untranslated record.  Every
log record the process makes during the run is captured, at every level and
from every logger, Streamlit's own included:

* no record carries the marker (AC-1), and the run did log the case, its
  entries' activity ids and their source records, so the check is not
  vacuous;
* every record that names the case also names its tracker reference (AC-2);
* an exception raised while the case is handled, or by the reader, is
  logged with its traceback and without the marker (AC-3).

Spec: VSD-01-003, SL-01-005, EH-06-001.
"""

from __future__ import annotations

import io
import logging
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import PurePosixPath

import pytest
from click.testing import CliRunner
from pydantic import BaseModel, ValidationError
from streamlit.testing.v1 import AppTest

from test.support.case_reader import (
    CONTENT_MARKER,
    FAKE_CASE,
    TRACKER_REFERENCE,
    FakeCaseReader,
    marked_case_records,
)
from vultron.errors import VultronError
from vultron.logging_correlation import correlation_context
from vultron.shadow.dashboard import cli
from vultron.shadow.log_content import (
    UNCLEANED,
    WITHHELD,
    WITHHELD_MESSAGE,
    ShadowFormatter,
    case_log_context,
    reading_content,
    records,
    shadow_logging,
    tracker_references,
    withheld_case_content,
)
from vultron.shadow.log_content.render import MAX_CHAIN

MARKER = CONTENT_MARKER
REFERENCE = TRACKER_REFERENCE

_TIMEOUT = 60

_FORMAT = "%(levelname)s %(name)s: %(message)s"

# The scripts name the marker, never spell it: a traceback quotes the
# source line it passes through, and the case's content is not in the code.
_PAGE = """
from test.support.case_reader import FAKE_CASE, FakeCaseReader, marked_case_records
from vultron.shadow.dashboard.page import render

render(FakeCaseReader({FAKE_CASE: marked_case_records()}))
"""

# The analysis fails after the case is read.  The Vultron error quotes the
# case's title, and the exception that caused it quotes the marker.
_FAILING_PAGE = """
from test.support.case_reader import (
    CONTENT_MARKER, FAKE_CASE, FakeCaseReader, marked_case_records,
)
from vultron.errors import VultronError
from vultron.shadow.dashboard import page

def analyse(reading):
    title = reading.ledger[0].payload_snapshot["object"]["name"]
    try:
        raise ValueError("cannot score " + CONTENT_MARKER)
    except ValueError as exc:
        raise VultronError("analysis of " + title + " failed") from exc

saved = page.analyse
page.analyse = analyse
try:
    page.render(FakeCaseReader({FAKE_CASE: marked_case_records()}))
finally:
    page.analyse = saved
"""

# The reader itself fails, as a reader that validates its source's records
# does: the validation error quotes the input it refused.
_FAILING_READER_PAGE = """
from pydantic import BaseModel
from test.support.case_reader import CONTENT_MARKER
from vultron.shadow.dashboard.page import render

class Record(BaseModel):
    count: int

class Reader:
    unobservable = ()

    def read_case(self, case_id):
        Record(count=CONTENT_MARKER)

render(Reader())
"""


@contextmanager
def _every_record() -> Generator[list[logging.LogRecord]]:
    """Every log record the process makes in the block, as it is made."""
    records: list[logging.LogRecord] = []
    with withheld_case_content():
        inner = logging.getLogRecordFactory()

        def collect(*args: object, **kwargs: object) -> logging.LogRecord:
            record = inner(*args, **kwargs)
            records.append(record)
            return record

        logging.setLogRecordFactory(collect)
        try:
            yield records
        finally:
            logging.setLogRecordFactory(inner)


def _text(record: logging.LogRecord) -> str:
    return ShadowFormatter(_FORMAT).format(record)


def _assert_marker_nowhere(records: list[logging.LogRecord]) -> None:
    assert records, "the run made no log record"
    for record in records:
        assert MARKER not in _text(record), _text(record)
        assert MARKER not in repr(vars(record)), vars(record)


def _run(script: str, case_id: str = FAKE_CASE) -> list[logging.LogRecord]:
    with _every_record() as records:
        at = AppTest.from_string(script, default_timeout=_TIMEOUT).run()
        at.text_input[0].input(case_id).run()
    return records


@pytest.fixture
def debug_logs(caplog: pytest.LogCaptureFixture) -> None:
    """Make every Vultron record, DEBUG included."""
    caplog.set_level(logging.DEBUG)


@pytest.mark.spec("VSD-01-003")
@pytest.mark.usefixtures("debug_logs")
def test_a_shadow_run_logs_the_case_and_never_its_content():
    """AC-1: no record, at any level, carries the marker."""
    records = _run(_PAGE)
    _assert_marker_nowhere(records)
    levels = {
        record.levelno
        for record in records
        if record.name.startswith("vultron.")
    }
    assert {logging.DEBUG, logging.INFO} <= levels
    texts = [_text(record) for record in records]
    assert any(f"Read case {FAKE_CASE}" in text for text in texts)
    # The entries' source records are named, so the check is not vacuous.
    assert any("source record rec-open" in text for text in texts)


@pytest.mark.spec("VSD-01-003")
@pytest.mark.spec("SL-02-003")
@pytest.mark.usefixtures("debug_logs")
def test_a_shadow_run_names_the_activity_and_the_tracker_reference():
    """AC-2: entry records carry their activity id, and every record that
    names the case names its tracker reference."""
    records = _run(_PAGE)
    activities = {vars(record).get("activity_id") for record in records}
    assert f"{FAKE_CASE}/activity/rec-open" in activities
    naming = [
        record
        for record in records
        if getattr(record, "case_id", None) == FAKE_CASE
        or FAKE_CASE in record.getMessage()
    ]
    assert naming
    for record in naming:
        assert getattr(record, "case_reference", None) == REFERENCE
        assert f"case_reference={REFERENCE}" in _text(record)


@pytest.mark.spec("VSD-01-003")
@pytest.mark.usefixtures("debug_logs")
def test_an_exception_while_a_case_is_handled_logs_no_content():
    """AC-3: the traceback is logged; the marker is not."""
    records = _run(_FAILING_PAGE)
    _assert_marker_nowhere(records)
    tracebacks = [record for record in records if record.exc_text]
    assert tracebacks, "the failure was not logged"
    text = _text(tracebacks[0])
    assert "Traceback (most recent call last):" in text
    assert (
        f"vultron.errors.VultronError: analysis of {WITHHELD} failed" in text
    )
    assert f"ValueError: {WITHHELD_MESSAGE}" in text
    assert "The above exception was the direct cause" in text
    # Streamlit logs it after the page's case context has ended; the
    # exception carried the case out with it.
    assert getattr(tracebacks[0], "case_reference", None) == REFERENCE


@pytest.mark.spec("VSD-01-003")
@pytest.mark.usefixtures("debug_logs")
def test_a_reader_failure_logs_no_input_it_refused():
    """AC-3: a validation error is logged by field and kind, no input."""
    records = _run(_FAILING_READER_PAGE)
    _assert_marker_nowhere(records)
    tracebacks = [record for record in records if record.exc_text]
    assert tracebacks, "the failure was not logged"
    text = _text(tracebacks[0])
    assert "pydantic_core._pydantic_core.ValidationError" in text
    assert "count: int_parsing" in text


@pytest.mark.spec("EH-06-001")
@pytest.mark.usefixtures("debug_logs")
def test_a_refused_read_is_logged_at_warning():
    records = _run(_PAGE, case_id="urn:uuid:no-such-case")
    warnings = [
        record
        for record in records
        if record.levelno == logging.WARNING
        and record.name == "vultron.shadow.dashboard.page"
    ]
    assert len(warnings) == 1
    assert "Could not read case urn:uuid:no-such-case" in _text(warnings[0])


def _reading():
    reader = FakeCaseReader(
        {FAKE_CASE: marked_case_records(MARKER, REFERENCE)}
    )
    return reader.read_case(FAKE_CASE)


def test_reading_content_holds_the_content_and_none_of_the_ids():
    reading = _reading()
    content = reading_content(reading)
    assert f"Title {MARKER}" in content
    assert f"Contact {MARKER}" in content
    # Each line of a multi-line string is withheld on its own too.
    assert f"Vul detail {MARKER} here." in content
    assert f"kind = post_{MARKER}" in content
    ids = {FAKE_CASE, REFERENCE, "rec-open", "RECEIVED", "ACTIVE"}
    ids |= {entry.log_object_id for entry in reading.ledger}
    assert not ids & set(content)
    assert all(len(piece) >= 4 for piece in content)
    assert list(content) == sorted(content, key=lambda p: (-len(p), p))


def test_tracker_references_are_the_issue_tracking_links():
    assert tracker_references(_reading()) == (REFERENCE,)


class _Record(BaseModel):
    count: int


def _validation_error() -> ValidationError:
    try:
        _Record(count=MARKER)  # type: ignore[arg-type]
    except ValidationError as exc:
        return exc
    raise AssertionError("no validation error")


@pytest.fixture
def shadow_log() -> Generator[io.StringIO]:
    """The shadow's logging, at DEBUG, written to a buffer."""
    stream = io.StringIO()
    with shadow_logging(logging.DEBUG, stream):
        yield stream


@pytest.mark.parametrize(
    ("arg", "rendered"),
    [
        (_Record(count=1), "<_Record>"),
        ({"title": MARKER}, "<dict>"),
        (ValueError(MARKER), f"ValueError: {WITHHELD_MESSAGE}"),
        (VultronError("case urn:x refused"), "case urn:x refused"),
        (
            _validation_error(),
            "1 validation error(s) for _Record (count: int_parsing)",
        ),
        ((1, "two"), "(1, 'two')"),
    ],
)
def test_an_argument_is_logged_without_its_content(shadow_log, arg, rendered):
    logging.getLogger("vultron.test").info("value %s", arg)
    line = shadow_log.getvalue()
    assert rendered in line
    assert MARKER not in line


def test_the_shadow_log_names_case_and_ids_and_withholds_content(shadow_log):
    log = logging.getLogger("vultron.test")
    with case_log_context(FAKE_CASE) as case_log:
        log.info("before the read: %s", MARKER)
        case_log.withhold(_reading())
        with correlation_context(
            activity_id="urn:activity:1", actor_id="urn:actor:1"
        ):
            log.debug("the title is %s", f"Title {MARKER}")
    log.info("after: %s", MARKER)
    lines = shadow_log.getvalue().splitlines()
    assert f"[case_id={FAKE_CASE}]" in lines[0]
    assert f"the title is {WITHHELD}" in lines[1]
    assert (
        "[activity_id=urn:activity:1 actor_id=urn:actor:1"
        f" case_id={FAKE_CASE} case_reference={REFERENCE}]"
    ) in lines[1]
    # Outside the context the content is not known, and no case is named.
    assert "case_id" not in lines[2]


def test_shadow_logging_puts_logging_back_on_exit():
    root = logging.getLogger()
    factory, level, handlers = (
        logging.getLogRecordFactory(),
        root.level,
        list(root.handlers),
    )
    with shadow_logging(logging.DEBUG, io.StringIO()) as handler:
        assert handler in root.handlers
        assert root.level == logging.DEBUG
        assert logging.getLogRecordFactory() is not factory
    assert logging.getLogRecordFactory() is factory
    assert root.level == level
    assert root.handlers == handlers


@pytest.mark.parametrize(
    ("option", "level"),
    [([], logging.INFO), (["--log-level", "debug"], logging.DEBUG)],
)
def test_the_launcher_runs_streamlit_inside_the_shadow_logging(
    monkeypatch: pytest.MonkeyPatch, option: list[str], level: int
) -> None:
    seen: list[tuple[int, bool]] = []

    def fake_main(*, args: list[str], prog_name: str) -> None:
        root = logging.getLogger()
        seen.append(
            (
                root.level,
                any(
                    isinstance(h.formatter, ShadowFormatter)
                    for h in root.handlers
                ),
            )
        )

    monkeypatch.setattr(cli.streamlit_cli, "main", fake_main)
    result = CliRunner().invoke(cli.main, option)
    assert result.exit_code == 0, result.output
    assert seen == [(level, True)]


def _logged_exception(
    shadow_log: io.StringIO, raise_it: Callable[[], None]
) -> str:
    try:
        raise_it()
    except Exception:
        logging.getLogger("vultron.test").exception("failed")
    return shadow_log.getvalue()


def test_an_exception_raised_while_handling_another_names_both(shadow_log):
    def lookup() -> None:
        raise KeyError(MARKER)

    def raise_it() -> None:
        try:
            lookup()
        except KeyError:
            raise VultronError("refused")  # noqa: B904 - the implicit context

    text = _logged_exception(shadow_log, raise_it)
    assert f"KeyError: {WITHHELD_MESSAGE}" in text
    assert "During handling of the above exception" in text
    assert "vultron.errors.VultronError: refused" in text
    assert MARKER not in text


def test_an_exception_group_names_each_member(shadow_log):
    def raise_it() -> None:
        raise ExceptionGroup(
            "several", [ValueError(MARKER), VultronError("case refused")]
        )

    text = _logged_exception(shadow_log, raise_it)
    assert "Sub-exception 1:" in text
    assert f"ValueError: {WITHHELD_MESSAGE}" in text
    assert "vultron.errors.VultronError: case refused" in text
    assert MARKER not in text


def test_named_arguments_and_paths_are_made_safe(shadow_log):
    log = logging.getLogger("vultron.test")
    with case_log_context(FAKE_CASE) as case_log:
        case_log.withhold(_reading())
        log.info(
            "title %(title)s count %(n)d", {"title": f"Title {MARKER}", "n": 2}
        )
        log.info("file %s", PurePosixPath("/cases") / f"Title {MARKER}")
        log.info("file %s", PurePosixPath("/cases/rv.jsonl"))
    lines = shadow_log.getvalue().splitlines()
    assert f"title {WITHHELD} count 2" in lines[0]
    assert f"file /cases/{WITHHELD}" in lines[1]
    assert "file /cases/rv.jsonl" in lines[2]
    assert MARKER not in shadow_log.getvalue()


def test_an_inner_case_context_names_its_own_case_on_the_exception(shadow_log):
    def raise_it() -> None:
        with case_log_context("urn:uuid:outer"):
            with case_log_context(FAKE_CASE) as case_log:
                case_log.withhold(_reading())
                raise VultronError(f"Title {MARKER}")

    text = _logged_exception(shadow_log, raise_it)
    assert f"vultron.errors.VultronError: {WITHHELD}" in text
    assert f"case_id={FAKE_CASE} case_reference={REFERENCE}" in text


class _Entry:
    id_ = "urn:uuid:entry-1"


def test_an_object_with_an_id_is_named_by_it_and_none_is_kept(shadow_log):
    logging.getLogger("vultron.test").info("got %s and %s", _Entry(), None)
    assert "got <_Entry urn:uuid:entry-1> and None" in shadow_log.getvalue()


def test_a_stack_and_an_empty_exc_info_are_cleaned(shadow_log):
    log = logging.getLogger("vultron.test")
    with case_log_context(FAKE_CASE) as case_log:
        case_log.withhold(_reading())
        title = f"Title {MARKER}"
        log.info("stack for %s", "it", stack_info=True)
        # A stack frame quoting content, as a source line could.
        record = logging.getLogger("vultron.test").makeRecord(
            "vultron.test",
            logging.INFO,
            __file__,
            1,
            "m",
            (),
            None,
            sinfo=f"Stack (most recent call last):\n  {title}",
        )
        log.info("no exception", exc_info=True)
    assert record.stack_info is not None
    assert MARKER not in record.stack_info
    text = shadow_log.getvalue()
    assert "Stack (most recent call last):" in text
    assert "no exception" in text
    assert "Traceback" not in text


def test_a_reference_that_is_not_issue_tracking_is_not_named():
    reading = _reading()
    payload = reading.ledger[0].payload_snapshot["object"]
    payload["caseReferences"][0]["url"]["rel"] = ["related"]
    assert tracker_references(reading) == ()


def test_a_very_long_chain_does_not_break_the_log_call(shadow_log):
    def raise_it() -> None:
        error: Exception = ValueError(MARKER)
        for _ in range(1200):
            newer = VultronError("again")
            newer.__cause__ = error
            error = newer
        raise error

    text = _logged_exception(shadow_log, raise_it)
    assert f"[exceptions before the last {MAX_CHAIN} not shown]" in text
    assert text.count("vultron.errors.VultronError: again") == MAX_CHAIN
    assert MARKER not in text


def test_a_record_the_cleaning_fails_on_is_still_written(
    shadow_log, monkeypatch
):
    def fail(*_args: object) -> object:
        raise TypeError("broken")

    monkeypatch.setattr(records, "safe_arg", fail)
    logging.getLogger("vultron.test").info("value %s", MARKER)
    text = shadow_log.getvalue()
    assert UNCLEANED % "TypeError" in text
    assert MARKER not in text


def test_content_carried_by_an_exception_joins_the_current_case(shadow_log):
    def raise_it() -> None:
        with case_log_context(FAKE_CASE) as case_log:
            case_log.withhold(_reading())
            raise VultronError(f"Title {MARKER}")

    try:
        raise_it()
    except VultronError:
        with case_log_context("urn:uuid:other"):
            logging.getLogger("vultron.test").exception("later")
    text = shadow_log.getvalue()
    assert "case_id=urn:uuid:other" in text
    assert f"VultronError: {WITHHELD}" in text
